"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { analysisSession } from "@/stores/analysisSession";

/* --------------------------------------------------------------------------- */
/* 快捷建议项                                                                   */
/* --------------------------------------------------------------------------- */

const SUGGESTIONS = [
  { label: "宠物社交App", prompt: "我想做一个宠物社交App，连接同城的宠物主人，提供遛狗约玩、宠物寄养、社区分享功能" },
  { label: "在线教育平台", prompt: "做一个面向职场新人的在线技能教育平台，主打项目实战+导师1v1反馈" },
  { label: "智能家居方案", prompt: "智能家居一站式解决方案，包括硬件选型、安装服务和售后支持" },
  { label: "跨境独立站", prompt: "帮中小工厂搭建跨境电商独立站，集成支付、物流和AI客服" },
];

/* --------------------------------------------------------------------------- */
/* 组件                                                                        */
/* --------------------------------------------------------------------------- */

export default function ChatInput() {
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const router = useRouter();

  // 如果用户从 Chat 页返回首页，session 已结束 → 重置 submitting
  useEffect(() => {
    if (!analysisSession.isActive) {
      setSubmitting(false);
    }
  }, []);

  /* ---- 自动调整高度 ---- */
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    autoResize();
  };

  /* ---- 快捷建议点击 ---- */
  const handleSuggestion = (prompt: string) => {
    setValue(prompt);
    // 等 state 更新后调整高度
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        autoResize();
      }
    });
  };

  /* ---- 提交 ---- */
  const handleSubmit = useCallback(() => {
    const description = value.trim();
    if (!description || submitting) return;

    setSubmitting(true);

    // 启动 SSE 会话（独立于 React 生命周期）
    analysisSession.start("/api/analyze/stream", { description });

    // URL 只放路由 ID，description 存在 analysisSession 里
    const id = Date.now().toString(36);
    router.push(`/chat/${id}`);
  }, [value, submitting, router]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter 提交，Shift+Enter 换行
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSubmit = value.trim().length > 0 && !submitting;

  return (
    <div className="w-full max-w-[680px] mx-auto">
      {/* ---- 输入区域 ---- */}
      <div
        className={`
          input-glow
          flex flex-col
          bg-white
          border border-bamboo-200
          rounded-2xl
          transition-shadow duration-200
          overflow-hidden
        `}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="描述你的项目想法，比如目标市场、核心功能、预算范围..."
          rows={3}
          className="
            w-full resize-none
            px-5 pt-4 pb-2
            text-[15px] leading-relaxed
            text-bamboo-800
            placeholder:text-bamboo-400
            bg-transparent
            outline-none
            border-none
          "
        />

        {/* ---- 底部操作栏 ---- */}
        <div className="flex items-center justify-between px-3 pb-3">
          <span className="text-xs text-bamboo-400 pl-2 select-none">
            Shift + Enter 换行
          </span>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`
              flex items-center gap-1.5
              px-4 py-1.5 rounded-xl
              text-sm font-medium
              transition-all duration-150
              ${
                canSubmit
                  ? "bg-accent text-white hover:bg-accent-hover cursor-pointer active:scale-[0.97]"
                  : "bg-bamboo-200 text-bamboo-400 cursor-not-allowed"
              }
            `}
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 7.5L13 2L10 13L7.5 10L5.5 12.5V9.5L10 5L6 9L2 7.5Z" />
            </svg>
            开始分析
          </button>
        </div>
      </div>

      {/* ---- 快捷建议 ---- */}
      <div className="flex flex-wrap items-center gap-2 mt-4 px-1">
        <span className="text-xs text-bamboo-400 mr-1">或试试这些 →</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            onClick={() => handleSuggestion(s.prompt)}
            className="
              suggestion-chip
              px-3 py-1.5
              rounded-full
              text-xs text-bamboo-600
              bg-white
              border border-bamboo-200
              cursor-pointer
            "
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
