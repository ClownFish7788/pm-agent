/**
 * SSE 连接与解析 —— 从 useSSE 中提取的底层函数。
 *
 * 独立于 React，可被 analysisSession 直接调用。
 */

import type { SSEEvent } from "@/types/schemas";

/**
 * 解析一个 SSE 文本块（按 \n\n 分割后的单块）。
 * 格式：event: <type>\ndata: <json>
 */
export function parseSSEChunk(chunk: string): SSEEvent | null {
  const lines = chunk.split("\n");
  let eventType = "";
  let dataStr = "";

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataStr = line.slice(6);
    }
  }

  if (!eventType || !dataStr) return null;

  try {
    const data = JSON.parse(dataStr);
    return { event_type: eventType, ...data } as SSEEvent;
  } catch {
    console.warn("[SSE] JSON parse failed:", dataStr.slice(0, 80));
    return null;
  }
}

/**
 * 建立 SSE 连接，逐个事件回调 onEvent。
 *
 * @param url     请求 URL
 * @param body    POST JSON body
 * @param signal  AbortController.signal（用于取消）
 * @param onEvent 每个解析成功的 SSEEvent 回调
 * @throws HTTP 错误（非 2xx）或网络错误
 */
export async function connectSSE(
  url: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  // 1. POST 请求
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  // 2. HTTP 错误码
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.text()).slice(0, 300);
    } catch { /* ignore */ }
    throw new Error(
      `SSE 连接失败 (HTTP ${response.status})${detail ? ": " + detail : ""}`
    );
  }

  // 3. 逐块读流
  const reader = response.body?.getReader();
  if (!reader) throw new Error("响应体为空");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const trimmed = chunk.trim();
        if (!trimmed) continue;
        const event = parseSSEChunk(trimmed);
        if (event) onEvent(event);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
