/**
 * Skill 类型定义。
 *
 * 一个 Skill = 名字 + 分类 + 多个 .md 文件。
 */

export type SkillCategory =
  | "market"
  | "competitor"
  | "product"
  | "future"
  | "change"
  | "global";

export const SKILL_CATEGORIES: { value: SkillCategory; label: string }[] = [
  { value: "market", label: "市场调研" },
  { value: "competitor", label: "竞品分析" },
  { value: "product", label: "产品设计" },
  { value: "future", label: "未来方向" },
  { value: "change", label: "当下改变" },
  { value: "global", label: "全局通用" },
];

export const CATEGORY_LABEL: Record<SkillCategory, string> = {
  market: "市场调研",
  competitor: "竞品分析",
  product: "产品设计",
  future: "未来方向",
  change: "当下改变",
  global: "全局通用",
};

/** 单个 .md 文件 */
export interface SkillFile {
  /** 文件名（如 "竞品对比.md"） */
  name: string;
  /** 文件内容（原始 markdown） */
  content: string;
}

/** 一个 Skill */
export interface Skill {
  id: string;
  name: string;
  category: SkillCategory;
  files: SkillFile[];
  createdAt: string;
}
