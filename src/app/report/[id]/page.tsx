/**
 * Report 页 —— 分析报告看板。
 *
 * 数据来源优先级：reportStore（Chat 页写入）→ MOCK_REPORT（开发期占位）
 */

"use client";

import { reportStore } from "@/stores/reportStore";
import { MOCK_REPORT } from "@/data/mockReport";
import ReportView from "@/components/ReportView";

export default function ReportPage() {
  // 优先读缓存，fallback mock
  const report = reportStore.get() ?? MOCK_REPORT;

  return (
    <ReportView
      report={report}
      departmentCount={5}
      callCount={33}
    />
  );
}
