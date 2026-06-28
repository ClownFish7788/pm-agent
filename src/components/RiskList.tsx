"use client";

/**
 * 风险列表 —— 3 列网格，颜色编码严重程度。
 */

import type { RiskFlag } from "@/types/schemas";
import { DEPARTMENT_LABELS } from "@/types/history";

interface RiskListProps {
  risks: RiskFlag[];
}

const SEV_CONFIG: Record<
  RiskFlag["severity"],
  { label: string; bg: string; border: string; text: string; dot: string }
> = {
  high: {
    label: "高风险",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    dot: "bg-red-500",
  },
  medium: {
    label: "中风险",
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-700",
    dot: "bg-amber-500",
  },
  low: {
    label: "低风险",
    bg: "bg-accent-subtle",
    border: "border-accent/20",
    text: "text-accent",
    dot: "bg-accent",
  },
};

export default function RiskList({ risks }: RiskListProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-bamboo-800 mb-4 tracking-tight">
        风险与不确定性
      </h2>

      {risks.length === 0 ? (
        <p className="text-sm text-bamboo-400 italic">未发现显著风险</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {risks.map((risk, i) => {
            const cfg = SEV_CONFIG[risk.severity];

            return (
              <div
                key={i}
                className={`rounded-xl border ${cfg.border} ${cfg.bg} p-4`}
                style={{ borderTopWidth: 3 }}
              >
                {/* 严重程度 */}
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                  <span className={`text-[11px] font-medium ${cfg.text}`}>
                    {cfg.label}
                  </span>
                </div>

                {/* 标题 */}
                <h4 className="text-sm font-medium text-bamboo-800 mb-1">
                  {risk.title}
                </h4>

                {/* 描述 */}
                <p className="text-xs text-bamboo-600 leading-relaxed mb-2">
                  {risk.description}
                </p>

                {/* 来源 */}
                {risk.related_dimension && (
                  <span className="text-[10px] text-bamboo-400">
                    来源：
                    {DEPARTMENT_LABELS[
                      risk.related_dimension as keyof typeof DEPARTMENT_LABELS
                    ] ?? risk.related_dimension}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
