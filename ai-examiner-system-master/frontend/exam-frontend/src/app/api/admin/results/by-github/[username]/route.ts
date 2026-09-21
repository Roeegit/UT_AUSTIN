import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest, { params }: { params: { username: string } }) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const assignment = req.nextUrl.searchParams.get("assignment") ?? "";

  if (!assignment) {
    return NextResponse.json({ error: "assignment query param required" }, { status: 400 });
  }

  try {
    const res = await proxyToBackend(
      `/api/admin/results/by-github/${encodeURIComponent(params.username)}?assignment=${encodeURIComponent(assignment)}`,
      { method: "GET", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Admin by-github proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
