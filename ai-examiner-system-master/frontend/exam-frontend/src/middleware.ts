import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const isQA = process.env.NEXT_PUBLIC_QA_MODE === "true";
  // ADMIN_ENABLED (no NEXT_PUBLIC prefix) — read from Cloud Run runtime env, not baked into the JS bundle
  const adminEnabled = process.env.ADMIN_ENABLED === "true";
  const { pathname, searchParams } = req.nextUrl;

  // Block all admin UI and API routes unless this deployment explicitly enables them.
  // The student-facing deployment sets NEXT_PUBLIC_ADMIN_ENABLED= (unset).
  if (!adminEnabled && (pathname.startsWith("/admin") || pathname.startsWith("/api/admin"))) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  if (isQA && pathname === "/exam") {
    // Only allow /exam when it comes from the /qa flow (has qa_assignment param)
    if (searchParams.get("assignment_name") !== "qa_assignment") {
      return NextResponse.redirect(new URL("/qa", req.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/exam", "/admin/:path*", "/api/admin/:path*"],
};
