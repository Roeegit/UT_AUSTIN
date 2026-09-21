import FileTabBar from "./FileTabBar";
import CodeViewer from "./CodeViewer";
import MarkdownViewer from "./MarkdownViewer";
import type { ExamAction } from "@/lib/types";
import type { SubmissionKind } from "@/lib/courseStrings";

// A transcribed maths submission is prose + LaTeX, not source code — Monaco shows it as raw
// `$$…$$` in mangled bidirectional text, which a student cannot read.
//
// Gated on submission_kind as well as the extension, deliberately: a code course's README.md
// is full of fenced code blocks that render worse line-by-line than they do in Monaco, and
// changing how a running course displays its files is not worth the incidental gain.
const useMarkdown = (filename: string, kind: SubmissionKind) =>
  kind === "solution" && filename.toLowerCase().endsWith(".md");

interface CodePanelProps {
  files: Record<string, string>;
  currentFile: string | null;
  action: ExamAction | null;
  scrollRevision: number;
  onFileSelect: (filename: string) => void;
  assignmentName: string;
  submissionKind: SubmissionKind;
}

export default function CodePanel({
  files,
  currentFile,
  action,
  scrollRevision,
  onFileSelect,
  assignmentName,
  submissionKind,
}: CodePanelProps) {
  const filenames = Object.keys(files);
  const code = currentFile ? (files[currentFile] ?? "") : "";
  const highlightCodeLine =
    action?.type === "JUMP_TO_LINE" && action.file === currentFile
      ? (action.codeLine ?? null)
      : null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Assignment label */}
      <div className="px-4 py-2 bg-gray-900 border-b border-gray-800 flex-shrink-0">
        <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">
          {assignmentName || "Assignment"}
        </span>
      </div>

      {/* File tabs */}
      <FileTabBar
        filenames={filenames}
        activeFile={currentFile}
        onSelect={onFileSelect}
      />

      {/* Code viewer */}
      {currentFile ? (
        <div className="flex-1 min-h-0 overflow-hidden" dir="ltr">
          {useMarkdown(currentFile, submissionKind) ? (
            <MarkdownViewer
              content={code}
              highlightCodeLine={highlightCodeLine}
              scrollRevision={scrollRevision}
            />
          ) : (
            <CodeViewer
              code={code}
              filename={currentFile}
              highlightCodeLine={highlightCodeLine}
              scrollRevision={scrollRevision}
            />
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          No files available.
        </div>
      )}
    </div>
  );
}
