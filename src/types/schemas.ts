/**
 * 前端类型定义 —— 与后端 agent-backend/schemas/__init__.py 严格对应。
 *
 * 所有 Agent 间通信的数据结构都在这里，是前端消费 SSE 事件流、
 * 渲染报告看板的「唯一真源」。后端改了字段这里必须同步更新。
 */

// =============================================================================
// 枚举
// =============================================================================

/** SSE 事件类型（对应后端 SSEEventType） */
export type SSEEventType =
  | "plan_generated"
  | "budget_update"
  | "department_start"
  | "department_skip"
  | "sub_agent_start"
  | "sub_agent_search"
  | "sub_agent_done"
  | "sub_agent_review"
  | "department_done"
  | "final_report"
  | "error"
  | "done";

/** 中层部门标识（对应后端 MiddleAgentType） */
export type MiddleAgentType =
  | "market_research"
  | "competitor_analysis"
  | "product_design"
  | "future_direction"
  | "change_plan";

/** Agent 状态（对应后端 AgentStatus） */
export type AgentStatus =
  | "running"
  | "passed"
  | "rejected"
  | "uncertain"
  | "skipped"
  | "idle";

/** 来源类型（对应后端 SourceType） */
export type SourceType = "data" | "report" | "opinion";

/** 可信度等级 */
export type ConfidenceLevel = "high" | "medium" | "low" | "uncertain";

/** 风险严重程度 */
export type Severity = "high" | "medium" | "low";

// =============================================================================
// 用户输入
// =============================================================================

/** 用户项目信息（对应后端 ProjectInfo） */
export interface ProjectInfo {
  description: string;
  target_market?: string | null;
  budget_range?: string | null;
  competitors_known?: string[];
  extra_context?: string | null;
}

/** 分析请求体（POST /analyze/stream 的 body） */
export interface AnalyzeRequest {
  description: string;
}

// =============================================================================
// 顶层执行计划
// =============================================================================

/** 中层部门专属任务（对应后端 DepartmentTask） */
export interface DepartmentTask {
  agent_type: MiddleAgentType;
  focus_areas: string[];
  instruction: string;
  core_topic: string;
}

/** 执行计划（对应后端 ExecutionPlan） */
export interface ExecutionPlan {
  tasks: DepartmentTask[];
  skipped: MiddleAgentType[];
  skip_reasons: Record<string, string>;
  max_cycles: number;
}

// =============================================================================
// 底层发现 & 报告
// =============================================================================

/** 单条关键发现（对应后端 Finding） */
export interface Finding {
  insight: string;
  source_url: string;
  source_type: SourceType;
  relevance: number;
  confidence: number;
}

/** 底层研究员报告（对应后端 BottomReport） */
export interface BottomReport {
  report: string;
  key_findings: Finding[];
  total_sources: number;
}

// =============================================================================
// 审核 & 驳回
// =============================================================================

/** 单条审核结果（对应后端 SubAgentReview） */
export interface SubAgentReview {
  sub_id: string;
  overall_score: number;
  completeness: number;
  credibility: number;
  freshness: number;
  relevance: number;
  verdict: "passed" | "rejected";
  reason: string;
  improved_query: string;
}

/** 审核批量结果（对应后端 ReviewResult） */
export interface ReviewResult {
  reviews: SubAgentReview[];
}

// =============================================================================
// 中层分析要点
// =============================================================================

/** 单条分析要点（对应后端 AnalysisPoint） */
export interface AnalysisPoint {
  title: string;
  content: string;
  confidence_level: ConfidenceLevel;
  source_count: number;
  related_finding_indices: number[];
}

// =============================================================================
// 部门中文映射
// =============================================================================

export const DEPARTMENT_LABELS: Record<MiddleAgentType, string> = {
  market_research: "市场调研",
  competitor_analysis: "竞品分析",
  product_design: "产品设计",
  future_direction: "未来方向",
  change_plan: "当下改变",
};

// =============================================================================
// CEO 最终报告
// =============================================================================

/** 跨部门交叉洞察（对应后端 CrossInsight） */
export interface CrossInsight {
  title: string;
  insight: string;
  involved_dimensions: string[];
  confidence: number;
}

/** 战略建议（对应后端 Recommendation） */
export interface Recommendation {
  priority: number;
  title: string;
  rationale: string;
  related_dimensions: string[];
}

/** 风险标记（对应后端 RiskFlag） */
export interface RiskFlag {
  severity: Severity;
  title: string;
  description: string;
  related_dimension: string;
}

/** CEO 最终报告（对应后端 FinalReport） */
export interface FinalReport {
  executive_summary: string;
  department_summaries: Record<string, string>;
  overall_score: number;
  cross_insights: CrossInsight[];
  recommendations: Recommendation[];
  risks: RiskFlag[];
  dimension_confidence: Record<string, number>;
}

// =============================================================================
// SSE 事件 ——  discriminated union
// 每个 event_type 对应不同 data 形状，消费时 TS 自动收窄类型
// =============================================================================

/** 顶层规划产出 */
export interface PlanGeneratedEvent {
  event_type: "plan_generated";
  timestamp: string;
  message: string;
  phase: string | null;
  department: null;
  agent_id: null;
  data: {
    task_count: number;
    skipped_count: number;
    /** key = agent_type, value = focus_areas (后端以 dict 而非数组发送) */
    tasks: Record<string, string[]>;
    skipped: string[];
  };
  call_count: number;
}

/** LLM 调用计数更新 */
export interface BudgetUpdateEvent {
  event_type: "budget_update";
  timestamp: string;
  message: string;
  phase: string | null;
  department: null;
  agent_id: null;
  data: {
    total_calls: number;
    max_calls: number;
  };
  call_count: number;
}

/** 中层部门启动 */
export interface DepartmentStartEvent {
  event_type: "department_start";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: null;
  data: {
    focus_areas: string[];
  };
  call_count: number;
}

/** 中层部门跳过 */
export interface DepartmentSkipEvent {
  event_type: "department_skip";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: null;
  data: {
    reason: string;
  };
  call_count: number;
}

/** 底层搜索启动 */
export interface SubAgentStartEvent {
  event_type: "sub_agent_start";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: string;
  data: {
    search_query: string;
  };
  call_count: number;
}

/** Tavily 搜索完成 */
export interface SubAgentSearchEvent {
  event_type: "sub_agent_search";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: string;
  data: {
    result_count: number;
  };
  call_count: number;
}

/** 底层 LLM 筛选分析完成 */
export interface SubAgentDoneEvent {
  event_type: "sub_agent_done";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: string;
  data: {
    report_summary: string;
    findings_count: number;
  };
  call_count: number;
}

/** 审核结果 */
export interface SubAgentReviewEvent {
  event_type: "sub_agent_review";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: string;
  data: {
    verdict: "passed" | "rejected";
    overall_score: number;
    credibility: number;
    reason: string;
  };
  call_count: number;
}

/** 部门综合分析完成 */
export interface DepartmentDoneEvent {
  event_type: "department_done";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string;
  agent_id: null;
  data: {
    summary: string;
    key_points_count: number;
    overall_confidence: number;
    status: string;
  };
  call_count: number;
}

/** CEO 综合报告 */
export interface FinalReportEvent {
  event_type: "final_report";
  timestamp: string;
  message: string;
  phase: string | null;
  department: null;
  agent_id: null;
  data: FinalReport;
  call_count: number;
}

/** 非致命错误 */
export interface ErrorEvent {
  event_type: "error";
  timestamp: string;
  message: string;
  phase: string | null;
  department: string | null;
  agent_id: string | null;
  data: {
    error: string;
  };
  call_count: number;
}

/** 流结束 */
export interface DoneEvent {
  event_type: "done";
  timestamp: string;
  message: string;
  phase: string | null;
  department: null;
  agent_id: null;
  data: Record<string, never>;
  call_count: number;
}

/** 所有 SSE 事件的联合类型 */
export type SSEEvent =
  | PlanGeneratedEvent
  | BudgetUpdateEvent
  | DepartmentStartEvent
  | DepartmentSkipEvent
  | SubAgentStartEvent
  | SubAgentSearchEvent
  | SubAgentDoneEvent
  | SubAgentReviewEvent
  | DepartmentDoneEvent
  | FinalReportEvent
  | ErrorEvent
  | DoneEvent;

/** GET /analyze/{thread_id} 返回的快照 */
export interface AnalyzeSnapshot {
  events: SSEEvent[];
  final_report: FinalReport | null;
}
