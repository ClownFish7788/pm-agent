/**
 * Chat 页 —— Agent 协作过程可视化。
 *
 * 当前使用 Mock SSE 端点测试。
 * 后续将 URL 改为 /api/analyze/stream 即可切换到真实后端。
 */

"use client";

import { useSearchParams } from "next/navigation";
import { useSSE } from "@/hooks/useSSE";
import AnalysisView from "@/components/AnalysisView";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const description =
    searchParams.get("description") ?? "宠物社交App（默认测试项目）";

  const { state, isConnected, error } = useSSE(
    "/api/analyze/stream",
    { body: { description } }
  );

  // 连接中
  if (!isConnected && !error && state.phase === "idle") {
    return (
      <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
        <div className="w-12 h-12 mb-4 rounded-full border-4 border-bamboo-200 border-t-accent animate-spin" />
        <p className="text-sm text-bamboo-500">正在连接分析服务...</p>
      </div>
    );
  }

  // 连接错误
  if (error && state.phase === "idle") {
    return (
      <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
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

  return <AnalysisView state={state} />;
}
