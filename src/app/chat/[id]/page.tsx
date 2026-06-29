/**
 * Chat 页 —— Agent 协作过程可视化。
 *
 * 使用 analysisSession（模块级 singleton），SSE 连接在路由切换后继续存活。
 * useAutoScroll 实现自动锁底滚动。
 */

"use client";

import { useParams } from "next/navigation";
import { useSSE } from "@/hooks/useSSE";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { analysisSession } from "@/stores/analysisSession";
import AnalysisView from "@/components/AnalysisView";

export default function ChatPage() {
  const params = useParams();
  const analysisId = (params.id as string) ?? "unknown";
  const { state, isConnected, error, abort } = useSSE();
  const { containerRef, onScroll, locked, scrollToBottom } = useAutoScroll({
    dependency: state,
  });

  const description = analysisSession.description || "分析中...";

  // 连接中（session 还没启动）
  if (!isConnected && state.phase === "idle" && state.plan === null) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-8 py-12">
        <div className="w-12 h-12 mb-4 rounded-full border-4 border-bamboo-200 border-t-accent animate-spin" />
        <p className="text-sm text-bamboo-500">正在连接分析服务...</p>
        <p className="text-xs text-bamboo-400 mt-1 max-w-sm text-center truncate">
          {description}
        </p>
      </div>
    );
  }

  // 连接错误且无数据
  if (error && state.phase === "idle" && state.plan === null) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-8 py-12">
        <div className="w-14 h-14 mb-4 rounded-2xl bg-red-50 flex items-center justify-center">
          <svg width="24" height="24" viewBox="0 0 18 18" fill="none" stroke="#D14343" strokeWidth="1.5" strokeLinecap="round">
            <circle cx="9" cy="9" r="7.2" />
            <line x1="5.5" y1="5.5" x2="12.5" y2="12.5" />
            <line x1="12.5" y1="5.5" x2="5.5" y2="12.5" />
          </svg>
        </div>
        <h2 className="text-sm font-medium text-bamboo-700 mb-1">连接失败</h2>
        <p className="text-xs text-bamboo-500 max-w-sm text-center">{error}</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      className="h-full overflow-y-auto"
    >
      <AnalysisView state={state} isConnected={isConnected} analysisId={analysisId} />

      {/* 解锁提示：用户向上翻看时显示浮动的"回到底部"按钮 */}
      {!locked && (
        <button
          onClick={scrollToBottom}
          className="
            fixed bottom-6 right-8 z-50
            w-10 h-10 rounded-full
            bg-white border border-bamboo-200
            shadow-md
            flex items-center justify-center
            hover:bg-bamboo-50
            transition-all
            cursor-pointer
          "
          aria-label="回到底部"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#5B7B68" strokeWidth="2" strokeLinecap="round">
            <polyline points="4,6 8,10 12,6" />
          </svg>
        </button>
      )}
    </div>
  );
}
