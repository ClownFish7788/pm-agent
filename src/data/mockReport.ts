/**
 * Mock 报告数据 —— 模拟一次完整的 CEO 综合分析报告。
 * 开发期占位，后续从 reportStore 读取真实数据。
 */

import type { FinalReport } from "@/types/schemas";

export const MOCK_REPORT: FinalReport = {
  executive_summary:
    "宠物社交App项目综合可行性评分76分。市场空间明确（3000亿+宠物经济），" +
    "同城即时约玩这一细分场景尚无头部竞品，存在明确的市场空白。" +
    "建议以一二线城市为切入点，以LBS遛狗约玩为核心钩子功能，" +
    "社区内容+宠物寄养为变现引擎。最大风险在于用户冷启动和信任体系构建，" +
    "需要在种子用户运营和宠物档案信任机制上投入足够资源。",

  department_summaries: {
    market_research:
      "中国宠物经济2025年规模突破3000亿元，年复合增长18%。" +
      "宠物社交类App渗透率不足15%，同城社交+服务平台尚无头部产品。" +
      "一二线城市宠物主年均消费5000-8000元，遛狗约玩和宠物寄养是最高频需求。",
    competitor_analysis:
      "直接竞品：小红书宠物板块（MAU 800万）、宠物家（200万），" +
      "但均未覆盖「同城即时约玩」这一核心场景。间接替代品包括美团宠物频道和闲鱼宠物板块。" +
      "差异化关键在于「即时匹配」和「信任体系」两个维度。",
    product_design:
      "MVP应聚焦LBS遛狗约玩作为钩子功能，社区+寄养为变现引擎。" +
      "差异化机会在信任体系建设——宠物档案、实名认证、双向评价系统是长期竞争壁垒。" +
      "建议在MVP阶段就纳入信任体系，而非V2再补。",
    future_direction:
      "AI宠物健康监测、智能喂食器、宠物可穿戴设备是未来3年技术热点。" +
      "银发+宠物（老年人养宠）是长期增量市场。" +
      "建议在产品架构中预留硬件对接API，为宠物数字身份生态做准备。",
    change_plan: "该部门本轮被跳过——MVP阶段尚未进入执行优化周期。",
  },

  overall_score: 76,

  cross_insights: [
    {
      title: "市场×竞品：空白窗口期有限",
      insight:
        "市场调研确认了同城约玩的需求强度（73%宠物主有此需求），" +
        "竞品分析确认无头部产品覆盖——这个窗口期预计12-18个月，" +
        "小红书或美团宠物频道可能随时进入。建议以最快速度验证PMF并建立用户壁垒。",
      involved_dimensions: ["market_research", "competitor_analysis"],
      confidence: 0.78,
    },
    {
      title: "产品×未来：信任数据是长期壁垒",
      insight:
        "产品设计的信任体系（实名+评价+宠物档案）和未来方向的AI硬件，" +
        "二者结合可构建「宠物数字身份」——这是竞品难以短期复制的数据壁垒。" +
        "宠物数字身份可延伸至宠物保险、宠物医疗等增值服务。",
      involved_dimensions: ["product_design", "future_direction"],
      confidence: 0.65,
    },
    {
      title: "市场×产品：冷启动存在双边网络困局",
      insight:
        "社交产品面临双边网络效应：0用户时匹配率低→留存差→负循环。" +
        "产品设计建议引入「AI虚拟遛狗搭子」作为冷启动期的单人体验，" +
        "降低初期用户对匹配率的依赖。",
      involved_dimensions: ["market_research", "product_design"],
      confidence: 0.60,
    },
  ],

  recommendations: [
    {
      priority: 1,
      title: "一二线城市冷启动，单点打透",
      rationale:
        "选择上海或成都作为首发城市，用3个月验证「遛狗约玩」的PMF。" +
        "集中资源在单个城市达到临界密度（约需5000活跃用户），跑通后再复制。",
      related_dimensions: ["market_research", "competitor_analysis"],
    },
    {
      priority: 2,
      title: "MVP优先建立信任体系",
      rationale:
        "宠物档案+实名认证+双向评价系统是长期壁垒。" +
        "建议在MVP阶段就纳入（而非V2再补），因为信任数据需要时间积累。",
      related_dimensions: ["product_design"],
    },
    {
      priority: 3,
      title: "与宠物医院/宠物店合作获客",
      rationale:
        "线下宠物场景是低成本获客渠道。可与连锁宠物医院谈合作，" +
        "以「宠物电子健康档案」为切入点，B端付费+C端免费模式。",
      related_dimensions: ["market_research", "product_design"],
    },
    {
      priority: 4,
      title: "预留AI硬件对接能力",
      rationale:
        "智能宠物硬件（项圈、喂食器）是3年内的大趋势。" +
        "建议在v1.5版本开放宠物健康数据API，吸引硬件厂商接入。",
      related_dimensions: ["future_direction"],
    },
  ],

  risks: [
    {
      severity: "medium",
      title: "用户冷启动难度大",
      description:
        "社交产品双边网络效应，0用户时匹配率低→留存差→负循环。" +
        "需要种子用户运营策略和AI虚拟搭子等过渡方案。",
      related_dimension: "market_research",
    },
    {
      severity: "medium",
      title: "小红书/美团潜在进入威胁",
      description:
        "这些平台具备流量+社交基因，一旦开通宠物同城功能，将对独立App形成降维打击。" +
        "窗口期有限，需要在12-18个月内建立用户壁垒。",
      related_dimension: "competitor_analysis",
    },
    {
      severity: "low",
      title: "宠物寄养责任边界模糊",
      description:
        "P2P寄养涉及宠物安全和法律纠纷风险。" +
        "需在服务条款和保险机制上提前设计，避免早期法律问题拖累产品节奏。",
      related_dimension: "product_design",
    },
  ],

  dimension_confidence: {
    market_research: 0.82,
    competitor_analysis: 0.65,
    product_design: 0.78,
    future_direction: 0.70,
  },
};
