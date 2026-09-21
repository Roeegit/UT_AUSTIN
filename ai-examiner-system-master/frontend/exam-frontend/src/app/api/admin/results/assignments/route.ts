import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const username = req.nextUrl.searchParams.get("github_username");

  const qs = username ? `?github_username=${encodeURIComponent(username)}` : "";

  try {
    const res = await proxyToBackend(`/api/admin/results/assignments${qs}`, {
      method: "GET",
      extraHeaders: { "X-Admin-Key": adminKey },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Admin assignments proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
