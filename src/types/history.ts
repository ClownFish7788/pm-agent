/**
 * 历史记录相关类型定义。
 * 与后端 Pydantic schemas/__init__.py 保持松散对应。
 */

/** 单条历史记录（列表展示用） */
export interface HistoryRecord {
  id: string;
  /** 用户原始项目描述 */
  projectDescription: string;
  /** 分析完成时间 (ISO 8601) */
  createdAt: string;
  /** 综合评分 0-100 */
  overallScore: number;
  /** 各部门可信度，key = 部门标识 */
  dimensionConfidence: Record<string, number>;
  /** 执行摘要（≤800字），列表展示时截断 */
  executiveSummary: string;
  /** LLM API 调用总次数 */
  callCount: number;
  /** 参与分析的中层部门数 */
  departmentCount: number;
  /** 驳回总轮次 */
  rejectionRounds: number;
}

/** 部门中文名映射 */
export const DEPARTMENT_LABELS: Record<string, string> = {
  market_research: "市场调研",
  competitor_analysis: "竞品分析",
  product_design: "产品设计",
  future_direction: "未来方向",
  change_plan: "当下改变",
};

/** 评分颜色：绿 ≥70 / 黄 40-69 / 红 <40 */
export function scoreColor(score: number): string {
  if (score >= 70) return "#219C5B";
  if (score >= 40) return "#C88C18";
  return "#D14343";
}

export function scoreLabel(score: number): string {
  if (score >= 70) return "良好";
  if (score >= 40) return "一般";
  return "偏低";
}
