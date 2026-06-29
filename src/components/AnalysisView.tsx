"use client";

/**
 * 分析主视图 —— ProgressHeader + PlanningCard + DepartmentCards + CompletionBanner。
 */

import { useRouter } from "next/navigation";
import type { AnalysisState } from "@/types/analysis";
import PlanningCard from "./PlanningCard";
import DepartmentCard from "./DepartmentCard";

interface AnalysisViewProps {
  state: AnalysisState;
  isConnected?: boolean;
  /** 当前分析会话 ID（用于跳转 report 页） */
  analysisId?: string;
}

/** 顶部阶段指示器（含思考圈） */
function ProgressHeader({
  phase,
  callCount,
  maxCalls,
  taskCount,
  completedCount,
  isConnected,
}: {
  phase: string;
  callCount: number;
  maxCalls: number;
  taskCount: number;
  completedCount: number;
  isConnected?: boolean;
}) {
  const phaseLabel =
    phase === "idle"
      ? "等待开始..."
      : phase === "planning"
        ? "🧠 CEO 规划中..."
        : phase === "executing"
          ? `🔄 ${completedCount}/${taskCount} 部门执行中...`
          : "✅ 分析完成";

  const pct = Math.round((callCount / maxCalls) * 100);
  const isThinking = phase === "executing";

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2.5">
          <h1 className="text-[17px] font-semibold text-bamboo-800 tracking-tight">
            {phaseLabel}
          </h1>
          {/* 思考指示器 */}
          {isThinking && isConnected && (
            <span
              className="w-[18px] h-[18px] rounded-full border-2 border-bamboo-300 border-t-accent animate-spin shrink-0"
              title="Agent 思考中..."
            />
          )}
        </div>
        <span className="text-xs text-bamboo-400 font-mono tabular-nums">
          LLM 调用 {callCount}/{maxCalls}
        </span>
      </div>

      {/* 调用进度条 */}
      <div className="h-1.5 rounded-full bg-bamboo-200 overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** 完成横幅 */
function CompletionBanner({ score, analysisId }: { score: number; analysisId?: string }) {
  const router = useRouter();

  return (
    <div className="mt-6 rounded-2xl border border-accent/30 bg-gradient-to-r from-accent-subtle/60 to-accent-subtle/20 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-bamboo-800 mb-0.5">
            ✅ 分析完成
          </p>
          <p className="text-xs text-bamboo-500">
            综合评分 {score}/100 · 所有部门已完成
          </p>
        </div>
        <button
          onClick={() => router.push(`/report/${analysisId || "demo-1"}`)}
          className="
            inline-flex items-center gap-1.5
            px-4 py-2 rounded-xl
            text-sm font-medium
            bg-accent text-white
            hover:bg-accent-hover
            transition-colors cursor-pointer
          "
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="1.5" y="1.5" width="12" height="12" rx="2" />
            <line x1="4" y1="5" x2="11" y2="5" />
            <line x1="4" y1="8" x2="11" y2="8" />
            <line x1="4" y1="11" x2="8" y2="11" />
          </svg>
          查看完整报告
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* 组件主体                                                                    */
/* --------------------------------------------------------------------------- */

export default function AnalysisView({ state, isConnected, analysisId }: AnalysisViewProps) {
  const { plan, departments } = state;
  const deptEntries = Object.entries(departments);
  const completedCount = deptEntries.filter(
    ([, d]) => d.status === "completed"
  ).length;
  const taskCount = plan?.taskCount ?? deptEntries.length;
  const isCompleted = state.phase === "completed" && state.finalReport;

  return (
    <div className="flex flex-col min-h-full max-w-[780px] mx-auto w-full px-8 py-10">
      {/* 顶部进度 */}
      <ProgressHeader
        phase={state.phase}
        callCount={state.callCount}
        maxCalls={state.maxCalls}
        taskCount={taskCount}
        completedCount={completedCount}
        isConnected={isConnected}
      />

      {/* CEO 执行计划 */}
      {plan && (
        <div className="mb-6">
          <PlanningCard
            taskCount={plan.taskCount}
            skippedCount={plan.skippedCount}
            tasks={plan.tasks}
          />
        </div>
      )}

      {/* 部门卡片列表 */}
      <div className="space-y-3">
        {deptEntries.map(([key, dept]) => (
          <DepartmentCard key={key} deptKey={key} dept={dept} />
        ))}
      </div>

      {/* 完成横幅 */}
      {isCompleted && (
        <CompletionBanner score={state.finalReport!.overall_score} analysisId={analysisId} />
      )}

      {/* 错误列表 */}
      {state.errors.length > 0 && (
        <div className="mt-5 p-4 rounded-xl bg-red-50 border border-red-100">
          <p className="text-xs font-medium text-red-600 mb-1">
            ⚠️ {state.errors.length} 条非致命错误
          </p>
          {state.errors.map((err, i) => (
            <p key={i} className="text-xs text-red-500 font-mono">
              {err}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
