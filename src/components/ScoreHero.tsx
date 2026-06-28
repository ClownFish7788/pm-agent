"use client";

/**
 * 评分英雄区 —— 报告页最显眼的视觉锚点。
 * 大号评分圆环 + 5 个部门置信度条 + 元数据行。
 */

import ScoreRing from "./ScoreRing";
import { DEPARTMENT_LABELS, scoreLabel } from "@/types/history";

interface ScoreHeroProps {
  overallScore: number;
  dimensionConfidence: Record<string, number>;
  departmentCount: number;
  callCount: number;
}

const DEPT_ORDER = [
  "market_research",
  "competitor_analysis",
  "product_design",
  "future_direction",
  "change_plan",
];

export default function ScoreHero({
  overallScore,
  dimensionConfidence,
  departmentCount,
  callCount,
}: ScoreHeroProps) {
  const label = scoreLabel(overallScore);
  const labelColor =
    overallScore >= 70
      ? "text-accent bg-accent-subtle"
      : overallScore >= 40
        ? "text-amber-600 bg-amber-50"
        : "text-red-600 bg-red-50";

  return (
    <div className="relative overflow-hidden rounded-2xl bg-white border border-bamboo-200">
      {/* 背景光晕（复用问候区的设计语言） */}
      <div
        className="absolute top-[-60px] right-[-60px] w-[300px] h-[300px] rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, rgba(33,156,91,0.05) 0%, transparent 70%)`,
        }}
      />

      <div className="relative px-8 py-10">
        {/* 第一行：评分环 + 标题 */}
        <div className="flex items-center gap-8 mb-8">
          <ScoreRing score={overallScore} size={120} strokeWidth={6} />

          <div>
            <span
              className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full mb-2 ${labelColor}`}
            >
              {label}
            </span>
            <h1 className="text-2xl font-bold text-bamboo-800 tracking-tight mb-1">
              综合可行性评分
            </h1>
            <p className="text-sm text-bamboo-500">
              基于 {departmentCount} 个部门分析结果的交叉评估
            </p>
          </div>
        </div>

        {/* 第二行：部门置信度条 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2.5">
          {DEPT_ORDER.map((key) => {
            const conf = dimensionConfidence[key];
            if (conf === undefined) return null;
            const pct = Math.round(conf * 100);
            const barColor =
              conf >= 0.7 ? "#219C5B" : conf >= 0.4 ? "#C88C18" : "#D14343";

            return (
              <div key={key} className="flex items-center gap-3">
                <span className="text-xs text-bamboo-600 w-16 shrink-0">
                  {DEPARTMENT_LABELS[key as keyof typeof DEPARTMENT_LABELS] ?? key}
                </span>
                <span className="flex-1 h-2 rounded-full bg-bamboo-100 overflow-hidden">
                  <span
                    className="block h-full rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, backgroundColor: barColor }}
                  />
                </span>
                <span className="text-xs font-mono text-bamboo-500 w-9 text-right tabular-nums">
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>

        {/* 第三行：元数据 */}
        <div className="mt-6 pt-5 border-t border-bamboo-100 flex items-center gap-5 text-xs text-bamboo-400">
          <span>{departmentCount} 个部门参与</span>
          <span className="text-bamboo-200">|</span>
          <span>{callCount} 次 LLM 调用</span>
          <span className="text-bamboo-200">|</span>
          <span>2026年6月28日</span>
        </div>
      </div>
    </div>
  );
}
