import type { HistoryRecord } from "@/types/history";
import HistoryRow from "@/components/HistoryRow";

/* =============================================================================
   硬编码演示数据（开发期占位，后续替换为 API 请求）
   ============================================================================= */

const DEMO_RECORDS: HistoryRecord[] = [
  {
    id: "demo-1",
    projectDescription:
      "我想做一个宠物社交App，连接同城的宠物主人，提供遛狗约玩、宠物寄养、社区分享功能",
    createdAt: "2026-06-28T10:30:00Z",
    overallScore: 78,
    dimensionConfidence: {
      market_research: 0.82,
      competitor_analysis: 0.61,
      product_design: 0.74,
      future_direction: 0.68,
      change_plan: 0.55,
    },
    executiveSummary:
      "宠物社交市场处于高速增长期，2025年中国宠物经济规模突破3000亿元，年复合增长率18%。" +
      "同城社交+服务平台这一细分赛道尚无头部产品，存在明确的市场空白。建议优先在一二线城市冷启动，" +
      "以遛狗约玩作为钩子功能，寄养和社区为变现点。竞品方面，小红书宠物板块和宠物家是间接竞品，" +
      "但均未覆盖「同城即时约玩」这一核心场景。产品设计上建议采用LBS+兴趣图谱双驱动模型。",
    callCount: 14,
    departmentCount: 5,
    rejectionRounds: 2,
  },
  {
    id: "demo-2",
    projectDescription:
      "做一个面向职场新人的在线技能教育平台，主打项目实战+导师1v1反馈",
    createdAt: "2026-06-27T14:20:00Z",
    overallScore: 52,
    dimensionConfidence: {
      market_research: 0.71,
      competitor_analysis: 0.43,
      product_design: 0.58,
      future_direction: 0.45,
      change_plan: 0.39,
    },
    executiveSummary:
      "在线教育赛道竞争激烈，已有腾讯课堂、网易云课堂、慕课网等成熟平台。" +
      "但面向「0-2年职场新人+项目实战+导师反馈」的精细化定位仍有差异化空间。" +
      "市场数据显示，职场新人为技能提升的年均付费意愿在2000-5000元，目标人群约1200万。" +
      "最大风险在于竞品密度极高，且用户获取成本持续攀升。建议与B端企业合作（企业培训预算）" +
      "作为突破口，避免纯C端流量的红海竞争。产品设计上弱化「课程」概念，强化「项目经历」导向。",
    callCount: 12,
    departmentCount: 4,
    rejectionRounds: 3,
  },
];

/* =============================================================================
   页面
   ============================================================================= */

export default function HistoryPage() {
  const hasRecords = DEMO_RECORDS.length > 0;

  return (
    <div className="flex flex-col min-h-full max-w-[860px] mx-auto w-full px-8 py-10">
      {/* ---- 页头 ---- */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-bamboo-800 tracking-tight mb-1">
            历史记录
          </h1>
          <p className="text-sm text-bamboo-500">
            {hasRecords
              ? `共 ${DEMO_RECORDS.length} 条分析记录`
              : "查看过往的项目分析记录"}
          </p>
        </div>

        {/* 工具栏 */}
        {hasRecords && (
          <div className="flex items-center gap-2">
            {/* 搜索框（装饰，暂不可用） */}
            <div className="relative">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 text-bamboo-400"
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              >
                <circle cx="6" cy="6" r="4.5" />
                <line x1="9.5" y1="9.5" x2="12.5" y2="12.5" />
              </svg>
              <input
                type="text"
                placeholder="搜索..."
                className="
                  w-44 pl-8 pr-3 py-1.5
                  rounded-lg border border-bamboo-200
                  text-xs text-bamboo-800 placeholder-bamboo-400
                  bg-white outline-none
                  focus:border-accent focus:ring-2 focus:ring-accent/10
                  transition-shadow
                "
              />
            </div>

            {/* 排序（装饰） */}
            <select className="
              px-3 py-1.5 rounded-lg
              border border-bamboo-200 bg-white
              text-xs text-bamboo-600
              outline-none cursor-pointer
              focus:border-accent
            ">
              <option>最新优先</option>
              <option>评分最高</option>
              <option>评分最低</option>
            </select>
          </div>
        )}
      </div>

      {/* ---- 列表 / 空状态 ---- */}
      {hasRecords ? (
        <div className="pt-2">
          {DEMO_RECORDS.map((record, i) => (
            <HistoryRow
              key={record.id}
              record={record}
              isLast={i === DEMO_RECORDS.length - 1}
            />
          ))}
        </div>
      ) : (
        /* 空状态 */
        <div className="flex flex-col items-center justify-center flex-1 py-20">
          <div className="w-14 h-14 mb-4 rounded-2xl bg-bamboo-100 flex items-center justify-center">
            <svg
              width="24"
              height="24"
              viewBox="0 0 18 18"
              fill="none"
              stroke="#8AA597"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="9" cy="9" r="7.2" />
              <polyline points="9,4.5 9,9 12.6,10.8" />
            </svg>
          </div>
          <p className="text-sm text-bamboo-400">暂无分析记录</p>
          <p className="text-xs text-bamboo-400/70 mt-1">
            完成一次分析后，记录将显示在这里
          </p>
        </div>
      )}

      {/* ---- 底部提示 ---- */}
      <p className="mt-8 text-xs text-center text-bamboo-400/70">
        演示数据 · 后续将从后端 API 拉取真实记录
      </p>
    </div>
  );
}
