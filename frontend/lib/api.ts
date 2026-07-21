import type { StreamEvent } from "./types";

export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";

export interface ReviewPayload {
  equipment_id_hint: string;
  raw_submittal_text: string;
  spec_section_hint?: string;
}

// EventSource can't send a POST body, so this reads the SSE stream by hand
// off fetch's ReadableStream -- the wire format is identical ("data: {...}\n\n"),
// just parsed manually instead of via the browser's built-in SSE client.
export async function streamReview(
  payload: ReviewPayload,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch(`${GATEWAY_URL}/review/submittal/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- keep statusText
    }
    throw new Error(`Gateway rejected the request (${resp.status}): ${detail}`);
  }
  if (!resp.body) {
    throw new Error("Gateway response had no body to stream");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (line.startsWith("data: ")) {
        onEvent(JSON.parse(line.slice("data: ".length)) as StreamEvent);
      }
    }
  }
}
