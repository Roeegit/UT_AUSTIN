import { NextResponse } from "next/server";
import { proxyToBackend } from "../../../../lib/backend-proxy";

// Prevent Next.js from caching this API route
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  try {
    const response = await proxyToBackend("/api/dashboard/results", { 
      method: "GET",
      extraHeaders: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
      }
    });

    if (!response.ok) {
      throw new Error(`Backend returned status ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "no-store, max-age=0",
      },
    });
  } catch (error) {
    console.error("Dashboard fetch error:", error);
    return NextResponse.json({ error: "Failed to fetch results" }, { status: 500 });
  }
}