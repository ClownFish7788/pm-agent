"use client";

/**
 * 分析主视图 —— 组装 ProgressHeader + PlanningCard + DepartmentCards。
 * 接收 AnalysisState，纯展示组件（硬编码阶段）。
 */

import type { AnalysisState } from "@/types/analysis";
import PlanningCard from "./PlanningCard";
import DepartmentCard from "./DepartmentCard";

interface AnalysisViewProps {
  state: AnalysisState;
}

/** 顶部阶段指示器 */
function ProgressHeader({
  phase,
  callCount,
  maxCalls,
  taskCount,
  completedCount,
}: {
  phase: string;
  callCount: number;
  maxCalls: number;
  taskCount: number;
  completedCount: number;
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

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-[17px] font-semibold text-bamboo-800 tracking-tight">
          {phaseLabel}
        </h1>
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

/* --------------------------------------------------------------------------- */
/* 组件主体                                                                    */
/* --------------------------------------------------------------------------- */

export default function AnalysisView({ state }: AnalysisViewProps) {
  const { plan, departments } = state;
  const deptEntries = Object.entries(departments);
  const completedCount = deptEntries.filter(
    ([, d]) => d.status === "completed"
  ).length;
  const taskCount = plan?.taskCount ?? deptEntries.length;

  return (
    <div className="flex flex-col min-h-full max-w-[780px] mx-auto w-full px-8 py-10">
      {/* 顶部进度 */}
      <ProgressHeader
        phase={state.phase}
        callCount={state.callCount}
        maxCalls={state.maxCalls}
        taskCount={taskCount}
        completedCount={completedCount}
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
