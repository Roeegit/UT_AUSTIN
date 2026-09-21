import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(
  req: NextRequest,
  { params }: { params: { name: string } },
) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const name = decodeURIComponent(params.name);

  try {
    const body = await req.json();
    const res = await proxyToBackend(
      `/api/admin/assignment/${encodeURIComponent(name)}/send-reminder-emails`,
      { method: "POST", body, extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Send reminder emails proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
