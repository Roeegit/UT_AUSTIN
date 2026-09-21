import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";

  try {
    const body = await req.json();
    const res = await proxyToBackend("/api/admin/resend-grade-emails", {
      method: "POST",
      body,
      extraHeaders: { "X-Admin-Key": adminKey },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Admin resend-grade-emails proxy error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
