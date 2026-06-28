"use client";

/**
 * 报告主视图 —— 组装所有 section。
 *
 * 顺序：ScoreHero → ExecutiveSummary → DepartmentGrid →
 *       CrossInsights → Recommendations → Risks → Export
 */

import type { FinalReport } from "@/types/schemas";
import ScoreHero from "./ScoreHero";
import DepartmentGrid from "./DepartmentGrid";
import CrossInsightCard from "./CrossInsightCard";
import RecommendationList from "./RecommendationList";
import RiskList from "./RiskList";

interface ReportViewProps {
  report: FinalReport;
  departmentCount?: number;
  callCount?: number;
}

export default function ReportView({
  report,
  departmentCount = 5,
  callCount = 33,
}: ReportViewProps) {
  return (
    <div className="flex flex-col min-h-full max-w-[860px] mx-auto w-full px-8 py-10">
      {/* ================================================================ */}
      {/* ① 评分英雄区                                                      */}
      {/* ================================================================ */}
      <section className="mb-8">
        <ScoreHero
          overallScore={report.overall_score}
          dimensionConfidence={report.dimension_confidence}
          departmentCount={departmentCount}
          callCount={callCount}
        />
      </section>

      {/* ================================================================ */}
      {/* ② 执行摘要                                                        */}
      {/* ================================================================ */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-bamboo-800 mb-3 tracking-tight">
          执行摘要
        </h2>
        <div className="rounded-xl bg-white border border-bamboo-200 overflow-hidden">
          <div className="flex">
            {/* 左侧绿色竖线 */}
            <div className="w-1 bg-accent shrink-0" />
            <div className="p-5">
              <p className="text-[15px] text-bamboo-700 leading-[1.8]">
                {report.executive_summary}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================ */}
      {/* ③ 部门分析                                                        */}
      {/* ================================================================ */}
      <section className="mb-10">
        <DepartmentGrid
          summaries={report.department_summaries}
          confidence={report.dimension_confidence}
        />
      </section>

      {/* ================================================================ */}
      {/* ④ 交叉洞察                                                        */}
      {/* ================================================================ */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-bamboo-800 mb-4 tracking-tight">
          跨部门交叉洞察
        </h2>
        {report.cross_insights.length === 0 ? (
          <p className="text-sm text-bamboo-400 italic">暂无交叉洞察</p>
        ) : (
          <div className="space-y-2.5">
            {report.cross_insights.map((ci, i) => (
              <CrossInsightCard key={i} insight={ci} />
            ))}
          </div>
        )}
      </section>

      {/* ================================================================ */}
      {/* ⑤ 战略建议                                                        */}
      {/* ================================================================ */}
      <section className="mb-10">
        <RecommendationList recommendations={report.recommendations} />
      </section>

      {/* ================================================================ */}
      {/* ⑥ 风险                                                            */}
      {/* ================================================================ */}
      <section className="mb-10">
        <RiskList risks={report.risks} />
      </section>

      {/* ================================================================ */}
      {/* ⑦ 导出                                                            */}
      {/* ================================================================ */}
      <section className="mb-8">
        <div className="flex items-center gap-3 justify-center">
          <button className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors cursor-pointer">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 10.5V13.5H13.5V10.5" />
              <path d="M8 2.5V10.5" />
              <polyline points="5,7 8,10 11,7" />
            </svg>
            导出 Markdown
          </button>

          <button className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-bamboo-200 bg-white text-sm font-medium text-bamboo-500 hover:border-bamboo-300 transition-colors cursor-not-allowed"
            title="PDF 导出即将支持"
            disabled
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1.5" y="1" width="13" height="14" rx="2" />
              <line x1="4.5" y1="4.5" x2="11.5" y2="4.5" />
              <line x1="4.5" y1="7.5" x2="11.5" y2="7.5" />
              <line x1="4.5" y1="10.5" x2="8" y2="10.5" />
            </svg>
            导出 PDF（即将支持）
          </button>
        </div>
      </section>
    </div>
  );
}
