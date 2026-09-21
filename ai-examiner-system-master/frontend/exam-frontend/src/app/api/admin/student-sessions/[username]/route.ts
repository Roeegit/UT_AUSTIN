import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: { username: string } },
) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const username = decodeURIComponent(params.username);

  try {
    const res = await proxyToBackend(
      `/api/admin/student-sessions/${encodeURIComponent(username)}`,
      { method: "GET", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Student sessions proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
