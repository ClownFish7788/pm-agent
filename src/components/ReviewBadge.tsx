"use client";

/**
 * 审核结果徽章 —— 通过/驳回/进行中。
 */

interface ReviewBadgeProps {
  verdict?: "passed" | "rejected" | null;
  overallScore?: number;
  credibility?: number;
  reason?: string;
  /** 审核进行中（还没有结论） */
  pending?: boolean;
}

export default function ReviewBadge({
  verdict,
  overallScore,
  credibility,
  reason,
  pending,
}: ReviewBadgeProps) {
  if (pending) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-bamboo-400">
        <span className="w-2 h-2 rounded-full bg-bamboo-300 animate-pulse" />
        审核中...
      </span>
    );
  }

  if (!verdict) return null;

  const isPassed = verdict === "passed";

  return (
    <div
      className={`inline-flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-lg ${
        isPassed ? "bg-accent-subtle text-accent" : "bg-red-50 text-red-600"
      }`}
    >
      <span className="font-medium">{isPassed ? "✅ 审核通过" : "❌ 审核驳回"}</span>
      {overallScore != null && (
        <span className="opacity-75">
          综合 {overallScore.toFixed(1)}
        </span>
      )}
      {credibility != null && (
        <span className="opacity-75">
          · 可信度 {credibility.toFixed(1)}
        </span>
      )}
      {!isPassed && reason && (
        <span className="block text-[11px] opacity-80 mt-0.5 w-full">
          原因：{reason}
        </span>
      )}
    </div>
  );
}
