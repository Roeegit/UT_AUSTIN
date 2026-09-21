"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface MarkdownViewerProps {
  content: string;
  /** Exact source line to highlight, copied verbatim by the examiner. Null = no highlight. */
  highlightCodeLine: string | null;
  /** Increments when a new question action arrives — triggers auto-scroll. */
  scrollRevision: number;
}

/**
 * Renders a transcribed submission: Markdown prose with LaTeX maths, Hebrew and English
 * mixed. Monaco shows this as raw source — `$$4x+6=0$$` amid mangled bidirectional text —
 * which a student cannot read well enough to confirm it is their own work.
 *
 * Rendered one source line at a time, deliberately. The examiner anchors questions by quoting
 * a line verbatim (JUMP_TO_LINE → exact trimmed string match), so the line → screen mapping
 * has to survive rendering. One DOM node per source line keeps that contract and the visible
 * line numbers as they were. It suits the data too: the transcription prompt requires one
 * logical step per line, so a line is usually a self-contained unit.
 *
 * The exception is display maths, which is routinely written across several lines — `$$`,
 * then the matrix rows, then the close. Each of those lines alone is not valid maths, so
 * strict per-line rendering left `\begin{array}` on screen as raw text. Those blocks are
 * therefore grouped into one unit (segmentLines) and a quoted line inside one highlights the
 * whole block. Nothing else is grouped: a table or fenced block still renders line by line,
 * which is the right trade, because losing the ability to point at a line would break the
 * exam and an ugly table would not.
 */

// Unwrap the paragraph react-markdown wraps each line in — block margins would double the
// line height and break the alignment with the line-number gutter.
const COMPONENTS = {
  p: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
};

/** First line whose trimmed text matches — same rule as CodeViewer.findCodeLine. */
function findLineIndex(lines: string[], target: string | null): number | null {
  const t = (target ?? "").trim();
  if (!t) return null;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === t) return i;
  }
  return null;
}

/** One rendering unit: a single source line, or a `$$…$$` block spanning several. */
interface Segment {
  start: number;   // 0-based index of the first source line
  end: number;     // 0-based index of the last source line (== start for a plain line)
  text: string;
}

/** A line carrying an odd number of `$$` opens (or closes) a display block. */
const opensBlock = (line: string) => ((line.match(/\$\$/g) ?? []).length % 2) === 1;

/**
 * Put both `$$` fences on their own lines before handing a block to remark-math.
 *
 * remark-math's flow syntax treats anything on the same line as the opening `$$` as the
 * fence's META string and discards it, and only recognises a closing `$$` at the start of a
 * line. Transcriptions write `$$\left(\begin{array}…` and close with `…\right)$$`, so without
 * this the first matrix is silently dropped and the trailing `$$` ends up inside the maths —
 * KaTeX then fails with "Can't use function '$' in math mode" and renders the source in red.
 *
 * Carriage returns have to go first: the files are CRLF, so a closing line is `…$$\r` and no
 * end-of-string check on "$$" would ever match.
 */
function normaliseFences(text: string): string {
  let t = text.replace(/\r/g, "").trim();
  if (t.startsWith("$$") && !t.startsWith("$$\n")) t = "$$\n" + t.slice(2);
  if (t.endsWith("$$") && !t.endsWith("\n$$")) t = t.slice(0, -2) + "\n$$";
  return t;
}

/**
 * Group the source into rendering units.
 *
 * Display maths is routinely written across several lines — `$$` on its own, then the matrix
 * rows, then the close — and each line in isolation is not valid maths, so rendering strictly
 * per line leaves raw `\begin{array}` on screen. Only `$$` blocks are grouped; everything else
 * stays one line per unit, which is what keeps the examiner's line anchoring intact.
 */
function segmentLines(lines: string[]): Segment[] {
  // Cap the search so one stray `$$` cannot swallow the rest of the document.
  const MAX_BLOCK_LINES = 40;
  const segments: Segment[] = [];
  let i = 0;

  while (i < lines.length) {
    if (opensBlock(lines[i])) {
      let close = -1;
      for (let j = i + 1; j < Math.min(lines.length, i + MAX_BLOCK_LINES); j++) {
        if (opensBlock(lines[j])) { close = j; break; }
      }
      if (close !== -1) {
        segments.push({
          start: i,
          end: close,
          text: normaliseFences(lines.slice(i, close + 1).join("\n")),
        });
        i = close + 1;
        continue;
      }
      // Unbalanced — fall through and treat it as an ordinary line rather than
      // consuming everything after it.
    }
    segments.push({ start: i, end: i, text: lines[i] });
    i++;
  }
  return segments;
}

export default function MarkdownViewer({
  content,
  highlightCodeLine,
  scrollRevision,
}: MarkdownViewerProps) {
  // \r?\n: the submissions are CRLF, and a stray \r breaks both the maths fences and the
  // exact-string match the examiner's line anchoring relies on.
  const lines = content.split(/\r?\n/);
  const segments = segmentLines(lines);
  const highlightIndex = findLineIndex(lines, highlightCodeLine);
  const highlightRef = useRef<HTMLDivElement | null>(null);

  // Scroll the quoted line into view when a new question arrives, and on first mount so the
  // student lands on the line being asked about rather than at the top of the document.
  useEffect(() => {
    if (highlightIndex === null) return;
    highlightRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [scrollRevision, highlightIndex]);

  return (
    // h-full + min-h-0 so this scrolls itself rather than stretching its parent. The parent
    // must also be min-h-0/overflow-hidden or a flex item's min-height:auto defeats both.
    <div className="h-full min-h-0 w-full overflow-y-auto overflow-x-auto bg-gray-950 py-3 text-[15px] leading-relaxed">
      {segments.map((seg) => {
        // A quoted line inside a multi-line block highlights the whole block — the block is
        // the smallest thing that renders, so it is the smallest thing that can be pointed at.
        const isHighlight =
          highlightIndex !== null &&
          highlightIndex >= seg.start &&
          highlightIndex <= seg.end;
        return (
          <div
            key={seg.start}
            ref={isHighlight ? highlightRef : undefined}
            data-line={seg.start + 1}
            data-line-end={seg.end + 1}
            className={
              "flex gap-3 px-3 items-start " +
              (isHighlight ? "bg-yellow-400/15 border-l-2 border-yellow-400" : "")
            }
          >
            <span className="select-none text-gray-600 text-xs w-10 shrink-0 text-right tabular-nums pt-1">
              {seg.start + 1}
            </span>
            {/*
              Base direction and alignment do different jobs here, and both matter.

              dir="rtl" — the documents are Hebrew. A line like `א. $\begin{cases}…$ מעל $\R$.`
              only orders correctly under an RTL base: forcing LTR throws the leading letter
              and the trailing "מעל ℝ." to the wrong sides of the maths. Maths runs inside the
              line still render left-to-right via the Unicode bidi algorithm.

              text-align: left — alignment stays put so lines start against the number gutter
              instead of drifting to the far edge. dir="auto" was worse than either: it
              re-detects per line, so a Hebrew sentence right-aligns and the LaTeX line beneath
              it left-aligns, and a proof zig-zags across the panel.
            */}
            <div className="flex-1 min-w-0 text-gray-200 text-left markdown-line" dir="rtl">
              {seg.text.trim() ? (
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={COMPONENTS}
                >
                  {seg.text}
                </ReactMarkdown>
              ) : (
                <span>&nbsp;</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
