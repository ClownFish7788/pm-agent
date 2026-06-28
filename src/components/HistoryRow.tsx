"use client";

import Link from "next/link";
import type { HistoryRecord } from "@/types/history";
import { DEPARTMENT_LABELS, scoreColor, scoreLabel } from "@/types/history";
import ScoreRing from "./ScoreRing";

/* --------------------------------------------------------------------------- */
/* 迷你部门置信度条                                                             */
/* --------------------------------------------------------------------------- */

function DepartmentBars({ confidence }: { confidence: Record<string, number> }) {
  const entries = Object.entries(confidence).filter(
    ([key]) => key in DEPARTMENT_LABELS
  );

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      {entries.map(([key, value]) => {
        const pct = Math.round(value * 100);
        const barColor =
          value >= 0.7 ? "#219C5B" : value >= 0.4 ? "#C88C18" : "#D14343";

        return (
          <div key={key} className="flex items-center gap-1.5 text-xs">
            <span className="text-bamboo-500 w-8 shrink-0">
              {DEPARTMENT_LABELS[key] ?? key}
            </span>
            {/* 迷你进度条 */}
            <span className="inline-block w-16 h-1.5 rounded-full bg-bamboo-200 overflow-hidden">
              <span
                className="block h-full rounded-full transition-all duration-300"
                style={{ width: `${pct}%`, backgroundColor: barColor }}
              />
            </span>
            <span className="text-bamboo-400 font-mono w-7 text-right tabular-nums">
              {pct}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* 单条时间线行                                                                */
/* --------------------------------------------------------------------------- */

interface HistoryRowProps {
  record: HistoryRecord;
  isLast: boolean;
}

export default function HistoryRow({ record, isLast }: HistoryRowProps) {
  const color = scoreColor(record.overallScore);
  const label = scoreLabel(record.overallScore);
  const date = new Date(record.createdAt).toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="flex gap-0 group">
      {/* ---- 左侧：时间线 ---- */}
      <div className="flex flex-col items-center w-[72px] shrink-0">
        {/* 日期 */}
        <span className="text-xs text-bamboo-400 mb-1.5 font-mono tabular-nums">
          {date}
        </span>

        {/* 圆点 + 竖线 */}
        <div className="relative flex flex-col items-center flex-1">
          {/* 竖线（从圆点向下延伸） */}
          {!isLast && (
            <div
              className="absolute top-3 w-px bg-bamboo-200"
              style={{ height: "calc(100% + 12px)" }}
            />
          )}

          {/* 圆点 */}
          <div
            className="relative z-10 w-3 h-3 rounded-full border-2 border-white shrink-0"
            style={{ backgroundColor: color, boxShadow: `0 0 0 2px ${color}20` }}
          />
        </div>
      </div>

      {/* ---- 右侧：内容卡片 ---- */}
      <div
        className={`
          flex-1 mb-4
          bg-white border border-bamboo-200 rounded-2xl
          hover:border-bamboo-300 hover:shadow-sm
          transition-all duration-200
          overflow-hidden
        `}
      >
        <div className="p-5">
          {/* 第一行：项目名 + 评分 */}
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-[15px] font-semibold text-bamboo-800 leading-snug truncate">
                {record.projectDescription.length > 50
                  ? record.projectDescription.slice(0, 50) + "..."
                  : record.projectDescription}
              </h3>
            </div>

            {/* 评分圆环 + 标签 */}
            <div className="flex items-center gap-2.5 shrink-0">
              <span
                className="text-[11px] font-medium px-2 py-0.5 rounded-full"
                style={{
                  color,
                  backgroundColor: `${color}15`,
                }}
              >
                {label}
              </span>
              <ScoreRing score={record.overallScore} size={46} strokeWidth={3} />
            </div>
          </div>

          {/* 第二行：部门置信度条 */}
          <DepartmentBars confidence={record.dimensionConfidence} />

          {/* 第三行：摘要（截断 2 行） */}
          <p className="mt-3 text-[13px] leading-relaxed text-bamboo-500 line-clamp-2">
            {record.executiveSummary}
          </p>

          {/* 第四行：元数据 + 操作 */}
          <div className="mt-3 flex items-center justify-between gap-4">
            {/* 元数据标签 */}
            <div className="flex items-center gap-3 text-[11px] text-bamboo-400">
              <span className="inline-flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
                  <path d="M6 1v2M6 9v2M1 6h2M9 6h2M2.5 2.5l1.4 1.4M8.1 8.1l1.4 1.4M2.5 9.5l1.4-1.4M8.1 3.9l1.4-1.4" />
                </svg>
                {record.callCount} 次调用
              </span>
              <span className="inline-flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
                  <rect x="1" y="1" width="4" height="4" rx="1" />
                  <rect x="7" y="1" width="4" height="4" rx="1" />
                  <rect x="1" y="7" width="4" height="4" rx="1" />
                  <rect x="7" y="7" width="4" height="4" rx="1" />
                </svg>
                {record.departmentCount} 部门
              </span>
              {record.rejectionRounds > 0 && (
                <span className="inline-flex items-center gap-1">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 6.5L4 3.5L11 10.5" />
                    <path d="M8 10.5L11 10.5L11 7.5" />
                  </svg>
                  {record.rejectionRounds} 轮驳回
                </span>
              )}
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-2 shrink-0">
              <Link
                href={`/chat/${record.id}`}
                className="
                  inline-flex items-center gap-1
                  px-3 py-1.5 rounded-lg
                  text-xs font-medium
                  text-bamboo-600 bg-bamboo-50
                  hover:bg-bamboo-100
                  border border-bamboo-200
                  transition-colors no-underline
                "
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5,1 11,6 5,11 1,11 1,1" />
                </svg>
                回放过程
              </Link>
              <Link
                href={`/report/${record.id}`}
                className="
                  inline-flex items-center gap-1
                  px-3 py-1.5 rounded-lg
                  text-xs font-medium
                  text-white bg-accent
                  hover:bg-accent-hover
                  transition-colors no-underline
                "
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="1.5" y="1" width="9" height="10" rx="1.5" />
                  <line x1="3.5" y1="3.5" x2="8.5" y2="3.5" />
                  <line x1="3.5" y1="5.5" x2="8.5" y2="5.5" />
                  <line x1="3.5" y1="7.5" x2="6" y2="7.5" />
                </svg>
                查看报告
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
