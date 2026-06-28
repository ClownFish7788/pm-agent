"use client";

/**
 * 单个中层部门卡片 —— 可折叠，展示调度链。
 *
 * 结构：
 *   头部：部门名 + 状态标识 + 折叠按钮
 *   展开 → 任务简述 → SubAgentRow 列表 → 完成摘要
 */

import { useState } from "react";
import type { DepartmentState } from "@/types/analysis";
import SubAgentRow from "./SubAgentRow";

interface DepartmentCardProps {
  deptKey: string;
  dept: DepartmentState;
}

const STATUS_CONFIG: Record<
  DepartmentState["status"],
  { label: string; dot: string; bg: string }
> = {
  completed: { label: "已完成", dot: "bg-accent", bg: "bg-accent-subtle/50" },
  running: { label: "运行中", dot: "bg-accent animate-pulse", bg: "bg-white" },
  pending: { label: "等待调度", dot: "bg-bamboo-300", bg: "bg-bamboo-50/50" },
  skipped: { label: "已跳过", dot: "bg-bamboo-300", bg: "bg-bamboo-50/30" },
};

export default function DepartmentCard({ deptKey, dept }: DepartmentCardProps) {
  const [expanded, setExpanded] = useState(
    dept.status === "running" || dept.status === "completed"
  );
  const cfg = STATUS_CONFIG[dept.status];
  const hasActivity = dept.subAgents.length > 0;

  return (
    <div
      className={`rounded-2xl border overflow-hidden transition-colors duration-200 ${
        dept.status === "completed"
          ? "border-accent/20 bg-accent-subtle/30"
          : dept.status === "running"
            ? "border-bamboo-200 bg-white"
            : dept.status === "skipped"
              ? "border-bamboo-100 bg-bamboo-50/30 opacity-70"
              : "border-bamboo-100 bg-bamboo-50/50"
      }`}
    >
      {/* ---- 头部 ---- */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 text-left cursor-pointer hover:bg-bamboo-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {/* 圆点 */}
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${cfg.dot}`} />

          {/* 部门名 + 任务 */}
          <div>
            <h3 className="text-[15px] font-semibold text-bamboo-800">
              {dept.label}
            </h3>
            {dept.focusAreas.length > 0 && dept.status !== "skipped" && (
              <p className="text-xs text-bamboo-400 mt-0.5">
                🧠 任务：{dept.focusAreas.join("、")}
              </p>
            )}
            {dept.status === "skipped" && (
              <p className="text-xs text-bamboo-400 mt-0.5">该部门本轮不适用</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`text-[11px] font-medium ${cfg.dot.replace("bg-", "text-")}`}>
            {dept.status === "completed" && dept.confidence > 0
              ? `${cfg.label} · ${Math.round(dept.confidence * 100)}%`
              : cfg.label}
          </span>
          <svg
            width="16" height="16" viewBox="0 0 16 16" fill="none"
            stroke="#8AA597" strokeWidth="1.5" strokeLinecap="round"
            className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          >
            <polyline points="4,6 8,10 12,6" />
          </svg>
        </div>
      </button>

      {/* ---- 展开内容 ---- */}
      {expanded && (
        <div className="px-5 pb-4 space-y-3">
          {/* 无活动时 */}
          {!hasActivity && dept.status === "pending" && (
            <p className="text-xs text-bamboo-400 italic py-2">
              ⏳ 等待上级 Agent 调度...
            </p>
          )}

          {/* SubAgent 活动列表 */}
          {dept.subAgents.map((slot) => (
            <SubAgentRow key={slot.id} slot={slot} />
          ))}

          {/* 部门完成摘要 */}
          {dept.status === "completed" && dept.summary && (
            <div className="mt-3 pt-3 border-t border-bamboo-100">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[11px] font-medium text-bamboo-500">
                  ✅ 部门分析完成
                </span>
                <span className="text-[11px] text-bamboo-400">
                  · 可信度 {Math.round(dept.confidence * 100)}%
                  · 产出 {dept.keyPointsCount} 条要点
                </span>
              </div>
              <p className="text-xs text-bamboo-600 leading-relaxed line-clamp-3">
                {dept.summary}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
