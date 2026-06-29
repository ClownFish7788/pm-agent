/**
 * 分析会话 —— 模块级 singleton，SSE 生命周期独立于 React 组件。
 *
 * 设计目的：路由切换（Chat ↔ Report）不中断 SSE 连接。
 * React 组件通过 subscribe() 订阅状态变化。
 */

import type { AnalysisState } from "@/types/analysis";
import { analysisReducer, INITIAL_STATE } from "@/hooks/analysisReducer";
import { connectSSE } from "@/lib/sse";
import { reportStore } from "./reportStore";

// =============================================================================
// 内部状态
// =============================================================================

let _state: AnalysisState = { ...INITIAL_STATE };
let _controller: AbortController | null = null;
let _listeners = new Set<(s: AnalysisState) => void>();
let _isActive = false;
let _description = "";

const FIRST_RESPONSE_TIMEOUT_MS = 30_000; // 首次 POST 请求超时

// =============================================================================
// 公开 API
// =============================================================================

export const analysisSession = {
  /** 同步读取当前累积状态 */
  getState(): AnalysisState {
    return _state;
  },

  /** 当前分析的项目描述 */
  get description(): string {
    return _description;
  },

  /** 是否正在分析 */
  get isActive(): boolean {
    return _isActive;
  },

  /** 是否已完成 */
  get isCompleted(): boolean {
    return _state.phase === "completed";
  },

  /** 发起分析 */
  start(url: string, body: Record<string, unknown>): void {
    // 先清理上一个会话
    this.abort();

    // 保存描述
    _description = (body.description as string) || "";

    // 重置状态
    _state = { ...INITIAL_STATE };
    _isActive = true;
    _notifyAll();

    // 首次请求熔断：30s 内 POST 必须返回响应头
    const firstByteController = new AbortController();
    const firstByteTimer = setTimeout(
      () => firstByteController.abort(),
      FIRST_RESPONSE_TIMEOUT_MS
    );

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: firstByteController.signal,
    })
      .then((res) => {
        clearTimeout(firstByteTimer);
        if (!res.ok) {
          throw new Error(`后端返回 HTTP ${res.status}`);
        }

        // 首次响应成功 → SSE 流开始，不再限制时间
        // LLM 思考可能 30s+，后续事件流不限时
        _controller = new AbortController();
        return connectSSE(url, body, _controller.signal, (event) => {
          _state = analysisReducer(_state, event);
          _notifyAll();

          if (event.event_type === "final_report") {
            reportStore.set(event.data);
          }
        });
      })
      .catch((err: unknown) => {
        clearTimeout(firstByteTimer);
        if (err instanceof DOMException && err.name === "AbortError") {
          _state = {
            ..._state,
            errors: [
              ..._state.errors,
              `连接超时（${FIRST_RESPONSE_TIMEOUT_MS / 1000}s）：后端无响应，请确认 FastAPI 已启动`,
            ],
          };
        } else {
          const msg = err instanceof Error ? err.message : String(err);
          _state = { ..._state, errors: [..._state.errors, msg] };
        }
        _isActive = false;
        _notifyAll();
      });
  },

  /** 手动中止 */
  abort(): void {
    _controller?.abort();
    _controller = null;
    _isActive = false;
    _notifyAll();
  },

  /**
   * 订阅状态变化。
   * 订阅时立即回调一次（同步当前状态）。
   * 返回 unsubscribe 函数。
   */
  subscribe(listener: (s: AnalysisState) => void): () => void {
    _listeners.add(listener);
    listener(_state);
    return () => {
      _listeners.delete(listener);
    };
  },
};

// =============================================================================
// 内部
// =============================================================================

function _notifyAll(): void {
  const snapshot = [..._listeners];
  for (const fn of snapshot) {
    try {
      fn(_state);
    } catch {
      // listener 抛错不阻塞其他订阅者
    }
  }
}
