/**
 * 报告缓存 —— 内存 + sessionStorage 双写。
 *
 * Chat 页收到 final_report 后调用 set()，
 * Report 页通过 get() 读取。刷新不丢（sessionStorage），
 * 同标签页秒读（内存缓存）。
 */

import type { FinalReport } from "@/types/schemas";

const STORAGE_KEY = "pm-agent-latest-report";

let cached: FinalReport | null = null;

export const reportStore = {
  get(): FinalReport | null {
    if (cached) return cached;
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        cached = JSON.parse(raw) as FinalReport;
        return cached;
      }
    } catch {
      // corrupted data, ignore
    }
    return null;
  },

  set(report: FinalReport): void {
    cached = report;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(report));
    } catch {
      // quota exceeded or private browsing, ignore
    }
  },

  clear(): void {
    cached = null;
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  },
};
