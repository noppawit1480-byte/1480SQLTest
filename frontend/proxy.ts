import { NextResponse, type NextRequest } from "next/server";

/**
 * Forwards /api/* to the FastAPI backend (same-origin for the browser, so the session cookie stays first-party).
 *
 * When PROXY_SECRET is set (production: frontend on Vercel, backend on a VPS) every forwarded request carries
 * that secret plus the learner's real IP. The backend only accepts requests with the secret and uses the IP for
 * per-client rate limiting — otherwise all learners would share the proxy's IP. Both values live only on the
 * server; nothing here is exposed to the browser.
 */
export function proxy(request: NextRequest) {
  const backend = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
  const target = new URL(backend + request.nextUrl.pathname + request.nextUrl.search);
  const headers = new Headers(request.headers);
  headers.delete("x-sqlab-proxy-secret");          // never trust a client-supplied value
  headers.delete("x-sqlab-client-ip");
  const secret = process.env.PROXY_SECRET;
  if (secret) {
    const fwd = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || request.headers.get("x-real-ip") || "";
    headers.set("x-sqlab-proxy-secret", secret);
    if (fwd) headers.set("x-sqlab-client-ip", fwd);
  }
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = { matcher: "/api/:path*" };
