export default function SkillsPage() {
  return (
    <div className="flex flex-col min-h-full px-8 py-10 max-w-[720px] mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-bamboo-800 tracking-tight mb-1">
          Skills
        </h1>
        <p className="text-sm text-bamboo-500">
          自定义 Skill 或从社区引入，扩展大模型的能力边界。
        </p>
      </div>

      {/* 空状态 */}
      <div className="flex flex-col items-center justify-center flex-1 py-20">
        <div className="w-14 h-14 mb-4 rounded-2xl bg-bamboo-100 flex items-center justify-center">
          <svg width="24" height="24" viewBox="0 0 18 18" fill="none" stroke="#8AA597" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M8.1 2.14L3.06 5.04V10.84L8.1 13.74L13.14 10.84V5.04L8.1 2.14Z" />
            <circle cx="8.1" cy="7.9" r="1.5" />
            <path d="M4.5 6.5L8.1 8.5L11.7 6.5" />
          </svg>
        </div>
        <p className="text-sm text-bamboo-400">暂无自定义 Skill</p>
        <p className="text-xs text-bamboo-400/70 mt-1">
          你可以创建 Skill 来定义特定的分析逻辑或引入社区 Skill
        </p>

        {/* 预留按钮 */}
        <button className="mt-5 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors cursor-pointer">
          + 创建 Skill
        </button>
      </div>
    </div>
  );
}
