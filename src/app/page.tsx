import Greeting from "@/components/Greeting";
import ChatInput from "@/components/ChatInput";

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-8 py-12">
      {/* 问候 + 光晕 */}
      <div className="mb-10 text-center">
        <Greeting />
      </div>

      {/* 输入框 + 建议 */}
      <ChatInput />

      {/* 底部提示 */}
      <p className="mt-10 text-xs text-bamboo-400 text-center">
        PM Agent 会通过多轮 Agent 协作，帮你完成市场调研、竞品分析、产品设计和风险评估
      </p>
    </div>
  );
}
