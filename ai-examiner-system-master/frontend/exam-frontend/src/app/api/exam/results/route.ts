import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";
import type { QAResults } from "@/lib/types";

export async function GET(req: NextRequest) {
  if (process.env.NEXT_PUBLIC_QA_MODE !== "true") {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const githubUsername = req.nextUrl.searchParams.get("github_username");
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!githubUsername) {
    return NextResponse.json({ error: "github_username is required" }, { status: 400 });
  }

  try {
    const backendRes = await proxyToBackend(`/api/admin/results/${githubUsername}`, {
      method: "GET",
    });

    if (!backendRes.ok) {
      const text = await backendRes.text();
      return NextResponse.json(
        { error: `Backend error: ${text}` },
        { status: backendRes.status }
      );
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const raw: any = await backendRes.json();

    // Determine completeness: both grader_verdict and code_review must be non-null
    const gradedSession = Array.isArray(raw?.sessions)
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (sessionId ? raw.sessions.find((s: any) => s?.session_id === sessionId) : null)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ?? raw.sessions.find((s: any) => s?.status === "graded")
          ?? raw.sessions[raw.sessions.length - 1]
      : raw;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    function parseIfString(val: any) {
      if (typeof val === "string") { try { return JSON.parse(val); } catch { return null; } }
      return val ?? null;
    }

    const graderVerdict = parseIfString(gradedSession?.grader_verdict ?? raw?.grader_verdict);
    const codeReview    = parseIfString(gradedSession?.code_review    ?? raw?.code_review);
    const finalGradeRaw = parseIfString(gradedSession?.final_grade    ?? raw?.final_grade);

    const isComplete = gradedSession?.status === "graded" || (graderVerdict !== null && codeReview !== null);

    // Extract only safe, non-sensitive fields
    const result: QAResults = {
      isComplete,
    };

    if (isComplete) {
      if (typeof graderVerdict?.oralDefenseScore === "number") {
        result.oralDefenseScore = graderVerdict.oralDefenseScore;
      }
      if (typeof codeReview?.staticCodeQualityScore === "number") {
        result.codeQualityScore = codeReview.staticCodeQualityScore;
      }
      if (finalGradeRaw !== null) {
        result.finalGrade =
          typeof finalGradeRaw?.finalWeightedGrade !== "undefined"
            ? finalGradeRaw.finalWeightedGrade
            : finalGradeRaw;
      }
    }

    // Extract per-question understanding scores from transcript
    // Examiner turns have content.internalEvaluation.understandingScore
    const transcript: unknown[] = gradedSession?.transcript ?? raw?.transcript ?? [];
    if (Array.isArray(transcript) && transcript.length > 0) {
      // Each examiner turn's understandingScore evaluates the *preceding* student answer.
      // The first examiner turn (start_exam) has no prior answer — skip it.
      // Slice(1) gives one score slot per student answer, preserving nulls so indices
      // align with the frontend transcript entries even when questions are re-asked.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const examinerTurns = transcript.filter((turn: any) => turn?.role?.toLowerCase() === "examiner");
      const perQuestionScores: Array<number | null> = examinerTurns.slice(1).map((turn: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
        const score =
          turn?.content?.internalEvaluation?.understandingScore ??
          turn?.internalEvaluation?.understandingScore ??
          null;
        return typeof score === "number" ? score : null;
      });
      if (perQuestionScores.length > 0) {
        result.perQuestionScores = perQuestionScores;
      }
    }

    // NEVER return: internalReasoning, authorshipConfidence, authorshipAssessment,
    // signalBAssessment, professorReport, integrityFlag, promptInjectionFlag,
    // chosenTopicDifficulty, nextQuestionDifficulty
    return NextResponse.json(result);
  } catch (err) {
    console.error("Results fetch error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
