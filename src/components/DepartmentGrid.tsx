"use client";

/**
 * 部门摘要网格 —— 动态列数响应式卡片。
 * 每个卡片展示部门的 CEO 提炼摘要 + 可信度。
 * 不再硬编码部门顺序——从 summaries/confidence 的 key 动态渲染。
 */

import { DEPARTMENT_LABELS } from "@/types/schemas";

interface DepartmentGridProps {
  summaries: Record<string, string>;
  confidence: Record<string, number>;
}

function _deptIcon(key: string): string {
  const icons: Record<string, string> = {
    market_research: "📊",
    competitor_analysis: "🏢",
    product_design: "🎨",
    future_direction: "🔮",
    change_plan: "⚡",
    user_analysis: "👥",
    growth_strategy: "🚀",
  };
  return icons[key] ?? "📋";
}

export default function DepartmentGrid({ summaries, confidence }: DepartmentGridProps) {
  // 从实际数据中提取所有部门 key（合并 summaries 和 confidence 的 key）
  const allKeys = Array.from(
    new Set([...Object.keys(summaries), ...Object.keys(confidence)])
  );

  return (
    <div>
      <h2 className="text-lg font-semibold text-bamboo-800 mb-4 tracking-tight">
        各部门分析结论
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {allKeys.map((key) => {
          const summary = summaries[key];
          const conf = confidence[key];
          const icon = _deptIcon(key);
          const label = DEPARTMENT_LABELS[key] ?? key;

          // 跳过的部门
          if (summary === undefined && conf === undefined) {
            return (
              <div
                key={key}
                className="rounded-xl border border-bamboo-100 bg-bamboo-50/50 p-4 opacity-60"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">{icon}</span>
                  <h3 className="text-sm font-medium text-bamboo-500">{label}</h3>
                </div>
                <p className="text-xs text-bamboo-400 italic">该部门本轮未参与</p>
              </div>
            );
          }

          // 正常部门
          const pct = conf != null ? Math.round(conf * 100) : null;
          const barColor =
            conf != null
              ? conf >= 0.7
                ? "#219C5B"
                : conf >= 0.4
                  ? "#C88C18"
                  : "#D14343"
              : "#8AA597";

          return (
            <div
              key={key}
              className="rounded-xl border border-bamboo-200 bg-white overflow-hidden hover:border-bamboo-300 hover:shadow-sm transition-all"
              style={{ borderTopWidth: 3, borderTopColor: barColor }}
            >
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{icon}</span>
                    <h3 className="text-sm font-medium text-bamboo-800">{label}</h3>
                  </div>
                  {pct != null && (
                    <span
                      className="text-[11px] font-mono font-medium tabular-nums"
                      style={{ color: barColor }}
                    >
                      {pct}%
                    </span>
                  )}
                </div>

                {summary ? (
                  <p className="text-xs text-bamboo-600 leading-relaxed line-clamp-4">
                    {summary}
                  </p>
                ) : (
                  <p className="text-xs text-bamboo-400 italic">暂无数据</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
