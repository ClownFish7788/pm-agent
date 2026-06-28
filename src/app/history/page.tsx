export default function HistoryPage() {
  return (
    <div className="flex flex-col min-h-full px-8 py-10 max-w-[720px] mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-bamboo-800 tracking-tight mb-1">
          历史记录
        </h1>
        <p className="text-sm text-bamboo-500">
          查看过往的项目分析记录，点击可进入报告详情或 Agent 协作回放。
        </p>
      </div>

      {/* 空状态 */}
      <div className="flex flex-col items-center justify-center flex-1 py-20">
        <div className="w-14 h-14 mb-4 rounded-2xl bg-bamboo-100 flex items-center justify-center">
          <svg width="24" height="24" viewBox="0 0 18 18" fill="none" stroke="#8AA597" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="9" cy="9" r="7.2" />
            <polyline points="9,4.5 9,9 12.6,10.8" />
          </svg>
        </div>
        <p className="text-sm text-bamboo-400">暂无分析记录</p>
        <p className="text-xs text-bamboo-400/70 mt-1">完成一次分析后，记录将显示在这里</p>
      </div>
    </div>
  );
}
