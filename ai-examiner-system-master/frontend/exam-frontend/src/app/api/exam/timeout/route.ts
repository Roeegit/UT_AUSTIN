import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    const { session_id, partial_answer } = await req.json();
    if (!session_id) {
      return NextResponse.json({ error: "session_id is required" }, { status: 400 });
    }
    const backendRes = await proxyToBackend("/api/exam/timeout", {
      method: "POST",
      body: { session_id, ...(partial_answer ? { partial_answer } : {}) },
    });
    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Timeout error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
