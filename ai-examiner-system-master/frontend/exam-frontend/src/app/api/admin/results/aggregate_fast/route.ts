import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

// Postgres-backed aggregate (result_summary table). Same shape as /aggregate but no blob
// download. See docs/MULTI_COURSE_MIGRATION.md §4.10.
export async function GET(req: NextRequest) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const assignment = req.nextUrl.searchParams.get("assignment") ?? "";

  if (!assignment) {
    return NextResponse.json({ error: "assignment query param required" }, { status: 400 });
  }

  try {
    const res = await proxyToBackend(
      `/api/admin/results/aggregate_fast?assignment=${encodeURIComponent(assignment)}`,
      { method: "GET", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Admin aggregate_fast proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
