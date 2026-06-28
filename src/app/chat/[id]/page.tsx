export default function ChatPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
      <div className="max-w-[680px] w-full mx-auto text-center">
        {/* 占位图标 */}
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-accent-subtle flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 18 18" fill="none" stroke="#219C5B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.4 3.6H3.6C2.61 3.6 1.8 4.41 1.8 5.4V10.8C1.8 11.79 2.61 12.6 3.6 12.6H5.4V16.2L9 12.6H14.4C15.39 12.6 16.2 11.79 16.2 10.8V5.4C16.2 4.41 15.39 3.6 14.4 3.6Z" />
          </svg>
        </div>

        <h1 className="text-xl font-semibold text-bamboo-800 mb-2 tracking-tight">
          Agent 协作过程
        </h1>
        <p className="text-sm text-bamboo-500 leading-relaxed">
          这里将展示各 Agent 的实时协作过程——从顶层规划到中层执行，
          <br />
          你可以看到每个部门的搜索进度、审核结果和发现输出。
        </p>

        {/* 流程示意 */}
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-bamboo-400">
          <span className="px-3 py-1.5 rounded-lg bg-bamboo-100 border border-bamboo-200">顶层规划</span>
          <span>→</span>
          <span className="px-3 py-1.5 rounded-lg bg-bamboo-100 border border-bamboo-200">5 部门并行</span>
          <span>→</span>
          <span className="px-3 py-1.5 rounded-lg bg-bamboo-100 border border-bamboo-200">审核驳回</span>
          <span>→</span>
          <span className="px-3 py-1.5 rounded-lg bg-bamboo-100 border border-bamboo-200">CEO 汇总</span>
        </div>
      </div>
    </div>
  );
}
