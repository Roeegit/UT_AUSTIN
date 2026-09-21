import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  const adminKey = req.headers.get("X-Admin-Key") ?? "";
  const to = new URL(req.url).searchParams.get("to") ?? "shacharsl97@gmail.com";

  try {
    const res = await proxyToBackend(
      `/api/admin/send-test-reminder-email?to=${encodeURIComponent(to)}`,
      { method: "POST", extraHeaders: { "X-Admin-Key": adminKey } },
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Test reminder email error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
