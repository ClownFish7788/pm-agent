"use client";

/* --------------------------------------------------------------------------- */
/* 按小时计算问候语                                                             */
/* --------------------------------------------------------------------------- */

interface GreetingData {
  greeting: string;
  subtitle: string;
  isEvening: boolean;
}

function getGreeting(): GreetingData {
  const hour = new Date().getHours();

  if (hour >= 5 && hour < 12) {
    return {
      greeting: "早上好",
      subtitle: "新的一天，准备好探索产品想法了吗？",
      isEvening: false,
    };
  }

  if (hour >= 12 && hour < 18) {
    return {
      greeting: "中午好",
      subtitle: "午后时光，来梳理一下你的产品思路吧。",
      isEvening: false,
    };
  }

  return {
    greeting: "晚上好",
    subtitle: "夜深了，正是深度思考的好时候。",
    isEvening: true,
  };
}

/* --------------------------------------------------------------------------- */
/* 组件                                                                        */
/* --------------------------------------------------------------------------- */

export default function Greeting() {
  const { greeting, subtitle, isEvening } = getGreeting();

  return (
    <div className={`greeting-glow relative z-10 ${isEvening ? "evening" : ""}`}>
      {/* 日期 */}
      <p className="text-sm text-bamboo-400 mb-3 tracking-wide">
        {new Date().toLocaleDateString("zh-CN", {
          year: "numeric",
          month: "long",
          day: "numeric",
          weekday: "long",
        })}
      </p>

      {/* 问候语 */}
      <h1
        className="text-[38px] font-bold tracking-tight text-bamboo-800 mb-3 leading-tight"
        style={{ fontFamily: "var(--font-geist-sans)" }}
      >
        {greeting}，<span className="text-accent">彭添豪</span>
      </h1>

      {/* 副标题 */}
      <p className="text-bamboo-500 text-[16px] leading-relaxed">
        {subtitle}
      </p>
    </div>
  );
}
