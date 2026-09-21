import Timer from "./Timer";
import QuestionDisplay from "./QuestionDisplay";
import AnswerInput from "./AnswerInput";
import type { Language } from "@/lib/welcomeStrings";
import { UI_TIME_WARNING, t } from "@/lib/uiStrings";
import type { SubmissionKind } from "@/lib/courseStrings";

interface ExamPanelProps {
  questionText: string;
  questionNumber: number;
  timeRemaining: number;
  isSubmitting: boolean;
  onSubmit: (answer: string) => void;
  error: string | null;
  sessionId?: string;
  language?: Language;
  onComplaintSubmitted?: () => void;
  registerAnswerGetter?: (getter: () => string) => void;
  submissionKind: SubmissionKind;
}

export default function ExamPanel({
  questionText,
  questionNumber,
  timeRemaining,
  isSubmitting,
  onSubmit,
  error,
  sessionId,
  language = "he",
  onComplaintSubmitted,
  registerAnswerGetter,
  submissionKind,
}: ExamPanelProps) {
  return (
    <div className="flex flex-col h-full bg-gray-950 overflow-hidden">
      {/* Top bar: timer */}
      <div className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-800 flex-shrink-0">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {language === "en" ? "Knowledge Assessment" : "הערכת ידע"}
        </span>
        <Timer secondsRemaining={timeRemaining} />
      </div>

      {/* 3-minute warning banner */}
      {timeRemaining <= 180 && timeRemaining > 0 && (
        <div dir={language === "en" ? "ltr" : "rtl"} className="px-6 py-2 bg-yellow-950 border-b border-yellow-800 text-yellow-300 text-sm text-center">
          {t(UI_TIME_WARNING, language)}
        </div>
      )}

      {/* Question area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <QuestionDisplay
          questionText={questionText}
          questionNumber={questionNumber}
          language={language}
          enableMath={submissionKind === "solution"}
        />
        {error && (
          <div dir="auto" className="mt-4 p-3 rounded bg-red-950 border border-red-800 text-red-300 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Answer input — pinned to bottom */}
      <div className="flex-shrink-0 px-6 pt-0 pb-3">
        <AnswerInput isSubmitting={isSubmitting} onSubmit={onSubmit} questionNumber={questionNumber} language={language} sessionId={sessionId} onComplaintSubmitted={onComplaintSubmitted} registerAnswerGetter={registerAnswerGetter} />
      </div>
    </div>
  );
}
