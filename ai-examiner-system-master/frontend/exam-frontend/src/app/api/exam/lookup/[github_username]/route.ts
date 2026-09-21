import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: { github_username: string } }
) {
  try {
    const qs = req.nextUrl.searchParams.toString();
    const path = `/api/exam/lookup/${encodeURIComponent(params.github_username)}${qs ? `?${qs}` : ""}`;
    const backendRes = await proxyToBackend(path, { method: "GET" });
    let data: unknown;
    try {
      data = await backendRes.json();
    } catch {
      data = { error: `Backend error (HTTP ${backendRes.status})` };
    }
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Lookup error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
