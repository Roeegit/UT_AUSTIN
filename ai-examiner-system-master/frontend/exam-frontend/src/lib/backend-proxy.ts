import { GoogleAuth } from "google-auth-library";

let auth: GoogleAuth | null = null;

function getAuth(): GoogleAuth {
  if (auth) return auth;
  const saKeyJson = process.env.GOOGLE_SA_KEY_JSON;
  if (saKeyJson) {
    const credentials = JSON.parse(saKeyJson);
    auth = new GoogleAuth({ credentials });
  } else {
    auth = new GoogleAuth();
  }
  return auth;
}

function isLocalBackend(url: string): boolean {
  return url.startsWith("http://localhost") || url.startsWith("http://127.0.0.1");
}

export async function proxyToBackend(
  path: string,
  options: { method: "GET" | "POST"; body?: unknown; extraHeaders?: Record<string, string> }
): Promise<Response> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) throw new Error("BACKEND_URL not configured");

  const targetUrl = `${backendUrl}${path}`;

  // When pointing at localhost (gcloud proxy), no auth token needed — proxy handles it.
  if (isLocalBackend(backendUrl)) {
    return fetch(targetUrl, {
      method: options.method,
      headers: { "Content-Type": "application/json", ...(options.extraHeaders ?? {}) },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  }

  // Production: mint a Google ID token for Cloud Run IAM auth.
  const client = await getAuth().getIdTokenClient(backendUrl);
  const iamHeaders = await client.getRequestHeaders();

  return fetch(targetUrl, {
    method: options.method,
    headers: { ...iamHeaders, "Content-Type": "application/json", ...(options.extraHeaders ?? {}) },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
}
