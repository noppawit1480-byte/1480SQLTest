import type { NextConfig } from "next";

// The browser only talks to Next.js; /api/* is forwarded to FastAPI by proxy.ts (read at runtime:
// BACKEND_URL, PROXY_SECRET) so the session cookie is first-party and no permissive CORS is needed.

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
