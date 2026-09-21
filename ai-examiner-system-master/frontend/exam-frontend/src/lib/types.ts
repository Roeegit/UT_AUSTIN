export interface ExamStartRequest {
  github_username: string;
  assignment_name: string;
}

export interface ExamStartResponse {
  session_id: string;
  assignment_name: string;
  question_text: string;
  question_number: number;
  action: string | null;
  action_file?: string | null;
  action_code_line?: string | null;
  files: Record<string, string>;
  exam_duration_seconds?: number;
}

export interface ExamAnswerResponse {
  finished: boolean;
  question_text?: string | null;
  question_number?: number | null;
  action?: string | null;
  action_file?: string | null;
  action_code_line?: string | null;
  message?: string | null;
  distress_ended?: boolean | null;
}

export interface ExamAction {
  type: string;
  file?: string | null;
  codeLine?: string | null;
}

export type ExamPhase =
  | "entry"               // ID input
  | "roster_lookup"       // waiting for roster API response
  | "assignment_confirm"  // confirm detected assignment, option to switch
  | "roster_confirm"      // showing code preview + confirm screen
  | "preferences"         // gender + language selection
  | "briefing"            // WelcomeScreen shown before exam starts
  | "loading"             // calling /api/auth/start
  | "active"              // exam in progress
  | "completed"           // exam finished normally
  | "distress"            // exam ended via distress signal
  | "error";              // unrecoverable error

export interface AssignmentOption {
  name:     string;
  label_he: string;
  label_en: string;
}

export interface TranscriptEntry {
  questionNumber: number;
  questionText: string;
  answerText: string;
}

export interface QAResults {
  isComplete: boolean;
  oralDefenseScore?: number;
  codeQualityScore?: number;
  finalGrade?: number | object;
  perQuestionScores?: Array<number | null>;
}
