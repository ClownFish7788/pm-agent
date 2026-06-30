"use client";

/**
 * Skill 查看 Modal —— 只读，展示所有文件内容。
 * 暂不支持编辑。
 */

import { useState } from "react";
import { createPortal } from "react-dom";
import type { Skill } from "@/types/skill";
import { CATEGORY_LABEL } from "@/types/skill";

interface SkillViewModalProps {
  skill: Skill | null;
  onClose: () => void;
}

export default function SkillViewModal({ skill, onClose }: SkillViewModalProps) {
  const [activeFileIdx, setActiveFileIdx] = useState(0);

  // ESC
  if (typeof window !== "undefined") {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey, { once: true });
  }

  if (!skill) return null;

  const file = skill.files[activeFileIdx];

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="
          w-full max-w-[640px] max-h-[85vh] mx-4
          bg-white rounded-2xl border border-bamboo-200
          shadow-xl shadow-bamboo-800/5
          flex flex-col
        "
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-bamboo-100 shrink-0">
          <div>
            <h2 className="text-[15px] font-semibold text-bamboo-800">
              {skill.name}
            </h2>
            <span className="text-[10px] text-bamboo-400 bg-bamboo-50 px-2 py-0.5 rounded-full">
              {CATEGORY_LABEL[skill.category]}
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-bamboo-400 hover:text-bamboo-600 hover:bg-bamboo-50 transition-colors cursor-pointer"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="2" y1="2" x2="12" y2="12" />
              <line x1="12" y1="2" x2="2" y2="12" />
            </svg>
          </button>
        </div>

        {/* 文件 tab 栏 */}
        {skill.files.length > 1 && (
          <div className="flex gap-1 px-5 pt-3 pb-1 overflow-x-auto shrink-0">
            {skill.files.map((f, i) => (
              <button
                key={i}
                onClick={() => setActiveFileIdx(i)}
                className={`
                  px-3 py-1.5 rounded-t-lg text-xs whitespace-nowrap
                  transition-colors cursor-pointer
                  ${
                    i === activeFileIdx
                      ? "bg-white text-bamboo-800 font-medium border border-bamboo-200 border-b-white"
                      : "text-bamboo-400 hover:text-bamboo-600 hover:bg-bamboo-50"
                  }
                `}
              >
                {f.name}
              </button>
            ))}
          </div>
        )}

        {/* 文件内容 */}
        <div className="flex-1 overflow-y-auto p-5">
          {file ? (
            <div>
              <p className="text-[11px] text-bamboo-400 mb-2 font-mono">
                {file.name}
              </p>
              <pre className="text-[13px] text-bamboo-700 leading-relaxed whitespace-pre-wrap font-sans">
                {file.content}
              </pre>
            </div>
          ) : (
            <p className="text-sm text-bamboo-400 italic">暂无文件</p>
          )}
        </div>

        {/* 底部 */}
        <div className="px-5 py-3 border-t border-bamboo-100 bg-bamboo-50/30 shrink-0 text-center">
          <span className="text-[11px] text-bamboo-400">
            {skill.files.length} 个文件 · 只读模式
          </span>
        </div>
      </div>
    </div>,
    document.body
  );
}
