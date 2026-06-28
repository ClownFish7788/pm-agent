export default function ReportPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
      <div className="max-w-[680px] w-full mx-auto text-center">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-accent-subtle flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 18 18" fill="none" stroke="#219C5B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2.5" y="1.5" width="13" height="15" rx="2" />
            <line x1="5.5" y1="5" x2="12.5" y2="5" />
            <line x1="5.5" y1="8" x2="12.5" y2="8" />
            <line x1="5.5" y1="11" x2="9.5" y2="11" />
          </svg>
        </div>

        <h1 className="text-xl font-semibold text-bamboo-800 mb-2 tracking-tight">
          分析报告
        </h1>
        <p className="text-sm text-bamboo-500 leading-relaxed">
          完整的结构化分析看板——执行摘要、部门结论、交叉洞察、
          <br />
          战略建议和风险评估，支持 MD/PDF 导出。
        </p>

        {/* 报告结构预览 */}
        <div className="mt-8 grid grid-cols-2 gap-2 max-w-[400px] mx-auto">
          {["执行摘要", "市场调研", "竞品分析", "产品设计", "交叉洞察", "战略建议"].map((item) => (
            <div
              key={item}
              className="px-3 py-2 rounded-lg text-xs text-bamboo-600 bg-bamboo-50 border border-bamboo-200 text-center"
            >
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
