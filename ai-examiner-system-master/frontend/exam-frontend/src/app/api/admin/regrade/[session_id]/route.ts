import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest, { params }: { params: { session_id: string } }) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";

  try {
    const res = await proxyToBackend(
      `/api/admin/regrade/${encodeURIComponent(params.session_id)}`,
      { method: "POST", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Admin regrade proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
