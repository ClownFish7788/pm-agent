"use client";

/**
 * CEO 执行计划卡片 —— plan_generated 后显示。
 * 列出 CEO 向各中层部门派发的任务，标注状态（完成/运行/等待/跳过）。
 */

import type { DispatchedTask } from "@/types/analysis";

interface PlanningCardProps {
  taskCount: number;
  skippedCount: number;
  tasks: DispatchedTask[];
}

const DEPT_ICONS: Record<string, string> = {
  market_research: "📊",
  competitor_analysis: "🏢",
  product_design: "🎨",
  future_direction: "🔮",
  change_plan: "⚡",
};

const STATUS_STYLE: Record<string, string> = {
  completed: "text-accent bg-accent-subtle",
  running: "text-amber-600 bg-amber-50",
  pending: "text-bamboo-400 bg-bamboo-100",
  skipped: "text-bamboo-400/60 bg-bamboo-50 line-through",
};

export default function PlanningCard({ taskCount, skippedCount, tasks }: PlanningCardProps) {
  return (
    <div className="rounded-2xl border border-accent/20 bg-accent-subtle/20 overflow-hidden">
      {/* 头部 */}
      <div className="px-5 py-4 border-b border-accent/10">
        <div className="flex items-center gap-2">
          <span className="text-lg">🧠</span>
          <div>
            <h2 className="text-sm font-semibold text-bamboo-800">
              CEO 分析完成，发布执行计划
            </h2>
            <p className="text-xs text-bamboo-500 mt-0.5">
              向 {taskCount} 个部门下达任务
              {skippedCount > 0 && `，跳过 ${skippedCount} 个`}
            </p>
          </div>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="px-5 py-3 space-y-1.5">
        {tasks.map((task) => (
          <div
            key={task.department}
            className="flex items-center gap-3 py-1.5"
          >
            {/* 状态点 */}
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                task.status === "completed"
                  ? "bg-accent"
                  : task.status === "running"
                    ? "bg-amber-400 animate-pulse"
                    : task.status === "skipped"
                      ? "bg-bamboo-300"
                      : "bg-bamboo-300"
              }`}
            />

            {/* 图标 + 部门名 */}
            <span className="text-sm shrink-0">
              {DEPT_ICONS[task.department] ?? "📋"}
            </span>
            <span className="text-sm font-medium text-bamboo-700 w-20 shrink-0">
              {task.label}
            </span>

            {/* 箭头 */}
            <span className="text-bamboo-300 shrink-0">←</span>

            {/* 任务内容 */}
            <span className="text-xs text-bamboo-500 leading-relaxed min-w-0 truncate">
              {task.focusAreas.join("、")}
            </span>

            {/* 状态标签 */}
            <span
              className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full font-medium ${
                STATUS_STYLE[task.status]
              }`}
            >
              {task.status === "completed"
                ? "完成"
                : task.status === "running"
                  ? "运行中"
                  : task.status === "skipped"
                    ? "跳过"
                    : "等待"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
