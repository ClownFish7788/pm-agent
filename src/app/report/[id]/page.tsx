/**
 * Report 页 —— 分析报告看板。
 *
 * 数据来源优先级：
 *   1. analysisSession（后台仍在收 SSE 时，实时更新）
 *   2. reportStore（Chat 页写入的缓存，刷新恢复）
 *   3. MOCK_REPORT（开发期占位）
 *
 * 包含「← 回放 Agent 过程」导航按钮，切换不中断 SSE。
 */

"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { analysisSession } from "@/stores/analysisSession";
import { reportStore } from "@/stores/reportStore";
import { MOCK_REPORT } from "@/data/mockReport";
import type { FinalReport } from "@/types/schemas";
import ReportView from "@/components/ReportView";

export default function ReportPage() {
  const params = useParams();
  const router = useRouter();
  const chatId = (params.id as string) ?? "demo-1";

  const [liveReport, setLiveReport] = useState<FinalReport | null>(
    () => analysisSession.getState().finalReport
  );
  const [liveCallCount, setLiveCallCount] = useState(
    () => analysisSession.getState().callCount
  );
  const [liveDeptCount, setLiveDeptCount] = useState(() => {
    const plan = analysisSession.getState().plan;
    return plan?.taskCount ?? 5;
  });

  // 订阅 analysisSession —— 实时拿到 finalReport + callCount
  useEffect(() => {
    return analysisSession.subscribe((s) => {
      if (s.finalReport) setLiveReport(s.finalReport);
      setLiveCallCount(s.callCount);
      if (s.plan) setLiveDeptCount(s.plan.taskCount);
    });
  }, []);

  // 数据来源优先级
  const report: FinalReport =
    liveReport ??           // 1. 实时 session
    reportStore.get() ??    // 2. sessionStorage 缓存
    MOCK_REPORT;            // 3. 开发期占位

  const callCount = liveCallCount > 0 ? liveCallCount : 33;
  const deptCount = liveDeptCount > 0 ? liveDeptCount : 5;
  const isLive = analysisSession.isActive;

  return (
    <div>
      {/* 顶部导航栏 */}
      <div className="sticky top-0 z-20 bg-bamboo-50/90 backdrop-blur-sm border-b border-bamboo-200">
        <div className="max-w-[860px] mx-auto px-8 py-2.5 flex items-center justify-between">
          <Link
            href={`/chat/${chatId}`}
            className="
              inline-flex items-center gap-1.5
              text-xs text-bamboo-500
              hover:text-accent
              transition-colors no-underline
            "
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="8,2 3,7 8,12" />
            </svg>
            回放 Agent 过程
          </Link>

          {isLive && (
            <span className="flex items-center gap-1.5 text-xs text-accent">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              分析进行中，数据实时更新
            </span>
          )}
        </div>
      </div>

      <ReportView
        report={report}
        departmentCount={deptCount}
        callCount={callCount}
      />
    </div>
  );
}
