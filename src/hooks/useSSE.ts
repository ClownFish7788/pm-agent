"use client";

/**
 * useSSE — 订阅分析会话的 React Hook。
 *
 * 重构后：不再管理 SSE 连接，只订阅 analysisSession 的状态。
 * 连接生命周期由 analysisSession.start()/abort() 管理。
 */

import { useState, useEffect, useCallback } from "react";
import { analysisSession } from "@/stores/analysisSession";
import type { AnalysisState } from "@/types/analysis";
import { INITIAL_STATE } from "./analysisReducer";

interface UseSSEReturn {
  state: AnalysisState;
  /** 是否有活跃的分析会话 */
  isConnected: boolean;
  error: string | null;
  abort: () => void;
}

export function useSSE(): UseSSEReturn {
  const [state, setState] = useState<AnalysisState>(
    () => analysisSession.getState()
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 订阅 analysisSession
    const unsubscribe = analysisSession.subscribe((nextState) => {
      setState(nextState);
      // 最新 error 作为 display error
      if (nextState.errors.length > 0) {
        setError(nextState.errors[nextState.errors.length - 1]);
      }
    });

    return unsubscribe;
  }, []);

  const abort = useCallback(() => {
    analysisSession.abort();
  }, []);

  return {
    state,
    isConnected: analysisSession.isActive,
    error,
    abort,
  };
}

/** 独立导出初始状态，供非 hook 场景使用 */
export { INITIAL_STATE };
