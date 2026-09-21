"use client";

import type { AssignmentOption } from "@/lib/types";

interface Props {
  detectedAssignment: AssignmentOption;
  availableAssignments: AssignmentOption[];
  isLoading: boolean;
  onConfirm: (assignmentName: string) => void;
  onBack: () => void;
}

export default function AssignmentConfirmScreen({
  detectedAssignment,
  availableAssignments,
  isLoading,
  onConfirm,
  onBack,
}: Props) {
  const others = availableAssignments.filter((a) => a.name !== detectedAssignment.name);

  return (
    <div className="h-screen flex flex-col items-center justify-center bg-gray-950 text-white px-4" dir="rtl">
      <div className="w-full max-w-md bg-gray-900 rounded-2xl p-8 shadow-xl flex flex-col gap-6">
        <h1 className="text-2xl font-bold text-center">אימות מטלה</h1>

        <div className="bg-gray-800 rounded-xl p-5 text-center">
          <p className="text-gray-400 text-sm mb-1">זיהינו עבורך</p>
          <p className="text-3xl font-bold text-blue-400">{detectedAssignment.label_he}</p>
          <p className="text-gray-500 text-xs mt-1">{detectedAssignment.label_en}</p>
        </div>

        <button
          onClick={() => onConfirm(detectedAssignment.name)}
          disabled={isLoading}
          className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 font-semibold text-lg transition-colors"
        >
          {isLoading ? "טוען…" : "כן, זאת המטלה שלי"}
        </button>

        {others.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-gray-400 text-sm text-center">(יש פה טעות. אני אמור להיבחן על: )</p>
            {others.map((a) => (
              <button
                key={a.name}
                onClick={() => onConfirm(a.name)}
                disabled={isLoading}
                className="w-full py-2 rounded-xl bg-gray-700 hover:bg-gray-600 disabled:opacity-50 font-medium transition-colors"
              >
                {a.label_he}
              </button>
            ))}
          </div>
        )}

        <button
          onClick={onBack}
          disabled={isLoading}
          className="text-gray-500 hover:text-gray-300 text-sm text-center transition-colors"
        >
          חזרה
        </button>
      </div>
    </div>
  );
}
