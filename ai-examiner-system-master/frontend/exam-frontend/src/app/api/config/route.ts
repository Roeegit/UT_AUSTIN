import { NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

// This handler reads nothing from the request, so Next would prerender it at build time and
// bake one course's config into the image that every course shares. It must be resolved per
// request, against whatever BACKEND_URL this deployment points at.
export const dynamic = "force-dynamic";

// Per-deployment UI config (identity mode, course title). Falls back to the GitHub
// wording so the entry screen still renders if the backend is unreachable.
export async function GET() {
  try {
    const res = await proxyToBackend("/api/config", { method: "GET" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Config proxy error:", err);
    return NextResponse.json({ identity_mode: "github_username" }, { status: 200 });
  }
}
