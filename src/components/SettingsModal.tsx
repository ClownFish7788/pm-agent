"use client";

/**
 * 设置 Modal —— 点击侧边栏「设置」触发。
 *
 * 通过 createPortal 渲染到 document.body，避免 z-index 被父容器限制。
 * 改完即时生效，不需要保存按钮。ESC / 点击遮罩 / × 均可关闭。
 */

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { settingsStore, type AppSettings } from "@/stores/settingsStore";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

/* --------------------------------------------------------------------------- */
/* 表单行                                                                       */
/* --------------------------------------------------------------------------- */

function FieldRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-bamboo-700">{label}</label>
      {children}
      {hint && (
        <p className="text-[11px] text-bamboo-400 leading-relaxed">{hint}</p>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* 主体                                                                         */
/* --------------------------------------------------------------------------- */

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [settings, setSettings] = useState<AppSettings>(() =>
    settingsStore.get()
  );

  // 订阅外部变更
  useEffect(() => {
    return settingsStore.subscribe(setSettings);
  }, []);

  // 统一写入
  const update = useCallback(
    <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
      settingsStore.set(key, value);
    },
    []
  );

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    /* 遮罩 */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* 卡片 */}
      <div
        className="
          w-full max-w-[420px] mx-4
          bg-white rounded-2xl
          border border-bamboo-200
          shadow-xl shadow-bamboo-800/5
          overflow-hidden
        "
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-bamboo-100">
          <h2 className="text-[15px] font-semibold text-bamboo-800 tracking-tight">
            设置
          </h2>
          <button
            onClick={onClose}
            className="
              w-7 h-7 rounded-lg
              flex items-center justify-center
              text-bamboo-400 hover:text-bamboo-600
              hover:bg-bamboo-50
              transition-colors cursor-pointer
            "
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="2" y1="2" x2="12" y2="12" />
              <line x1="12" y1="2" x2="2" y2="12" />
            </svg>
          </button>
        </div>

        {/* 内容 */}
        <div className="px-5 py-4 space-y-5 max-h-[60vh] overflow-y-auto">
          {/* ---- 连接 ---- */}
          <section>
            <p className="text-[11px] font-medium text-bamboo-400 uppercase tracking-wider mb-3">
              连接
            </p>
            <div className="space-y-3">
              <FieldRow
                label="后端地址"
                hint="FastAPI 分析服务的地址，支持相对路径或完整 URL"
              >
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => update("backendUrl", e.target.value)}
                  className="
                    w-full px-3 py-2
                    rounded-lg border border-bamboo-200
                    text-[13px] text-bamboo-800
                    placeholder:text-bamboo-400
                    bg-bamboo-50/50
                    outline-none
                    focus:border-accent focus:ring-2 focus:ring-accent/10
                    transition-shadow font-mono
                  "
                />
              </FieldRow>
            </div>
          </section>

          {/* ---- 分析参数 ---- */}
          <section>
            <p className="text-[11px] font-medium text-bamboo-400 uppercase tracking-wider mb-3">
              分析参数
            </p>
            <div className="space-y-3">
              <FieldRow label="LLM 调用上限" hint="达到上限后自动停止，用已有数据生成报告">
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={10}
                    max={60}
                    step={5}
                    value={settings.maxCalls}
                    onChange={(e) => update("maxCalls", Number(e.target.value))}
                    className="flex-1 accent-accent"
                  />
                  <span className="w-8 text-xs font-mono text-bamboo-600 text-right tabular-nums">
                    {settings.maxCalls}
                  </span>
                </div>
              </FieldRow>

              <FieldRow label="首次响应超时" hint="发起分析后等待后端首次响应的时间">
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={10}
                    max={120}
                    step={5}
                    value={settings.firstByteTimeout}
                    onChange={(e) =>
                      update("firstByteTimeout", Number(e.target.value))
                    }
                    className="flex-1 accent-accent"
                  />
                  <span className="w-12 text-xs font-mono text-bamboo-600 text-right tabular-nums">
                    {settings.firstByteTimeout} 秒
                  </span>
                </div>
              </FieldRow>
            </div>
          </section>

          {/* ---- 数据 ---- */}
          <section>
            <p className="text-[11px] font-medium text-bamboo-400 uppercase tracking-wider mb-3">
              数据
            </p>
            <button
              onClick={() => {
                settingsStore.reset();
                // 同时清 report 缓存
                try {
                  sessionStorage.removeItem("pm-agent-latest-report");
                } catch { /* ignore */ }
              }}
              className="
                text-xs text-red-500
                hover:text-red-600
                px-3 py-1.5 rounded-lg
                border border-red-200
                hover:bg-red-50
                transition-colors cursor-pointer
              "
            >
              恢复默认设置 & 清除分析缓存
            </button>
          </section>
        </div>

        {/* 底部 */}
        <div className="px-5 py-3 border-t border-bamboo-100 bg-bamboo-50/50">
          <p className="text-[11px] text-bamboo-400 text-center">
            PM Agent v0.3.0 · Next.js 16 · FastAPI · LangGraph · DeepSeek
          </p>
        </div>
      </div>
    </div>,
    document.body
  );
}
