import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: { name: string } },
) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const name = decodeURIComponent(params.name);

  try {
    const res = await proxyToBackend(
      `/api/admin/assignment/${encodeURIComponent(name)}/question-stats`,
      { method: "GET", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Question stats proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
