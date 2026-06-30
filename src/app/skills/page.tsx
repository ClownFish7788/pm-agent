/**
 * Skills 管理页。
 *
 * 功能：创建/查看/删除 Skill + 拖拽 .md 文件/文件夹导入。
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import type { Skill, SkillFile, SkillCategory } from "@/types/skill";
import { SKILL_CATEGORIES } from "@/types/skill";
import { skillStore } from "@/stores/skillStore";
import SkillCard from "@/components/SkillCard";
import SkillAddModal from "@/components/SkillAddModal";
import SkillViewModal from "@/components/SkillViewModal";

/* =============================================================================
   预置示例 Skill
   ============================================================================= */

const PRESET_SKILLS: Skill[] = [
  {
    id: "preset-1",
    name: "竞品深度分析",
    category: "competitor",
    files: [
      {
        name: "竞品对比矩阵.md",
        content:
          "请从以下维度对竞品进行分析：\n\n" +
          "1. 产品功能矩阵：列出各竞品的核心功能，按「必备」「加分」「独有」三级分类\n" +
          "2. 定价策略：对比各竞品的定价模型和价格区间\n" +
          "3. 用户评价：提取 App Store / Google Play 评分及好评差评关键词\n" +
          "4. 差异化优势：每个竞品的核心卖点和目标用户群\n\n" +
          "输出格式：每项以表格呈现，最后附总结对比段落。",
      },
    ],
    createdAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "preset-2",
    name: "数据优先调研",
    category: "market",
    files: [
      {
        name: "数据优先原则.md",
        content:
          "进行市场调研时请遵循以下原则：\n\n" +
          "1. 优先查找统计数据、行业报告（.gov 域名为佳）\n" +
          "2. 拒绝以个人博客、论坛帖子作为主要来源\n" +
          "3. 每个数据点必须标注来源 URL 和发布时间\n" +
          "4. 未找到 2025 年后数据时标注「时效性存疑」\n\n" +
          "搜索词模板：`[行业] 市场规模 [年份] 报告 PDF`",
      },
    ],
    createdAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "preset-3",
    name: "MVP 功能优先级",
    category: "product",
    files: [
      {
        name: "MVP评估框架.md",
        content:
          "使用 RICE 框架评估功能优先级：\n\n" +
          "- Reach（覆盖面）：影响多少用户？\n" +
          "- Impact（影响力）：对核心指标的提升幅度？\n" +
          "- Confidence（可信度）：支撑数据有多可靠？\n" +
          "- Effort（实现成本）：人月估算\n\n" +
          "每个功能给出 RICE 分数 = (R × I × C) / E，按分数排序输出 MVP 范围。",
      },
      {
        name: "用户体验原则.md",
        content:
          "产品分析中请关注：\n\n" +
          "1. 新手引导是否 3 步内完成核心价值传递？\n" +
          "2. 核心操作路径是否在 3 次点击内？\n" +
          "3. 是否有明显的「空状态」设计？\n\n" +
          "对每个竞品的以上三点进行评价。",
      },
    ],
    createdAt: "2026-06-01T00:00:00Z",
  },
];

/* =============================================================================
   确认删除 Dialog
   ============================================================================= */

function ConfirmDialog({
  open,
  message,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/15"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-xl border border-bamboo-200 shadow-lg p-5 max-w-[300px] mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-bamboo-700 mb-4">{message}</p>
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-xs text-bamboo-500 hover:bg-bamboo-50 cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 rounded-lg text-xs text-white bg-red-500 hover:bg-red-600 cursor-pointer"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  );
}

/* =============================================================================
   页面主体
   ============================================================================= */

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>(() => {
    const existing = skillStore.getAll();
    if (existing.length === 0) {
      skillStore.importMany(PRESET_SKILLS);
      return skillStore.getAll();
    }
    return existing;
  });

  const [filter, setFilter] = useState<SkillCategory | "all">("all");
  const [addOpen, setAddOpen] = useState(false);
  const [viewSkill, setViewSkill] = useState<Skill | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Skill | null>(null);
  const [preloadedFiles, setPreloadedFiles] = useState<SkillFile[] | undefined>();
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    return skillStore.subscribe(() => setSkills(skillStore.getAll()));
  }, []);

  const filtered =
    filter === "all" ? skills : skills.filter((s) => s.category === filter);

  /* ---- 拖拽 ---- */
  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);

    const files: SkillFile[] = [];
    const items = e.dataTransfer.items;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== "file") continue;

      const entry = item.webkitGetAsEntry?.() as
        | FileSystemDirectoryEntry
        | FileSystemFileEntry
        | null;

      if (entry?.isDirectory) {
        const dirFiles = await readDirectory(
          entry as FileSystemDirectoryEntry
        );
        files.push(...dirFiles);
      } else if (entry?.isFile) {
        const f = await readFileEntry(entry as FileSystemFileEntry);
        if (f) files.push(f);
      } else {
        const f = item.getAsFile();
        if (f && f.name.endsWith(".md")) {
          const content = await f.text();
          files.push({ name: f.name, content });
        }
      }
    }

    if (files.length > 0) {
      setPreloadedFiles(files);
      setAddOpen(true);
    }
  }, []);

  /* ---- CRUD ---- */
  const handleSave = useCallback(
    (name: string, category: SkillCategory, files: SkillFile[]) => {
      skillStore.add({
        id: Date.now().toString(36),
        name,
        category,
        files,
        createdAt: new Date().toISOString(),
      });
      setAddOpen(false);
      setPreloadedFiles(undefined);
    },
    []
  );

  const handleDelete = useCallback(() => {
    if (deleteTarget) {
      skillStore.delete(deleteTarget.id);
      setDeleteTarget(null);
    }
  }, [deleteTarget]);

  /* ---- 渲染 ---- */
  return (
    <div
      className="flex flex-col min-h-full max-w-[960px] mx-auto w-full px-8 py-10"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragOver(false);
      }}
      onDrop={handleDrop}
    >
      {/* 拖拽高亮 */}
      {dragOver && (
        <div className="fixed inset-0 z-40 bg-accent/5 border-2 border-dashed border-accent rounded-2xl flex items-center justify-center pointer-events-none m-4">
          <div className="text-center">
            <svg
              width="48" height="48" viewBox="0 0 24 24" fill="none"
              stroke="#219C5B" strokeWidth="1.5" strokeLinecap="round"
              className="mx-auto mb-2"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14,2 14,8 20,8" />
            </svg>
            <p className="text-sm font-medium text-accent">
              释放以导入 .md 文件
            </p>
            <p className="text-xs text-bamboo-400 mt-1">
              支持单个文件或文件夹
            </p>
          </div>
        </div>
      )}

      {/* 页头 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-bamboo-800 tracking-tight mb-1">
            Skills
          </h1>
          <p className="text-sm text-bamboo-500">
            自定义分析能力 · 拖拽 .md 文件到此处导入
          </p>
        </div>
        <button
          onClick={() => {
            setPreloadedFiles(undefined);
            setAddOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors cursor-pointer"
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="7.5" y1="2" x2="7.5" y2="13" />
            <line x1="2" y1="7.5" x2="13" y2="7.5" />
          </svg>
          创建 Skill
        </button>
      </div>

      {/* 分类筛选 */}
      <div className="flex items-center gap-1.5 mb-5">
        {[{ value: "all", label: "全部" } as const, ...SKILL_CATEGORIES].map(
          (c) => (
            <button
              key={c.value}
              onClick={() => setFilter(c.value as SkillCategory | "all")}
              className={`px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer ${
                filter === c.value
                  ? "bg-accent-subtle text-accent font-medium"
                  : "text-bamboo-500 hover:bg-bamboo-100"
              }`}
            >
              {c.label}
            </button>
          )
        )}
      </div>

      {/* 卡片网格 / 空状态 */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 py-20">
          <div className="w-14 h-14 mb-4 rounded-2xl bg-bamboo-100 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 18 18" fill="none" stroke="#8AA597" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8.1 2.14L3.06 5.04V10.84L8.1 13.74L13.14 10.84V5.04L8.1 2.14Z" />
              <circle cx="8.1" cy="7.9" r="1.5" />
              <path d="M4.5 6.5L8.1 8.5L11.7 6.5" />
            </svg>
          </div>
          <p className="text-sm text-bamboo-400">暂无 Skill</p>
          <p className="text-xs text-bamboo-400/70 mt-1">
            点击「创建 Skill」或拖拽 .md 文件到此处
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {filtered.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              onView={setViewSkill}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <SkillAddModal
        open={addOpen}
        onClose={() => {
          setAddOpen(false);
          setPreloadedFiles(undefined);
        }}
        onSave={handleSave}
        preloadedFiles={preloadedFiles}
      />

      <SkillViewModal skill={viewSkill} onClose={() => setViewSkill(null)} />

      <ConfirmDialog
        open={deleteTarget !== null}
        message={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

/* =============================================================================
   文件夹递归读取（Chromium FileSystemDirectoryEntry API）
   ============================================================================= */

async function readDirectory(
  dirEntry: FileSystemDirectoryEntry
): Promise<SkillFile[]> {
  const files: SkillFile[] = [];
  const reader = dirEntry.createReader();

  const readAll = (): Promise<FileSystemEntry[]> =>
    new Promise((resolve) => {
      const all: FileSystemEntry[] = [];
      const next = () => {
        reader.readEntries((entries) => {
          if (entries.length === 0) resolve(all);
          else {
            all.push(...entries);
            next();
          }
        });
      };
      next();
    });

  const entries = await readAll();

  for (const entry of entries) {
    if (entry.isDirectory) {
      const sub = await readDirectory(entry as FileSystemDirectoryEntry);
      files.push(...sub);
    } else if (entry.isFile) {
      const f = await readFileEntry(entry as FileSystemFileEntry);
      if (f) files.push(f);
    }
  }

  return files;
}

function readFileEntry(
  fileEntry: FileSystemFileEntry
): Promise<SkillFile | null> {
  return new Promise((resolve) => {
    fileEntry.file((f) => {
      if (!f.name.endsWith(".md")) {
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = () =>
        resolve({ name: f.name, content: (reader.result as string) || "" });
      reader.onerror = () => resolve(null);
      reader.readAsText(f);
    });
  });
}
