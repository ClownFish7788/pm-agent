/**
 * 分析页专用类型 —— 前端状态机 State 形状。
 *
 * 与 schemas.ts（SSE 事件类型）分离：
 * - schemas.ts = 线上传输格式（后端 → 前端）
 * - analysis.ts = 前端累积状态（reducer 聚合多事件后的 UI 模型）
 */

// =============================================================================
// 子 Agent 重试轮次
// =============================================================================

/** 单轮搜索 + 审核 */
export interface SubAgentRound {
  round: number;
  /** 本轮使用的搜索关键词 */
  searchQuery: string;
  /** Tavily 返回结果数 */
  resultCount: number | null;
  /** LLM 筛选后产出条数 */
  findingsCount: number | null;
  /** LLM 产出摘要（截断 200 字） */
  reportSummary: string | null;
  /** 审核结论（最后一轮才有，中间轮次为 null） */
  review: {
    verdict: "passed" | "rejected";
    overallScore: number;
    credibility: number;
    reason: string;
  } | null;
}

/** 底层搜索 Agent 的完整活动记录 */
export interface SubAgentSlot {
  id: string;
  status: "idle" | "searching" | "analyzing" | "passed" | "rejected";
  rounds: SubAgentRound[];
}

// =============================================================================
// 部门状态
// =============================================================================

/** CEO 派发的任务 */
export interface DispatchedTask {
  department: string;
  label: string;
  focusAreas: string[];
  metrics: string[];
  status: "pending" | "running" | "completed" | "skipped";
}

/** 单个中层部门 */
export interface DepartmentState {
  label: string;
  focusAreas: string[];
  status: "pending" | "running" | "completed" | "skipped";
  subAgents: SubAgentSlot[];
  summary: string;
  confidence: number;
  keyPointsCount: number;
}

// =============================================================================
// 全局分析状态
// =============================================================================

export type AnalysisPhase = "idle" | "planning" | "executing" | "completed";

export interface AnalysisState {
  phase: AnalysisPhase;
  /** CEO 执行计划 */
  plan: {
    taskCount: number;
    skippedCount: number;
    tasks: DispatchedTask[];
  } | null;
  /** 各部门状态，key = "market_research" 等 */
  departments: Record<string, DepartmentState>;
  /** LLM 调用计数 */
  callCount: number;
  maxCalls: number;
  /** 最终报告（done 后填充） */
  finalReport: import("./schemas").FinalReport | null;
  /** 非致命错误 */
  errors: string[];
}
