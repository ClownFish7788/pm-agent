/**
 * 硬编码模拟数据 —— 模拟一次完整分析的中途状态。
 *
 * 场景：宠物社交App 分析，5 个部门中 1 个完成、2 个运行中、
 * 1 个等待、1 个跳过。其中 SearchAgent #2 经历过 1 次驳回重试。
 */

import type { AnalysisState } from "@/types/analysis";

export const MOCK_ANALYSIS: AnalysisState = {
  phase: "executing",
  callCount: 14,
  maxCalls: 30,
  finalReport: null,
  errors: [],

  /* ---- CEO 执行计划 ---- */
  plan: {
    taskCount: 5,
    skippedCount: 1,
    tasks: [
      {
        department: "market_research",
        label: "市场调研",
        focusAreas: ["宠物社交市场规模", "养宠用户画像", "商业模式与变现"],
        status: "completed",
      },
      {
        department: "competitor_analysis",
        label: "竞品分析",
        focusAreas: ["直接竞品功能对比", "间接替代品威胁"],
        status: "running",
      },
      {
        department: "product_design",
        label: "产品设计",
        focusAreas: ["核心功能 MVP", "用户体验差异化"],
        status: "running",
      },
      {
        department: "future_direction",
        label: "未来方向",
        focusAreas: ["技术趋势", "市场长期演变"],
        status: "pending",
      },
      {
        department: "change_plan",
        label: "当下改变",
        focusAreas: ["近期可执行优化"],
        status: "skipped",
      },
    ],
  },

  /* ---- 各部门状态 ---- */
  departments: {
    // =========================================================================
    // 市场调研 —— 已完成，2 个 SearchAgent，其中 #2 经历过 1 次驳回重试
    // =========================================================================
    market_research: {
      label: "市场调研",
      focusAreas: ["宠物社交市场规模", "养宠用户画像", "商业模式与变现"],
      status: "completed",
      summary:
        "中国宠物经济 2025 年规模突破 3000 亿元，年复合增长 18%。" +
        "同城社交+服务平台尚无头部产品，一二线城市宠物主年均消费 5000-8000 元。" +
        "遛狗约玩和宠物寄养是最高频需求场景。",
      confidence: 0.82,
      keyPointsCount: 5,
      subAgents: [
        {
          id: "market_query_1",
          status: "passed",
          rounds: [
            {
              round: 1,
              searchQuery: "宠物社交App 市场规模 2025 2026",
              resultCount: 8,
              findingsCount: 5,
              reportSummary:
                "中国宠物经济规模突破3000亿元，年增长18%。宠物社交类App渗透率不足15%，" +
                "市场空白明显。一二线城市宠物主为社交需求的付费意愿强烈。",
              review: {
                verdict: "passed",
                overallScore: 7.2,
                credibility: 8.0,
                reason: "引用《2025中国宠物行业白皮书》和艾瑞咨询数据，来源权威",
              },
            },
          ],
        },
        {
          id: "market_query_2",
          status: "passed",
          rounds: [
            {
              round: 1,
              searchQuery: "养宠用户画像 中国市场 2025",
              resultCount: 6,
              findingsCount: 4,
              reportSummary: "",
              review: {
                verdict: "rejected",
                overallScore: 4.5,
                credibility: 3.2,
                reason: "来源均为个人博客和论坛帖子，缺乏权威数据支撑",
              },
            },
            {
              round: 2,
              searchQuery: "宠物App用户画像 行业报告 2025",
              resultCount: 5,
              findingsCount: 4,
              reportSummary:
                "养宠人群以25-35岁女性为主（占62%），一二线城市占比78%。" +
                "核心诉求：遛狗约玩(73%)、宠物寄养(58%)、养宠知识(45%)。",
              review: {
                verdict: "passed",
                overallScore: 6.8,
                credibility: 7.5,
                reason: "改用行业报告和QuestMobile数据，可信度达标",
              },
            },
          ],
        },
      ],
    },

    // =========================================================================
    // 竞品分析 —— 运行中，1 个 SearchAgent 刚搜完
    // =========================================================================
    competitor_analysis: {
      label: "竞品分析",
      focusAreas: ["直接竞品功能对比", "间接替代品威胁"],
      status: "running",
      summary: "",
      confidence: 0,
      keyPointsCount: 0,
      subAgents: [
        {
          id: "competitor_query_1",
          status: "analyzing",
          rounds: [
            {
              round: 1,
              searchQuery: "宠物社交App 竞品 功能对比 2025",
              resultCount: 7,
              findingsCount: null,
              reportSummary: null,
              review: null,
            },
          ],
        },
        {
          id: "competitor_query_2",
          status: "searching",
          rounds: [
            {
              round: 1,
              searchQuery: "宠物服务 替代品 小红书 宠物家",
              resultCount: null,
              findingsCount: null,
              reportSummary: null,
              review: null,
            },
          ],
        },
      ],
    },

    // =========================================================================
    // 产品设计 —— 运行中，1 个 SearchAgent 正在审核
    // =========================================================================
    product_design: {
      label: "产品设计",
      focusAreas: ["核心功能 MVP", "用户体验差异化"],
      status: "running",
      summary: "",
      confidence: 0,
      keyPointsCount: 0,
      subAgents: [
        {
          id: "product_query_1",
          status: "passed",
          rounds: [
            {
              round: 1,
              searchQuery: "宠物App 核心功能 产品设计",
              resultCount: 6,
              findingsCount: 5,
              reportSummary:
                "高频功能排序：LBS遛狗约玩 > 社区分享 > 宠物寄养 > 在线问诊。" +
                "差异化机会在「即时匹配」和「信任体系」两个维度。",
              review: {
                verdict: "passed",
                overallScore: 7.5,
                credibility: 8.2,
                reason: "多源交叉验证，数据一致性好",
              },
            },
          ],
        },
      ],
    },

    // =========================================================================
    // 未来方向 —— 等待中
    // =========================================================================
    future_direction: {
      label: "未来方向",
      focusAreas: ["技术趋势", "市场长期演变"],
      status: "pending",
      summary: "",
      confidence: 0,
      keyPointsCount: 0,
      subAgents: [],
    },

    // =========================================================================
    // 当下改变 —— 被跳过
    // =========================================================================
    change_plan: {
      label: "当下改变",
      focusAreas: ["近期可执行优化"],
      status: "skipped",
      summary: "",
      confidence: 0,
      keyPointsCount: 0,
      subAgents: [],
    },
  },
};
