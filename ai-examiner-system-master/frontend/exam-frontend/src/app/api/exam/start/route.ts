import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    const { github_username, assignment_name, persona, language } = await req.json();
    if (!github_username) {
      return NextResponse.json({ error: "github_username is required" }, { status: 400 });
    }
    const backendRes = await proxyToBackend("/api/auth/start", {
      method: "POST",
      body: { github_username, assignment_name: assignment_name ?? null, persona, language },
    });
    let data: unknown;
    try {
      data = await backendRes.json();
    } catch {
      data = { error: `Backend error (HTTP ${backendRes.status})` };
    }
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Start exam error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
