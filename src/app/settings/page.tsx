export default function SettingsPage() {
  return (
    <div className="flex flex-col min-h-full px-8 py-10 max-w-[720px] mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-bamboo-800 tracking-tight mb-1">
          设置
        </h1>
        <p className="text-sm text-bamboo-500">
          配置 API Key、模型偏好和系统参数。
        </p>
      </div>

      {/* 设置项占位 */}
      <div className="space-y-4">
        {[
          { label: "API Key", desc: "DeepSeek API 密钥", value: "••••••••••••••••" },
          { label: "搜索服务", desc: "Tavily Search API Key", value: "••••••••••••••••" },
          { label: "模型选择", desc: "当前使用", value: "deepseek-chat" },
          { label: "最大调用次数", desc: "单次分析 LLM 调用上限", value: "30" },
        ].map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between px-4 py-3 rounded-xl bg-white border border-bamboo-200"
          >
            <div>
              <div className="text-sm font-medium text-bamboo-800">{item.label}</div>
              <div className="text-xs text-bamboo-400 mt-0.5">{item.desc}</div>
            </div>
            <div className="text-sm text-bamboo-500 font-mono">{item.value}</div>
          </div>
        ))}
      </div>

      <p className="mt-6 text-xs text-bamboo-400 text-center">
        更多设置项将在后续版本中开放（Toast/Modal 形式的快捷设置也在计划中）
      </p>
    </div>
  );
}
