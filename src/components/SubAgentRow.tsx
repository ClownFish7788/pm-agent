"use client";

/**
 * 单个 SearchAgent 的活动行 —— 展示完整的搜索→分析→审核链路。
 * 支持多轮重试（rounds[]），每一轮独立展示，驳回前后的搜索词可对照。
 */

import type { SubAgentSlot } from "@/types/analysis";
import ReviewBadge from "./ReviewBadge";

interface SubAgentRowProps {
  slot: SubAgentSlot;
}

export default function SubAgentRow({ slot }: SubAgentRowProps) {
  const { rounds } = slot;
  const isMultiRound = rounds.length > 1;

  return (
    <div className="ml-2 pl-4 border-l-2 border-bamboo-200">
      {/* ---- 调度头 ---- */}
      <div className="flex items-center gap-2 mb-2 -ml-[22px]">
        <span
          className={`w-2.5 h-2.5 rounded-full shrink-0 border-2 border-white ${
            slot.status === "passed"
              ? "bg-accent"
              : slot.status === "rejected"
                ? "bg-red-400"
                : slot.status === "searching"
                  ? "bg-amber-400 animate-pulse"
                  : slot.status === "analyzing"
                    ? "bg-blue-400 animate-pulse"
                    : "bg-bamboo-300"
          }`}
        />
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#5B7B68" strokeWidth="1.5" strokeLinecap="round">
          <path d="M7 2v2M11 4l-2 2M7 12v-2M3 10l2-2" />
          <circle cx="7" cy="7" r="1.5" />
          <path d="M3 2l4 4M11 12l-4-4" />
        </svg>
        <span className="text-sm font-medium text-bamboo-700">
          SearchAgent {slot.id}
        </span>
        {isMultiRound && (
          <span className="text-[11px] text-bamboo-400">
            ({rounds.length} 轮)
          </span>
        )}
      </div>

      {/* ---- 各轮次 ---- */}
      {rounds.map((round, ri) => {
        const isRetry = ri > 0;
        const isCurrentRound = ri === rounds.length - 1;

        return (
          <div
            key={round.round}
            className={`mb-3 ${isRetry ? "mt-1" : ""}`}
          >
            {/* 重试分隔线 */}
            {isRetry && (
              <div className="flex items-center gap-2 mb-2 -ml-4">
                <div className="flex-1 h-px bg-bamboo-200" />
                <span className="text-[11px] font-medium text-amber-600 flex items-center gap-1 shrink-0">
                  🔄 第 {round.round} 轮 · 重新调度
                </span>
                <div className="w-6 h-px bg-bamboo-200" />
              </div>
            )}

            {/* 搜索词 */}
            <div className="flex items-start gap-2 mb-1.5">
              <span className="text-[11px] text-bamboo-400 shrink-0 mt-0.5">
                {isRetry ? "改进搜索词" : "📤 搜索词"}
              </span>
              <code className="text-[12px] text-bamboo-700 bg-bamboo-50 px-2 py-0.5 rounded font-mono leading-relaxed">
                {round.searchQuery}
              </code>
            </div>

            {/* 搜索完成 */}
            {round.resultCount != null && (
              <div className="flex items-center gap-2 text-xs text-bamboo-500 mb-1 ml-9">
                <span className="text-bamboo-300">└→</span>
                搜索完成（{round.resultCount} 条结果）
              </div>
            )}

            {/* LLM 分析完成 */}
            {round.findingsCount != null && (
              <div className="flex items-start gap-2 text-xs text-bamboo-500 mb-1 ml-9">
                <span className="text-bamboo-300 mt-0.5">└→</span>
                <span>
                  LLM 分析完成（{round.findingsCount} 条发现）
                  {round.reportSummary && (
                    <span className="block text-[11px] text-bamboo-400 mt-0.5 line-clamp-2">
                      {round.reportSummary}
                    </span>
                  )}
                </span>
              </div>
            )}

            {/* 审核结论 */}
            {round.review && (
              <div className="ml-9 mt-1">
                <ReviewBadge
                  verdict={round.review.verdict}
                  overallScore={round.review.overallScore}
                  credibility={round.review.credibility}
                  reason={round.review.verdict === "rejected" ? round.review.reason : undefined}
                />
              </div>
            )}

            {/* 当前轮正在审核中 */}
            {isCurrentRound && !round.review && round.resultCount != null && (
              <div className="ml-9 mt-1">
                <ReviewBadge pending />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
