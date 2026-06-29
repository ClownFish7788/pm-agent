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
    if (_controller) {
      _controller.abort();
    }

    // 保存描述
    _description = (body.description as string) || "";

    // 重置
    _state = { ...INITIAL_STATE };
    _isActive = true;
    _notifyAll();

    _controller = new AbortController();

    connectSSE(url, body, _controller.signal, (event) => {
      _state = analysisReducer(_state, event);
      _notifyAll();

      // finalReport 产出 → 写入内存 + sessionStorage
      if (event.event_type === "final_report") {
        reportStore.set(event.data);
      }
    })
      .catch((err: unknown) => {
        if (_controller?.signal.aborted) return;
        const msg = err instanceof Error ? err.message : String(err);
        _state = {
          ..._state,
          errors: [..._state.errors, msg],
        };
        _notifyAll();
      })
      .finally(() => {
        _isActive = false;
        if (!_controller?.signal.aborted) {
          _notifyAll();
        }
        _controller = null;
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
    listener(_state); // 立即同步
    return () => {
      _listeners.delete(listener);
    };
  },
};

// =============================================================================
// 内部
// =============================================================================

function _notifyAll(): void {
  // 快照迭代：防止 listener 里 unsubscribe 导致 Set 变异
  const snapshot = [..._listeners];
  for (const fn of snapshot) {
    try {
      fn(_state);
    } catch {
      // listener 抛错不阻塞其他订阅者
    }
  }
}
