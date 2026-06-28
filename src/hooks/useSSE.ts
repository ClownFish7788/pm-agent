"use client";

/**
 * useSSE — 消费 SSE 事件流的 React Hook。
 *
 * 设计决策：
 * - 手写 fetch + ReadableStream（不用 EventSource，因为需要 POST + 错误码区分）
 * - 零依赖（不引入 fetch-event-source 等第三方库）
 * - while + await reader.read() 不阻塞 UI 线程
 * - AbortController 在组件卸载时自动取消
 *
 * 用法：
 *   const { state, isConnected, error, abort } = useSSE("/api/analyze/stream", {
 *     description: "宠物社交App",
 *   });
 */

import { useEffect, useReducer, useRef, useCallback } from "react";
import type { SSEEvent } from "@/types/schemas";
import { analysisReducer, INITIAL_STATE } from "./analysisReducer";

// =============================================================================
// SSE 文本块 → 结构化事件
// =============================================================================

/**
 * 解析一个 SSE chunk（已按 \n\n 分割后的单块）。
 * 格式：event: <type>\ndata: <json>\n
 * 返回结构化 SSEEvent，解析失败返回 null（静默跳过，不中断流）。
 */
function parseSSEChunk(chunk: string): SSEEvent | null {
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
    // 仅保留 event_type 字段用于 discriminated union 收窄
    return { event_type: eventType, ...data } as SSEEvent;
  } catch {
    console.warn("[useSSE] JSON parse failed for chunk:", chunk.slice(0, 100));
    return null;
  }
}

// =============================================================================
// SSE 连接核心（独立函数，方便测试）
// =============================================================================

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

  // 2. HTTP 错误码 → 抛错（调用方 catch 处理）
  if (!response.ok) {
    let detail = "";
    try {
      const errBody = await response.text();
      detail = errBody.slice(0, 300);
    } catch { /* ignore */ }
    throw new Error(
      `SSE 连接失败 (HTTP ${response.status})${detail ? ": " + detail : ""}`
    );
  }

  // 3. 逐块读流
  const reader = response.body?.getReader();
  if (!reader) throw new Error("响应体为空，无法读取 SSE 流");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // 按 \n\n 分割事件块
      const chunks = buffer.split("\n\n");
      // 最后一块可能不完整，留在 buffer 下次拼接
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

// =============================================================================
// Hook
// =============================================================================

interface UseSSEOptions {
  /** 请求体（POST JSON） */
  body: Record<string, unknown>;
  /** 是否在挂载时自动连接（默认 true） */
  autoConnect?: boolean;
}

interface UseSSEReturn {
  state: typeof INITIAL_STATE;
  isConnected: boolean;
  error: string | null;
  /** 手动中止连接 */
  abort: () => void;
}

export function useSSE(url: string, options: UseSSEOptions): UseSSEReturn {
  const { body, autoConnect = true } = options;
  const [state, dispatch] = useReducer(analysisReducer, INITIAL_STATE);
  const [isConnected, setIsConnected] = useReducer(() => true, false);
  const [error, setError] = useReducer(
    (_prev: string | null, next: string | null) => next,
    null
  );
  const controllerRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!autoConnect) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    setError(null);

    connectSSE(url, body, controller.signal, (event) => {
      // 每个 SSE 事件触发一次 dispatch → reducer 做状态迁移
      dispatch(event);
      if (!controller.signal.aborted) {
        setIsConnected();
      }
    })
      .then(() => {
        // 流正常结束（done 事件后 reader 关闭）
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // 主动取消，不算错误
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, JSON.stringify(body), autoConnect]);

  return { state, isConnected, error, abort };
}
