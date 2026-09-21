"use client";

import { useRef, useEffect } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor } from "monaco-editor";

interface CodeViewerProps {
  code: string;
  filename: string;
  /** Exact code line to highlight (copied verbatim from the file by the AI). Null = no highlight. */
  highlightCodeLine: string | null;
  /** Increments each time a new question action arrives — triggers auto-scroll */
  scrollRevision: number;
}

/** Find the 1-based line number of the first line that matches codeLine (trimmed). */
function findCodeLine(code: string, codeLine: string): number | null {
  const target = codeLine.trim();
  if (!target) return null;
  const lines = code.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === target) return i + 1; // 1-based
  }
  return null;
}

function inferLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    c: "c", h: "c", cpp: "cpp", hpp: "cpp",
    py: "python", java: "java", js: "javascript",
    ts: "typescript", rs: "rust", go: "go",
    sh: "shell", bash: "shell",
    md: "markdown", txt: "plaintext",
  };
  if (filename.toLowerCase() === "makefile") return "makefile";
  return map[ext] || "plaintext";
}

export default function CodeViewer({ code, filename, highlightCodeLine, scrollRevision }: CodeViewerProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<editor.IEditorDecorationsCollection | null>(null);
  const highlightLine = highlightCodeLine ? findCodeLine(code, highlightCodeLine) : null;
  const highlightLineRef = useRef<number | null>(null);
  highlightLineRef.current = highlightLine;
  const scrollRevisionRef = useRef<number>(scrollRevision);
  scrollRevisionRef.current = scrollRevision;

  /** Apply yellow-line decoration without scrolling (e.g. when switching back to a file). */
  function applyDecoration(ed: editor.IStandaloneCodeEditor, line: number | null) {
    if (decorationsRef.current) {
      decorationsRef.current.clear();
      decorationsRef.current = null;
    }
    if (line && line > 0) {
      decorationsRef.current = ed.createDecorationsCollection([
        {
          range: { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: 1 },
          options: { isWholeLine: true, className: "highlight-line", glyphMarginClassName: "highlight-glyph" },
        },
      ]);
    }
  }

  function handleEditorMount(mountedEditor: editor.IStandaloneCodeEditor, monaco: Monaco) {
    editorRef.current = mountedEditor;
    monaco.editor.defineTheme("exam-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
      colors: { "editor.background": "#030712" },
    });
    monaco.editor.setTheme("exam-dark");
    // Apply decoration immediately for the first question.
    // Scroll is deferred until Monaco fires onDidLayoutChange (i.e. it knows its dimensions),
    // otherwise revealLineInCenter has no effect and the view stays at the top.
    const line = highlightLineRef.current;
    applyDecoration(mountedEditor, line);
    if (line && line > 0) {
      const disposable = mountedEditor.onDidLayoutChange(() => {
        disposable.dispose();
        editorRef.current?.revealLineInCenter(line);
      });
    }
  }

  // Re-apply decoration whenever highlighted line or file content changes (no scroll).
  useEffect(() => {
    const ed = editorRef.current;
    if (!ed) return;
    applyDecoration(ed, highlightLine);
  }, [highlightLine, code]);

  // Scroll to center only when a new question action arrives (scrollRevision increments).
  useEffect(() => {
    const ed = editorRef.current;
    const line = highlightLineRef.current;
    if (!ed || !line || line <= 0) return;
    ed.revealLineInCenter(line);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollRevision]);

  return (
    <Editor
      height="100%"
      language={inferLanguage(filename)}
      value={code}
      theme="exam-dark"
      onMount={handleEditorMount}
      options={{
        readOnly: true,
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        wordWrap: "on",
        domReadOnly: true,
        contextmenu: false,
        folding: false,
        glyphMargin: true,
      }}
    />
  );
}
