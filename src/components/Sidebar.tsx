"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import SettingsModal from "./SettingsModal";

/* --------------------------------------------------------------------------- */
/* 内联 SVG 图标                                                               */
/* --------------------------------------------------------------------------- */

function HistoryIcon() {
  return (
    <svg
      width="18" height="18" viewBox="0 0 18 18" fill="none"
      stroke="#5B7B68" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round"
    >
      <circle cx="9" cy="9" r="7.2" />
      <polyline points="9,4.5 9,9 12.6,10.8" />
    </svg>
  );
}

function SkillsIcon() {
  return (
    <svg
      width="18" height="18" viewBox="0 0 18 18" fill="none"
      stroke="#5B7B68" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M8.1 2.14L3.06 5.04V10.84L8.1 13.74L13.14 10.84V5.04L8.1 2.14Z" />
      <circle cx="8.1" cy="7.9" r="1.5" />
      <path d="M4.5 6.5L8.1 8.5L11.7 6.5" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg
      width="16" height="16" viewBox="0 0 18 18" fill="none"
      stroke="#8AA597" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round"
    >
      <circle cx="9" cy="9" r="2.5" />
      <path d="M9 1.5V3.5" />
      <path d="M9 14.5V16.5" />
      <path d="M3.7 3.7L5.1 5.1" />
      <path d="M12.9 12.9L14.3 14.3" />
      <path d="M1.5 9H3.5" />
      <path d="M14.5 9H16.5" />
      <path d="M3.7 14.3L5.1 12.9" />
      <path d="M12.9 5.1L14.3 3.7" />
    </svg>
  );
}

function LoginIcon() {
  return (
    <svg
      width="16" height="16" viewBox="0 0 18 18" fill="none"
      stroke="#8AA597" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round"
    >
      <circle cx="9" cy="6" r="3" />
      <path d="M2.5 15.5C2.5 12.5 5.4 10 9 10C12.6 10 15.5 12.5 15.5 15.5" />
    </svg>
  );
}

/* --------------------------------------------------------------------------- */
/* 组件主体                                                                    */
/* --------------------------------------------------------------------------- */

export default function Sidebar() {
  const pathname = usePathname();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <aside
      className="
        flex flex-col
        w-60 h-screen
        bg-bamboo-100
        border-r border-bamboo-200
        shrink-0
        select-none
      "
    >
      {/* ---- Logo ---- */}
      <div className="px-5 pt-7 pb-5">
        <Link href="/" className="inline-flex items-center gap-2 no-underline">
          <span
            className="text-lg font-semibold tracking-tight text-bamboo-800"
            style={{ fontFamily: "var(--font-geist-sans)" }}
          >
            PM Agent
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-subtle text-accent font-medium tracking-wide">
            BETA
          </span>
        </Link>
      </div>

      {/* ---- 新对话按钮 ---- */}
      <div className="px-4 pb-4">
        <Link
          href="/"
          className="
            flex items-center gap-2.5
            w-full px-3 py-2 rounded-lg
            bg-accent text-white text-sm font-medium
            hover:bg-accent-hover
            transition-colors duration-150
            no-underline
          "
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="8" y1="2" x2="8" y2="14" />
            <line x1="2" y1="8" x2="14" y2="8" />
          </svg>
          新对话
        </Link>
      </div>

      {/* ---- 导航 ---- */}
      <nav className="flex flex-col gap-0.5 px-3 flex-1">
        <Link
          href="/history"
          className={`sidebar-link flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm no-underline
            ${isActive("/history") ? "active" : "text-bamboo-600 hover:bg-bamboo-200/60"}`}
        >
          <HistoryIcon />
          历史记录
        </Link>

        <Link
          href="/skills"
          className={`sidebar-link flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm no-underline
            ${isActive("/skills") ? "active" : "text-bamboo-600 hover:bg-bamboo-200/60"}`}
        >
          <SkillsIcon />
          Skills
        </Link>
      </nav>

      {/* ---- 底部 ---- */}
      <div className="px-3 pb-5 flex flex-col gap-0.5 border-t border-bamboo-200 pt-3 mx-3">
        <button
          onClick={() => setSettingsOpen(true)}
          className="sidebar-link flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-bamboo-500 hover:bg-bamboo-200/60 no-underline w-full text-left cursor-pointer"
        >
          <SettingsIcon />
          设置
        </button>

        <Link
          href="/login"
          className="sidebar-link flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-bamboo-500 hover:bg-bamboo-200/60 no-underline"
        >
          <LoginIcon />
          登录
        </Link>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </aside>
  );
}
