import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    const { session_id, answer_text } = await req.json();
    if (!session_id || !answer_text) {
      return NextResponse.json(
        { error: "session_id and answer_text are required" },
        { status: 400 }
      );
    }
    const backendRes = await proxyToBackend("/api/exam/answer", {
      method: "POST",
      body: { session_id, student_answer: answer_text },
    });
    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Answer error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
