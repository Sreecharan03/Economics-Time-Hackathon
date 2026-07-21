import { NextRequest } from "next/server";

// Same-origin proxy to gateway, so the browser never needs to reach gateway
// directly. This is server-side code (runs in the Next.js server, not the
// browser), so it can use the container-network address
// (http://gateway:8000 inside docker-compose) that isn't and shouldn't be
// publicly reachable -- only the frontend's own port needs to be exposed
// anywhere, cloud sandbox or otherwise. Also sidesteps CORS entirely, since
// the browser only ever talks to its own origin.
const GATEWAY_INTERNAL_URL = process.env.GATEWAY_INTERNAL_URL || "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const target = `${GATEWAY_INTERNAL_URL}/${path.join("/")}`;
  const init: RequestInit = { method: req.method, headers: { "Content-Type": "application/json" } };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const upstream = await fetch(target, init);

  // Passing upstream.body straight through (rather than buffering with
  // .json()/.text()) is what makes the SSE stream endpoint actually stream
  // instead of arriving as one chunk after gateway finishes everything.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(req, path);
}
