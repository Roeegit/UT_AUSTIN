import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(
  _req: NextRequest,
  { params }: { params: { github_username: string } }
) {
  try {
    const backendRes = await proxyToBackend(
      `/api/exam/roster/${encodeURIComponent(params.github_username)}`,
      { method: "GET" }
    );
    let data: unknown;
    try {
      data = await backendRes.json();
    } catch {
      data = { error: `Backend error (HTTP ${backendRes.status})` };
    }
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Roster lookup error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
