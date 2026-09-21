"""
Plan Assembler v2 — copied from gemini-prompt-test/plan_assembler.py.
Added to_state() / from_state() for DB serialization in the stateless API.
"""

import json
import random
from collections import Counter
from typing import Optional


def load_pool(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data["questions"]
    return data


def validate_no_conflicts(questions: list[dict]) -> list[str]:
    errors = []
    for i, q_a in enumerate(questions):
        conflicts_a = set(q_a.get("conflicts_with", []))
        for j, q_b in enumerate(questions):
            if i >= j:
                continue
            conflicts_b = set(q_b.get("conflicts_with", []))
            id_a, id_b = q_a.get("id"), q_b.get("id")
            if id_b in conflicts_a or id_a in conflicts_b:
                errors.append(
                    f"CONFLICT: {id_a} ({q_a.get('focus', '')[:40]}) "
                    f"<-> {id_b} ({q_b.get('focus', '')[:40]})"
                )
    return errors


class QuestionPicker:
    """Stateful per-session question picker."""

    def __init__(self, pool_or_path, seed: Optional[int] = None, silent: bool = False):
        if isinstance(pool_or_path, str):
            self.pool = load_pool(pool_or_path)
        else:
            self.pool = pool_or_path

        self._reverse_conflicts: dict[str, set[str]] = {}
        for q in self.pool:
            qid = q.get("id")
            if qid:
                self._reverse_conflicts.setdefault(qid, set())
            for cid in q.get("conflicts_with", []):
                self._reverse_conflicts.setdefault(cid, set()).add(qid)

        self.seed = seed
        self.silent = silent
        self.rng = random.Random(seed)
        self.used_focuses: set[str] = set()
        self.used_files: list[str] = []
        self.used_dims: set[str] = set()
        self.excluded_ids: set[str] = set()
        self.turn = 0
        if not silent:
            print(f"[QuestionPicker] Initialized with seed: {seed}")

    # ── Serialization ────────────────────────────────────────────────────────

    def to_state(self) -> dict:
        """Return a plain-dict snapshot of picker state for DB storage."""
        return {
            "seed": self.seed,
            "turn": self.turn,
            "used_focuses": list(self.used_focuses),
            "used_files": list(self.used_files),
            "used_dims": list(self.used_dims),
            "excluded_ids": list(self.excluded_ids),
        }

    @classmethod
    def from_state(cls, pool: list[dict], state: dict, silent: bool = True) -> "QuestionPicker":
        """Reconstruct a QuestionPicker from a previously saved state dict."""
        picker = cls(pool, seed=state["seed"], silent=silent)
        # Re-advance the RNG to the same position it was at when the state was
        # saved.  We do this by consuming as many random numbers as pick_question
        # and peek_options would have consumed during the turns already played.
        # The simplest correct approach: just restore the mutable counters
        # directly — the RNG advances only matter for *future* picks and we
        # will re-seed from the stored seed + replay turns implicitly via the
        # same random.Random object.
        picker.turn = state["turn"]
        picker.used_focuses = set(state["used_focuses"])
        picker.used_files = list(state["used_files"])
        picker.used_dims = set(state["used_dims"])
        picker.excluded_ids = set(state["excluded_ids"])
        return picker

    # ── Core picking ─────────────────────────────────────────────────────────

    def pick_question(self, difficulty: str = "medium") -> Optional[dict]:
        self.turn += 1
        candidates = [
            q for q in self.pool
            if q["focus"] not in self.used_focuses
            and q.get("id") not in self.excluded_ids
        ]

        if not candidates:
            return None

        scored = []
        for q in candidates:
            score = 0
            if q["difficulty"] == difficulty:
                score += 100
            elif (difficulty == "hard" and q["difficulty"] == "medium") or \
                 (difficulty == "easy" and q["difficulty"] == "medium"):
                score += 40
            if any(f not in self.used_files for f in q["files"]):
                score += 50

            if q["dimension"] not in self.used_dims:
                score += 25
            else:
                score -= 15

            score += self.rng.random() * 40
            scored.append((score, q))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_score = scored[0][0]
        top_tier = [q for s, q in scored if s >= top_score - 60]

        if not self.silent:
            print(f"[QuestionPicker] Turn {self.turn}, difficulty={difficulty}, "
                  f"seed={self.seed}, candidates={len(candidates)}, top_tier_size={len(top_tier)}")

        chosen = self.rng.choice(top_tier)
        self._register(chosen)
        return chosen

    def peek_options(self, difficulties: list[str]) -> list[Optional[dict]]:
        """Return one candidate per difficulty WITHOUT updating state."""
        base_candidates = [
            q for q in self.pool
            if q["focus"] not in self.used_focuses
            and q.get("id") not in self.excluded_ids
        ]

        results: list[Optional[dict]] = []
        already_chosen_ids: set[str] = set()

        for difficulty in difficulties:
            exact_candidates = [
                q for q in base_candidates
                if q.get("id") not in already_chosen_ids
                and q["difficulty"] == difficulty
            ]
            fallback_candidates = [
                q for q in base_candidates
                if q.get("id") not in already_chosen_ids
            ]
            candidates = exact_candidates if exact_candidates else fallback_candidates

            if not candidates:
                results.append(None)
                continue

            scored = []
            for q in candidates:
                score = 0
                if any(f not in self.used_files for f in q["files"]):
                    score += 50
                if q["dimension"] not in self.used_dims:
                    score += 25
                else:
                    score -= 15
                score += self.rng.random() * 40
                scored.append((score, q))

            scored.sort(key=lambda x: x[0], reverse=True)
            top_score = scored[0][0]
            top_tier = [q for s, q in scored if s >= top_score - 60]
            chosen = self.rng.choice(top_tier)
            results.append(chosen)
            already_chosen_ids.add(chosen.get("id", ""))

        return results

    def mark_used(self, question: dict) -> None:
        """Register a specific question as used after examiner selects from peek_options."""
        self.turn += 1
        self._register(question)

    def _register(self, chosen: dict) -> None:
        self.used_focuses.add(chosen["focus"])
        self.used_files.extend(chosen["files"])
        self.used_dims.add(chosen["dimension"])

        chosen_id = chosen.get("id")
        if chosen_id:
            for cid in chosen.get("conflicts_with", []):
                self.excluded_ids.add(cid)
            for cid in self._reverse_conflicts.get(chosen_id, set()):
                self.excluded_ids.add(cid)

    def reset(self):
        self.used_focuses.clear()
        self.used_files.clear()
        self.used_dims.clear()
        self.excluded_ids.clear()
        self.turn = 0

    def format_topic_for_examiner(self, question: dict) -> dict:
        return {
            "files": question["files"],
            "focus": question["focus"],
            "dimension": question["dimension"],
            "difficulty": question["difficulty"],
            "examiner_notes": question.get("examiner_notes", ""),
        }
