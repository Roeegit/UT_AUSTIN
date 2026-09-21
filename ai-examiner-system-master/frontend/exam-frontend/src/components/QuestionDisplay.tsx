import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

import type { Language } from "@/lib/welcomeStrings";
import { UI_QUESTION_LABEL, t } from "@/lib/uiStrings";

interface QuestionDisplayProps {
  questionText: string;
  questionNumber: number;
  language?: Language;
  /**
   * Parse `$…$` as maths. Off by default and gated per course rather than always on: an
   * Operating Systems question quotes shell variables (`$PATH`, `$1`, `$HOME`), which
   * remark-math would read as maths delimiters and mangle the question text.
   */
  enableMath?: boolean;
}

const markdownComponents: Components = {
  // Fenced code blocks — LTR monospace box
  pre({ children }) {
    return (
      <pre
        dir="ltr"
        className="my-3 p-3 rounded bg-gray-800 border border-gray-700 text-sm font-mono text-gray-100 overflow-x-auto text-left"
      >
        {children}
      </pre>
    );
  },
  code({ className, children, ...props }) {
    const isBlock = !props.ref && !className?.includes("inline");
    if (isBlock && !className) {
      // Inline code
      return (
        <code dir="ltr" className="px-1 py-0.5 rounded bg-gray-800 text-indigo-300 font-mono text-base">
          {children}
        </code>
      );
    }
    return <code className={className}>{children}</code>;
  },
  // Paragraphs — preserve RTL text direction
  p({ children }) {
    return <p dir="auto" className="mb-2 last:mb-0">{children}</p>;
  },
};

export default function QuestionDisplay({
  questionText, questionNumber, language = "he", enableMath = false,
}: QuestionDisplayProps) {
  const label = t(UI_QUESTION_LABEL, language).replace("{n}", String(questionNumber));
  const dir = language === "en" ? "ltr" : "rtl";
  const align = language === "en" ? "text-left" : "text-right";
  return (
    <div>
      <div className={`mb-3 flex ${language === "en" ? "justify-start" : "justify-end"}`}>
        <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-indigo-900 text-indigo-300 uppercase tracking-wider">
          {label}
        </span>
      </div>
      {/*
        question-math carries the bidi guard for KaTeX (see globals.css). It is set
        unconditionally — the rule only bites where maths was actually rendered, and tying
        it to `enableMath` would be one more switch to forget when a course turns maths on.
      */}
      <div
        dir={dir}
        className={`question-math text-gray-100 text-xl leading-relaxed select-none ${align}`}
        style={{ userSelect: "none", unicodeBidi: "plaintext" }}
      >
        <ReactMarkdown
          components={markdownComponents}
          remarkPlugins={enableMath ? [remarkMath] : []}
          rehypePlugins={enableMath ? [rehypeKatex] : []}
        >
          {questionText}
        </ReactMarkdown>
      </div>
    </div>
  );
}