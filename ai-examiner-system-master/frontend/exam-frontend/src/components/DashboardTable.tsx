"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css"; // Applies the math formatting

type QAPair = { question: string; answer: string };
type SessionData = {
  session_id: string;
  username: string;
  assignment: string;
  score: string | number;
  report: string;
  qa_pairs: QAPair[];
};

export default function DashboardTable() {
  const [data, setData] = useState<SessionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState<SessionData | null>(null);

  useEffect(() => {
    fetch("/api/dashboard/results")
      .then((res) => res.json())
      .then((json) => {
        if (Array.isArray(json)) {
          setData(json);
        } else {
          console.error("Backend returned a non-array response:", json);
          setData([]);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Dashboard fetch exception:", err);
        setData([]);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div className="p-8 text-gray-600 font-medium animate-pulse" dir="ltr">Loading dashboard...</div>;
  }

  // Separates block-level code boxes from inline code variables so sentences flow naturally
  const markdownComponents = {
    p: ({ node, ...props }: any) => <p className="mb-3 text-gray-800 leading-relaxed text-left" {...props} />,
    ul: ({ node, ...props }: any) => <ul className="list-disc pl-6 mb-4 space-y-2 text-gray-800 text-left" {...props} />,
    li: ({ node, ...props }: any) => <li className="pl-1" {...props} />,
    strong: ({ node, ...props }: any) => <strong className="font-bold text-gray-900" {...props} />,
    pre: ({ node, ...props }: any) => (
      <pre className="bg-gray-800 text-gray-50 p-4 rounded-lg mt-2 mb-4 overflow-x-auto text-sm font-mono text-left" dir="ltr" {...props} />
    ),
    code: ({ node, className, children, ...props }: any) => {
      // If it doesn't have a language class, treat it as inline code
      const isInline = !className;
      return isInline ? (
        <code className="bg-gray-100 text-blue-800 px-1.5 py-0.5 rounded text-sm font-mono break-words" dir="ltr" {...props}>
          {children}
        </code>
      ) : (
        <code className={className} dir="ltr" {...props}>
          {children}
        </code>
      );
    }
  };

  return (
    <div dir="ltr" className="font-sans">
      {/* Main Table */}
      <div className="overflow-hidden bg-white shadow-sm border border-gray-200 rounded-lg max-w-7xl mx-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-gray-700 text-sm tracking-wide">
              <th className="p-4 font-semibold text-left">Student Username</th>
              <th className="p-4 font-semibold text-left">Assignment</th>
              <th className="p-4 font-semibold text-left">Final Score</th>
              <th className="p-4 font-semibold text-left">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map((session) => (
              <tr key={session.session_id} className="hover:bg-blue-50/30 transition-colors">
                <td className="p-4 font-medium text-gray-900 text-left">{session.username}</td>
                <td className="p-4 text-gray-500 text-sm text-left">{session.assignment}</td>
                <td className="p-4 text-left">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    session.score === "N/A" ? "bg-gray-100 text-gray-800" :
                    Number(session.score) >= 85 ? "bg-green-100 text-green-800" :
                    Number(session.score) >= 60 ? "bg-yellow-100 text-yellow-800" :
                    "bg-red-100 text-red-800"
                  }`}>
                    {session.score !== "N/A" ? session.score : "Incomplete"}
                  </span>
                </td>
                <td className="p-4 text-left">
                  <button
                    onClick={() => setSelectedSession(session)}
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition shadow-sm"
                  >
                    View Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/60 backdrop-blur-sm p-4 sm:p-6" dir="ltr">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-y-auto flex flex-col relative text-left">
            <div className="p-6 border-b border-gray-200 flex justify-between items-start sticky top-0 bg-white/95 backdrop-blur z-10">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 text-left">Exam Details</h2>
                <div className="flex items-center gap-3 mt-2">
                  <p className="text-sm text-gray-500 text-left">Student: <span className="font-semibold text-gray-700">{selectedSession.username}</span></p>
                  <span className="text-gray-300">|</span>
                  <p className="text-sm text-gray-500 text-left">Score: <span className={`font-bold ${
                    selectedSession.score === "N/A" ? "text-gray-800" :
                    Number(selectedSession.score) >= 85 ? "text-green-600" :
                    Number(selectedSession.score) >= 60 ? "text-yellow-600" :
                    "text-red-600"
                  }`}>{selectedSession.score !== "N/A" ? selectedSession.score : "Incomplete"}</span></p>
                </div>
              </div>
              <button
                onClick={() => setSelectedSession(null)}
                className="text-gray-400 hover:bg-gray-100 hover:text-gray-800 rounded-full p-2 transition"
                aria-label="Close modal"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            
            <div className="p-6 sm:p-8 space-y-10">
              <section>
                <h3 className="text-lg font-bold text-gray-900 border-b border-gray-200 pb-2 mb-4 text-left">Professor Report</h3>
                <div className="bg-blue-50/50 p-6 rounded-lg border border-blue-100">
                  <ReactMarkdown 
                    remarkPlugins={[remarkMath]} 
                    rehypePlugins={[rehypeKatex]} 
                    components={markdownComponents}
                  >
                    {selectedSession.report || "No report generated."}
                  </ReactMarkdown>
                </div>
              </section>

              <section>
                <h3 className="text-lg font-bold text-gray-900 border-b border-gray-200 pb-2 mb-4 text-left">Session Transcript</h3>
                {selectedSession.qa_pairs && selectedSession.qa_pairs.length > 0 ? (
                  <div className="space-y-6 text-left">
                    {selectedSession.qa_pairs.map((qa, i) => (
                      <div key={i} className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                        <div className="mb-6">
                          <span className="inline-block bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded tracking-wider mb-3">
                            EXAMINER (QUESTION {i + 1})
                          </span>
                          <div className="text-gray-900 text-sm bg-gray-50 p-4 rounded border border-gray-100">
                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownComponents}>
                              {qa.question}
                            </ReactMarkdown>
                          </div>
                        </div>
                        <div>
                          <span className="inline-block bg-emerald-100 text-emerald-800 text-xs font-bold px-2 py-1 rounded tracking-wider mb-3">
                            STUDENT ANSWER
                          </span>
                          <div className="text-gray-800 text-sm pl-1">
                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownComponents}>
                              {qa.answer}
                            </ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-gray-50 text-gray-500 italic p-6 rounded text-center border border-gray-200">
                    No Q&A recorded for this session. (The student may have timed out or aborted).
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}