import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const assignment = req.nextUrl.searchParams.get("assignment") ?? "";

  if (!assignment) {
    return NextResponse.json({ error: "assignment query param required" }, { status: 400 });
  }

  try {
    const res = await proxyToBackend(
      `/api/admin/results/export.csv?assignment=${encodeURIComponent(assignment)}`,
      { method: "GET", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data, { status: res.status });
    }
    const csvText = await res.text();
    return new NextResponse(csvText, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${assignment}_results.csv"`,
      },
    });
  } catch (err) {
    console.error("Admin export proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
