"use client";

/**
 * 交叉洞察卡片 —— 默认折叠，点击展开。
 * 展示跨部门关联分析，包含涉及的部门标签和置信度。
 */

import { useState } from "react";
import type { CrossInsight } from "@/types/schemas";
import { DEPARTMENT_LABELS } from "@/types/history";

interface CrossInsightCardProps {
  insight: CrossInsight;
}

export default function CrossInsightCard({ insight }: CrossInsightCardProps) {
  const [expanded, setExpanded] = useState(false);

  const confPct = Math.round(insight.confidence * 100);
  const confColor =
    insight.confidence >= 0.7
      ? "text-accent bg-accent-subtle"
      : insight.confidence >= 0.5
        ? "text-amber-600 bg-amber-50"
        : "text-red-600 bg-red-50";

  return (
    <button
      onClick={() => setExpanded(!expanded)}
      className="w-full text-left rounded-xl border border-bamboo-200 bg-white hover:border-bamboo-300 hover:shadow-sm transition-all cursor-pointer overflow-hidden"
    >
      <div className="p-4">
        {/* 标题行 */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-bamboo-800 leading-snug">
              {insight.title}
            </h4>
            {/* 涉及部门标签 */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {insight.involved_dimensions.map((dim) => (
                <span
                  key={dim}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-bamboo-100 text-bamboo-600 font-medium"
                >
                  {DEPARTMENT_LABELS[dim as keyof typeof DEPARTMENT_LABELS] ?? dim}
                </span>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${confColor}`}>
              {confPct}%
            </span>
            <svg
              width="16" height="16" viewBox="0 0 16 16" fill="none"
              stroke="#8AA597" strokeWidth="1.5" strokeLinecap="round"
              className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            >
              <polyline points="4,6 8,10 12,6" />
            </svg>
          </div>
        </div>

        {/* 展开内容 */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-bamboo-100">
            <p className="text-xs text-bamboo-600 leading-relaxed">
              {insight.insight}
            </p>
          </div>
        )}
      </div>
    </button>
  );
}
