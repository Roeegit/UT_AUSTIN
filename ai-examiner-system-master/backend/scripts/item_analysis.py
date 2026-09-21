#!/usr/bin/env python3
"""
item_analysis.py — offline question-pool quality report for one assignment.

Reads the graded result blobs (local dir or GCS) plus the assignment's question pool, and
scores every pool question on the four signals that reveal weak items, then emits
plain-language recommendations. Run it after an assignment's exams close; feed the output
into pool maintenance (relabel difficulty, cut dead questions) and, eventually, the admin
item-analysis panel (MULTI_COURSE_MIGRATION §4.8).

Metrics (see docs/MULTI_COURSE_MIGRATION §4.8 for the rationale):
  take_rate    asked / offered — a low rate is the examiner voting the question down.
  residual     mean(score - that student's own mean). Corrects for adaptive routing so a
               "hard" question that only strong students see doesn't look easy. Compare to
               the label to catch mislabels.
  ceiling/floor % scoring 5 / % scoring <=2. No 5s ⇒ no headroom.
  divergence   mean pairwise cosine of the question's instantiation embeddings. Low = the
               one pool entry produced genuinely different questions per student (good);
               high = same question, names swapped. Needs sentence-transformers; skipped
               (reported as None) if unavailable. Calibrated bands (a1+a2+a3): green <0.78,
               yellow 0.78-0.84, red >0.84.

Run from backend/:
  python scripts/item_analysis.py --assignment assignment-3 --local-dir C:/tmp/blobs/a3
  python scripts/item_analysis.py --assignment assignment-3          # blobs from GCS
  python scripts/item_analysis.py ... --json report.json             # also dump machine-readable
"""
import argparse
import glob
import json
import os
import statistics as st
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DIV_GREEN, DIV_YELLOW = 0.78, 0.84   # calibrated across a1+a2+a3 (50 questions, n>=8)
MIN_N_FOR_DIVERGENCE = 8


# ---- data loading ----------------------------------------------------------

def _load_blob(text: str) -> dict:
    return json.JSONDecoder().raw_decode(text.lstrip("﻿").lstrip())[0]


def _iter_blobs(assignment: str, local_dir: str | None):
    if local_dir:
        for fp in sorted(glob.glob(os.path.join(local_dir, "*.json"))):
            try:
                yield _load_blob(open(fp, encoding="utf-8-sig").read())
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {os.path.basename(fp)}: {exc}")
        return
    from github_stub import _gcs_client
    bucket = _gcs_client.bucket(os.environ["GCS_SUBMISSIONS_BUCKET"].strip())
    for blob in bucket.list_blobs(prefix=f"results/{assignment}/"):
        if blob.name.endswith(".json"):
            try:
                yield _load_blob(blob.download_as_text())
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {blob.name}: {exc}")


def _load_pool(assignment: str) -> dict:
    p = Path(__file__).parent.parent / "assignments" / f"{assignment}_question_pool.json"
    pool = json.load(open(p, encoding="utf-8"))
    return {q["id"]: q for q in pool["questions"]}


# ---- collection ------------------------------------------------------------

def collect(assignment: str, local_dir: str | None, qmeta: dict):
    """Return (students, offered, texts):
      students — list of per-student [{qid, score}] (score is the graded understandingScore)
      offered  — {qid: times offered}
      texts    — {qid: [questionText, ...]} for the divergence metric
    """
    by_focus = {q["focus"]: qid for qid, q in qmeta.items()}
    students, offered, texts = [], defaultdict(int), defaultdict(list)
    for d in _iter_blobs(assignment, local_dir):
        ex = [t for t in (d.get("transcript") or []) if t.get("role") == "Examiner"
              and isinstance(t.get("content"), dict)]
        turns = []
        for t in ex:
            # Old blobs occasionally carry a malformed turn (e.g. internalEvaluation as a
            # string instead of a dict). Skip any entry that doesn't parse cleanly rather than
            # sinking the whole assignment — the metrics are aggregates, a dropped turn is fine.
            try:
                ct = t.get("chosen_topic")
                ct = ct if isinstance(ct, dict) else {}
                qid = ct.get("id") or by_focus.get(ct.get("focus"))
                for o in (t.get("offered_topic_options") or []):
                    if not isinstance(o, dict):
                        continue
                    oid = o.get("id") or by_focus.get(o.get("focus"))
                    if oid:
                        offered[oid] += 1
                ie = t["content"].get("internalEvaluation")
                ie = ie if isinstance(ie, dict) else {}
                turns.append({"qid": qid, "_score_here": ie.get("understandingScore")})
                qtext = t["content"].get("questionText")
                if qid and isinstance(qtext, str) and qtext:
                    texts[qid].append(qtext)
            except Exception:  # noqa: BLE001 — a malformed turn is skipped, not fatal
                continue
        # score of question i lives on turn i+1; keep only real pool questions
        rows = []
        for i, r in enumerate(turns):
            if not r["qid"]:
                continue
            rows.append({"qid": r["qid"],
                         "score": turns[i + 1]["_score_here"] if i + 1 < len(turns) else None})
        if rows:
            students.append(rows)
    return students, offered, texts


# ---- metrics ---------------------------------------------------------------

def per_question_stats(students):
    """Leave-one-out residual + discrimination per qid, from per-student score sets.

    residual(q) = mean over askers of (score_on_q - that student's mean over their OTHER
    questions). Negative = genuinely harder than its askers' baseline. Corrects for the fact
    that adaptive routing sends stronger students to harder questions.
    discrim(q)  = corr(score_on_q, student's leave-one-out ability). Noisy at 3 questions.
    """
    resid, ability_pairs = defaultdict(list), defaultdict(list)
    for rows in students:
        scored = [r for r in rows if isinstance(r["score"], (int, float))]
        if len(scored) < 2:
            continue
        total = sum(r["score"] for r in scored)
        own_mean = total / len(scored)
        for r in scored:
            loo_ability = (total - r["score"]) / (len(scored) - 1)
            resid[r["qid"]].append(r["score"] - own_mean)
            ability_pairs[r["qid"]].append((r["score"], loo_ability))
    out = {}
    for qid in resid:
        pairs = ability_pairs[qid]
        out[qid] = {
            "residual": round(st.mean(resid[qid]), 2) if resid[qid] else None,
            "discrim": _pearson([p[0] for p in pairs], [p[1] for p in pairs]),
        }
    return out


def _pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    dx = sum((a - mx) ** 2 for a in xs) ** .5
    dy = sum((b - my) ** 2 for b in ys) ** .5
    if not dx or not dy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (dx * dy)


def divergence(texts_for_q):
    """Mean pairwise cosine via the exact O(n) centroid identity. None if model unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        return None
    if not hasattr(divergence, "_model"):
        divergence._model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    emb = divergence._model.encode(texts_for_q, normalize_embeddings=True, show_progress_bar=False)
    n = len(emb)
    if n < 2:
        return None
    c = emb.mean(axis=0)
    return round((n * float(np.dot(c, c)) - 1) / (n - 1), 3)


def band(div):
    if div is None:
        return "gray"
    if div < DIV_GREEN:
        return "green"
    if div < DIV_YELLOW:
        return "yellow"
    return "red"


# ---- report ----------------------------------------------------------------

def build_report(assignment, students, offered, texts, qmeta, want_divergence):
    all_scores = [r["score"] for rows in students for r in rows if isinstance(r["score"], (int, float))]
    global_mean = st.mean(all_scores) if all_scores else 0.0

    by_q = defaultdict(list)
    for rows in students:
        for r in rows:
            by_q[r["qid"]].append(r)
    pq = per_question_stats(students)

    rows_out = []
    for qid in sorted(qmeta):
        rs = by_q.get(qid, [])
        sc = [r["score"] for r in rs if isinstance(r["score"], (int, float))]
        off = offered.get(qid, 0)
        div = divergence(texts[qid]) if (want_divergence and len(texts[qid]) >= MIN_N_FOR_DIVERGENCE) else None
        stats = pq.get(qid, {})
        row = {
            "qid": qid,
            "difficulty": qmeta[qid]["difficulty"],
            "dimension": qmeta[qid].get("dimension"),
            "asked": len(rs),
            "offered": off,
            "take_rate": round(len(rs) / off, 3) if off else None,
            "n_scored": len(sc),
            "mean_score": round(st.mean(sc), 2) if sc else None,
            "residual": stats.get("residual"),              # leave-one-out, routing-corrected
            "discrimination": round(stats["discrim"], 2) if stats.get("discrim") is not None else None,
            "pct_ceiling_5": round(100 * sum(1 for s in sc if s >= 5) / len(sc)) if sc else None,
            "pct_floor_2": round(100 * sum(1 for s in sc if s <= 2) / len(sc)) if sc else None,
            "divergence": div,
            "divergence_band": band(div),
        }
        row["recommendations"] = _recommend(row)
        rows_out.append(row)
    return {"assignment": assignment, "global_mean_score": round(global_mean, 2), "questions": rows_out}


def _recommend(row):
    recs = []
    if row["offered"] and row["take_rate"] is not None and row["take_rate"] < 0.05:
        recs.append(f"remove/rewrite — examiner almost never picks it ({row['asked']}/{row['offered']})")
    if row["n_scored"] and row["n_scored"] >= 8 and row["pct_ceiling_5"] == 0:
        recs.append("no headroom — nobody scored 5; question may lack depth")
    if row["divergence_band"] == "red":
        recs.append(f"template-like (div {row['divergence']}) — same question per student; consider replacing")
    if row["divergence_band"] == "yellow":
        recs.append(f"borderline divergence (div {row['divergence']}) — review")
    if row["residual"] is not None:
        if row["difficulty"] == "hard" and row["residual"] > 0.2:
            recs.append("labelled hard but easier than its askers' baseline — consider relabelling easier")
        if row["difficulty"] == "easy" and row["residual"] < -0.2:
            recs.append("labelled easy but harder than its askers' baseline — consider relabelling harder")
    if row["discrimination"] is not None and row["discrimination"] < 0 and row["n_scored"] >= 15:
        recs.append(f"negative discrimination ({row['discrimination']}) — review (noisy at 3 q/student)")
    return recs


def process_one(assignment, local_dir, want_divergence, json_path, write_gcs):
    """Compute and optionally print/dump/upload one assignment's report. Returns the report
    dict, or None if the assignment has no exams. The embedding model (used by divergence)
    is cached across calls, so looping many assignments loads it only once."""
    from datetime import datetime, timezone
    qmeta = _load_pool(assignment)
    students, offered, texts = collect(assignment, local_dir, qmeta)
    if not students:
        print(f"{assignment}: no exams found — skipped")
        return None
    n_asked = sum(len(rows) for rows in students)
    report = build_report(assignment, students, offered, texts, qmeta, want_divergence)
    report["computed_at"] = datetime.now(timezone.utc).isoformat()
    report["divergence_available"] = any(q["divergence"] is not None for q in report["questions"])

    print(f"\n{assignment}: {len(students)} students, {n_asked} questions asked, "
          f"global mean score {report['global_mean_score']}")
    print(f"{'id':5} {'diff':6} {'take%':>6} {'n':>4} {'mean':>5} {'resid':>6} {'ceil%':>6} {'div':>6} {'band':7} rec")
    print("-" * 100)
    for q in report["questions"]:
        tk = f"{q['take_rate']*100:.0f}" if q["take_rate"] is not None else "-"
        print("%-5s %-6s %6s %4s %5s %6s %6s %6s %-7s %s" % (
            q["qid"], q["difficulty"], tk, q["asked"],
            q["mean_score"] if q["mean_score"] is not None else "-",
            f"{q['residual']:+.2f}" if q["residual"] is not None else "-",
            q["pct_ceiling_5"] if q["pct_ceiling_5"] is not None else "-",
            q["divergence"] if q["divergence"] is not None else "-",
            q["divergence_band"],
            "; ".join(q["recommendations"]) or "ok"))

    if json_path:
        json.dump(report, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[written] {json_path}")
    if write_gcs:
        import os
        from github_stub import _gcs_client
        from config import ITEM_ANALYSIS_GCS_PATH
        bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
        if not bucket_name:
            sys.exit("GCS_SUBMISSIONS_BUCKET not set — cannot --write-gcs")
        path = ITEM_ANALYSIS_GCS_PATH.format(assignment=assignment)
        _gcs_client.bucket(bucket_name).blob(path).upload_from_string(
            json.dumps(report, ensure_ascii=False), content_type="application/json; charset=utf-8")
        print(f"[uploaded] gs://{bucket_name}/{path}  (the admin panel reads this)")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assignment", help="one assignment; omit with --all")
    ap.add_argument("--all", action="store_true",
                    help="process every real assignment (config.KNOWN_ASSIGNMENTS) — the nightly job")
    ap.add_argument("--local-dir", help="read blobs from a local dir instead of GCS")
    ap.add_argument("--no-divergence", action="store_true", help="skip the embedding metric")
    ap.add_argument("--json", help="also write the machine-readable report here (single-assignment only)")
    ap.add_argument("--write-gcs", action="store_true",
                    help="upload the report to gs://{GCS_SUBMISSIONS_BUCKET}/item_analysis/{assignment}.json "
                         "— this is the 'recompute' the admin item-analysis panel reads")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    if args.all:
        from config import KNOWN_ASSIGNMENTS
        failures = 0
        for a in KNOWN_ASSIGNMENTS:
            try:
                process_one(a, args.local_dir, not args.no_divergence, None, args.write_gcs)
            except Exception as exc:  # noqa: BLE001 — one bad assignment must not sink the rest
                failures += 1
                print(f"[ERROR] {a}: {exc}")
        print(f"\n[done] processed {len(KNOWN_ASSIGNMENTS)} assignments, {failures} failed")
        sys.exit(1 if failures else 0)

    if not args.assignment:
        sys.exit("give --assignment X, or --all")
    process_one(args.assignment, args.local_dir, not args.no_divergence, args.json, args.write_gcs)


if __name__ == "__main__":
    main()
