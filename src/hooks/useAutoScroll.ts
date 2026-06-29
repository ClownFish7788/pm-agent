"use client";

/**
 * useAutoScroll — 自动滚动锁底 Hook。
 *
 * 行为：
 * - dependency 变化且 locked → 自动滚到底（smooth）
 * - 用户向上滚动（距底部 > 50px）→ 解锁
 * - 用户滚回底部 50px 内 → 重新锁上
 */

import { useEffect, useRef, useState, useCallback } from "react";

interface UseAutoScrollOptions {
  /** 触发自动滚动的依赖值（通常是 state） */
  dependency: unknown;
  /** 解锁阈值，距底部多少 px 内算"在底部" */
  threshold?: number;
}

export function useAutoScroll({
  dependency,
  threshold = 50,
}: UseAutoScrollOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [locked, setLocked] = useState(true);

  // dependency 变化 → locked 时自动滚到底
  useEffect(() => {
    if (!locked || !containerRef.current) return;
    containerRef.current.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [dependency, locked]);

  // 监听用户滚动
  const onScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (dist > threshold) {
      setLocked(false);
    } else {
      setLocked(true);
    }
  }, [threshold]);

  // 手动滚到底
  const scrollToBottom = useCallback(() => {
    setLocked(true);
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, []);

  return { containerRef, onScroll, locked, scrollToBottom };
}
