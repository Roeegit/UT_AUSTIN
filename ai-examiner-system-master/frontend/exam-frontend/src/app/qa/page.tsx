"use client";

import { notFound, useRouter } from "next/navigation";
import { useState } from "react";

if (process.env.NEXT_PUBLIC_QA_MODE !== "true") {
  // This component renders 404 when QA mode is off
}

const STUDENTS = [
  {
    id: "student-a",
    label: "עבודה כתובה היטב",
    badgeColor: "bg-green-800 text-green-200",
  },
  {
    id: "student-b",
    label: "עבודה בינונית",
    badgeColor: "bg-yellow-800 text-yellow-200",
  },
  {
    id: "student-c",
    label: "עבודה שמועתקת מ-GPT",
    badgeColor: "bg-red-900 text-red-200",
  },
];


export default function QAPage() {
  const router = useRouter();

  if (process.env.NEXT_PUBLIC_QA_MODE !== "true") {
    notFound();
  }

  const [selectedStudent, setSelectedStudent] = useState<string | null>(null);
  const [selectedPersona, setSelectedPersona] = useState<string>("");

  function handleStart() {
    if (!selectedStudent || !selectedPersona) return;
    const params = new URLSearchParams({
      student_id: selectedStudent,
      assignment_name: "qa_assignment",
      github_username: selectedStudent,
      persona: selectedPersona,
    });
    router.push(`/exam?${params.toString()}`);
  }

  return (
    <div
      className="min-h-screen bg-gray-950 text-white py-10 px-4"
      dir="rtl"
    >
      <div className="max-w-3xl mx-auto space-y-10">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-white">
            בדיקת QA — מערכת בחינה בעל פה
          </h1>
          <p className="text-gray-400">
            בחר פרופיל סטודנט ופרסונה, לאחר מכן לחץ "התחל בחינה" כדי לדמות ריאיון.
          </p>
        </div>

        {/* Student cards */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4">
            פרופיל סטודנט
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {STUDENTS.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedStudent(s.id)}
                className={`rounded-xl border-2 p-5 text-right transition-all ${
                  selectedStudent === s.id
                    ? "border-indigo-500 bg-indigo-950"
                    : "border-gray-700 bg-gray-900 hover:border-gray-500"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full ${s.badgeColor}`}
                  >
                    {s.id}
                  </span>
                  {selectedStudent === s.id && (
                    <span className="w-4 h-4 rounded-full bg-indigo-500 flex-shrink-0" />
                  )}
                </div>
                <h3 className="text-base font-bold text-white">
                  {s.label}
                </h3>
              </button>
            ))}
          </div>
        </section>

        {/* Persona selector */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4">
            פרסונת נבחן (לתיעוד בלבד)
          </h2>
          <input
            type="text"
            value={selectedPersona}
            onChange={(e) => setSelectedPersona(e.target.value)}
            placeholder="תאר את הפרסונה שאתה מגלם..."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-right"
          />
        </section>

        {/* Start button */}
        <div className="flex justify-center">
          <button
            onClick={handleStart}
            disabled={!selectedStudent || !selectedPersona}
            className="px-10 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg text-base transition-colors"
          >
            התחל בחינה
          </button>
        </div>
      </div>
    </div>
  );
}
