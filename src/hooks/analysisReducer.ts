/**
 * 分析状态机纯函数 —— 12 种 SSE 事件 → AnalysisState 迁移。
 *
 * 不依赖 React、不调 API、不存状态。可脱离浏览器单独测试。
 *
 * 核心复杂度在 sub_agent_start：同一 agent_id 再次出现 = 重试，
 * 需要 push 新 round 而非覆盖。
 */

import type { AnalysisState, DepartmentState, SubAgentSlot } from "@/types/analysis";
import type { SSEEvent } from "@/types/schemas";

// =============================================================================
// 初始状态
// =============================================================================

export const INITIAL_STATE: AnalysisState = {
  phase: "idle",
  plan: null,
  departments: {},
  callCount: 0,
  maxCalls: 150,
  finalReport: null,
  errors: [],
};

// =============================================================================
// Reducer
// =============================================================================

export function analysisReducer(
  state: AnalysisState,
  event: SSEEvent
): AnalysisState {
  switch (event.event_type) {
    // -----------------------------------------------------------------
    // plan_generated: CEO 产出执行计划 → 创建所有部门槽位
    // -----------------------------------------------------------------
    case "plan_generated": {
      const { tasks, skipped } = event.data;
      const departments: Record<string, DepartmentState> = {};

      for (const [key, taskInfo] of Object.entries(tasks)) {
        departments[key] = {
          label: taskInfo.display_name || key,
          focusAreas: taskInfo.focus_areas,
          status: (skipped as string[] | undefined)?.includes(key)
            ? "skipped"
            : "pending",
          subAgents: [],
          summary: "",
          confidence: 0,
          keyPointsCount: 0,
        };
      }

      return {
        ...state,
        phase: "executing",
        callCount: event.call_count,
        plan: {
          taskCount: event.data.task_count,
          skippedCount: event.data.skipped_count,
          tasks: Object.entries(tasks).map(([key, taskInfo]) => ({
            department: key,
            label: taskInfo.display_name || key,
            focusAreas: taskInfo.focus_areas,
            metrics: taskInfo.metrics,
            status: (skipped as string[] | undefined)?.includes(key)
              ? ("skipped" as const)
              : ("pending" as const),
          })),
        },
        departments,
      };
    }

    // -----------------------------------------------------------------
    // budget_update: 更新调用计数
    // -----------------------------------------------------------------
    case "budget_update":
      return {
        ...state,
        callCount: event.data.total_calls,
        maxCalls: event.data.max_calls,
      };

    // -----------------------------------------------------------------
    // department_start: 部门收到任务，开始执行
    // -----------------------------------------------------------------
    case "department_start": {
      const dept = event.department!;
      const prev = state.departments[dept];
      if (!prev) return state;
      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: {
            ...prev,
            status: "running",
            focusAreas: event.data.focus_areas,
          },
        },
      };
    }

    // -----------------------------------------------------------------
    // department_skip: 部门被跳过
    // -----------------------------------------------------------------
    case "department_skip": {
      const dept = event.department!;
      const prev = state.departments[dept];
      if (!prev) return state;
      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: { ...prev, status: "skipped" },
        },
      };
    }

    // -----------------------------------------------------------------
    // sub_agent_start: 调度 SearchAgent
    // 关键逻辑：同 id 已存在 → push 新 round（驳回重试）
    //           否则 → 新建 SubAgentSlot
    // -----------------------------------------------------------------
    case "sub_agent_start": {
      const dept = event.department!;
      const agentId = event.agent_id!;
      const prev = state.departments[dept];
      if (!prev) return state;

      const existIdx = prev.subAgents.findIndex((s) => s.id === agentId);

      let next: SubAgentSlot[];
      if (existIdx >= 0) {
        // 重试：追加新 round
        next = [...prev.subAgents];
        const old = next[existIdx];
        next[existIdx] = {
          ...old,
          status: "searching",
          rounds: [
            ...old.rounds,
            {
              round: old.rounds.length + 1,
              searchQuery: event.data.search_query,
              resultCount: null,
              findingsCount: null,
              reportSummary: null,
              review: null,
            },
          ],
        };
      } else {
        // 新 Agent：创建 slot
        next = [
          ...prev.subAgents,
          {
            id: agentId,
            status: "searching",
            rounds: [
              {
                round: 1,
                searchQuery: event.data.search_query,
                resultCount: null,
                findingsCount: null,
                reportSummary: null,
                review: null,
              },
            ],
          },
        ];
      }

      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: { ...prev, subAgents: next },
        },
      };
    }

    // -----------------------------------------------------------------
    // sub_agent_search: Tavily 搜索完成
    // -----------------------------------------------------------------
    case "sub_agent_search": {
      const dept = event.department!;
      const agentId = event.agent_id!;
      const prev = state.departments[dept];
      if (!prev) return state;

      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: {
            ...prev,
            subAgents: updateLatestRound(prev.subAgents, agentId, {
              resultCount: event.data.result_count,
            }),
          },
        },
      };
    }

    // -----------------------------------------------------------------
    // sub_agent_done: LLM 分析完成
    // -----------------------------------------------------------------
    case "sub_agent_done": {
      const dept = event.department!;
      const agentId = event.agent_id!;
      const prev = state.departments[dept];
      if (!prev) return state;

      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: {
            ...prev,
            subAgents: updateLatestRound(prev.subAgents, agentId, {
              findingsCount: event.data.findings_count,
              reportSummary: event.data.report_summary,
            }),
          },
        },
      };
    }

    // -----------------------------------------------------------------
    // sub_agent_review: 审核结果
    // -----------------------------------------------------------------
    case "sub_agent_review": {
      const dept = event.department!;
      const agentId = event.agent_id!;
      const prev = state.departments[dept];
      if (!prev) return state;

      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: {
            ...prev,
            subAgents: updateLatestRound(prev.subAgents, agentId, {
              review: {
                verdict: event.data.verdict,
                overallScore: event.data.overall_score,
                credibility: event.data.credibility,
                reason: event.data.reason,
              },
            }).map((s) =>
              s.id === agentId
                ? {
                    ...s,
                    status:
                      event.data.verdict === "passed"
                        ? ("passed" as const)
                        : ("rejected" as const),
                  }
                : s
            ),
          },
        },
      };
    }

    // -----------------------------------------------------------------
    // department_done: 部门完成，写入摘要
    // -----------------------------------------------------------------
    case "department_done": {
      const dept = event.department!;
      const prev = state.departments[dept];
      if (!prev) return state;

      return {
        ...state,
        callCount: event.call_count,
        departments: {
          ...state.departments,
          [dept]: {
            ...prev,
            status: "completed",
            summary: event.data.summary,
            confidence: event.data.overall_confidence,
            keyPointsCount: event.data.key_points_count,
          },
        },
      };
    }

    // -----------------------------------------------------------------
    // final_report: CEO 综合报告
    // -----------------------------------------------------------------
    case "final_report":
      return {
        ...state,
        phase: "completed",
        callCount: event.call_count,
        finalReport: event.data,
      };

    // -----------------------------------------------------------------
    // done: 流结束
    // -----------------------------------------------------------------
    case "done":
      return { ...state, callCount: event.call_count };

    // -----------------------------------------------------------------
    // error: 非致命错误
    // -----------------------------------------------------------------
    case "error":
      return {
        ...state,
        callCount: event.call_count,
        errors: [...state.errors, event.data.error],
      };

    default:
      return state;
  }
}

// =============================================================================
// 辅助：更新 SubAgentSlot 的最新 round（不改其他 slot）
// =============================================================================

function updateLatestRound(
  slots: SubAgentSlot[],
  agentId: string,
  patch: Partial<SubAgentSlot["rounds"][number]>
): SubAgentSlot[] {
  return slots.map((s) => {
    if (s.id !== agentId) return s;
    const rounds = [...s.rounds];
    const last = { ...rounds[rounds.length - 1], ...patch };
    rounds[rounds.length - 1] = last;
    return { ...s, rounds };
  });
}
