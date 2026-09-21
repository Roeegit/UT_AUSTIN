import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    const { session_id, github_username, contact_name, contact_info, note } = await req.json();
    if (!contact_name || !contact_info) {
      return NextResponse.json(
        { error: "contact_name and contact_info are required" },
        { status: 400 }
      );
    }
    const backendRes = await proxyToBackend("/api/exam/complaint", {
      method: "POST",
      body: {
        session_id:      session_id      ?? null,
        github_username: github_username ?? null,
        contact_name,
        contact_info,
        note: note ?? "",
      },
    });
    let data: unknown;
    try {
      data = await backendRes.json();
    } catch {
      data = { error: `Backend error (HTTP ${backendRes.status})` };
    }
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error("Complaint submission error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
