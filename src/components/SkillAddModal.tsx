"use client";

/**
 * Skill 创建/编辑 Modal。
 *
 * 功能：
 * - 粘贴 .md 内容或选择 .md 文件
 * - 多个文件 tab，可增删
 * - 支持预加载文件（从页面拖拽传入）
 */

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import type { Skill, SkillFile, SkillCategory } from "@/types/skill";
import { SKILL_CATEGORIES } from "@/types/skill";

interface SkillAddModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (name: string, category: SkillCategory, files: SkillFile[]) => void;
  /** 预加载文件（拖拽传入时不为空） */
  preloadedFiles?: SkillFile[];
  /** 编辑模式 */
  editing?: Skill | null;
}

/** 单个文件条目 */
interface FileEntry {
  id: string;
  name: string;
  content: string;
  mode: "paste" | "file";
  /** file 模式下已选择的文件名（仅展示） */
  fileName?: string;
}

function createEntry(name = ""): FileEntry {
  return {
    id: Math.random().toString(36).slice(2, 8),
    name,
    content: "",
    mode: "paste",
  };
}

export default function SkillAddModal({
  open,
  onClose,
  onSave,
  preloadedFiles,
  editing,
}: SkillAddModalProps) {
  const [skillName, setSkillName] = useState(editing?.name ?? "");
  const [category, setCategory] = useState<SkillCategory>(
    editing?.category ?? "global"
  );
  const [entries, setEntries] = useState<FileEntry[]>(() => {
    if (editing) {
      return editing.files.map((f) => ({
        id: Math.random().toString(36).slice(2, 8),
        name: f.name,
        content: f.content,
        mode: "paste" as const,
        fileName: f.name,
      }));
    }
    if (preloadedFiles && preloadedFiles.length > 0) {
      return preloadedFiles.map((f) => ({
        id: Math.random().toString(36).slice(2, 8),
        name: f.name,
        content: f.content,
        mode: "paste" as const,  // 内容已加载，用粘贴模式展示
        fileName: f.name,
      }));
    }
    return [createEntry()];
  });

  // 关闭时重置
  useEffect(() => {
    if (!open) return;
    setSkillName(editing?.name ?? "");
    setCategory(editing?.category ?? "global");
    if (editing) {
      setEntries(
        editing.files.map((f) => ({
          id: Math.random().toString(36).slice(2, 8),
          name: f.name,
          content: f.content,
          mode: "paste" as const,
          fileName: f.name,
        }))
      );
    } else if (preloadedFiles && preloadedFiles.length > 0) {
      setEntries(
        preloadedFiles.map((f) => ({
          id: Math.random().toString(36).slice(2, 8),
          name: f.name,
          content: f.content,
          mode: "paste" as const,  // 内容已加载，用粘贴模式展示
          fileName: f.name,
        }))
      );
    } else {
      setEntries([createEntry()]);
    }
  }, [open, editing, preloadedFiles]);

  // ESC
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  /* ---- 文件条目操作 ---- */
  const updateEntry = useCallback(
    (id: string, patch: Partial<FileEntry>) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...patch } : e))
      );
    },
    []
  );

  const removeEntry = useCallback((id: string) => {
    setEntries((prev) => (prev.length <= 1 ? prev : prev.filter((e) => e.id !== id)));
  }, []);

  const addEntry = useCallback(() => {
    setEntries((prev) => [...prev, createEntry()]);
  }, []);

  /* ---- 文件选择 ---- */
  const handleFileSelect = useCallback(
    (id: string, e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (!file.name.endsWith(".md")) {
        alert("仅支持 .md 文件");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        updateEntry(id, {
          name: file.name,
          content: (reader.result as string) || "",
          fileName: file.name,
          mode: "file",
        });
      };
      reader.readAsText(file);
    },
    [updateEntry]
  );

  /* ---- 保存 ---- */
  const handleSave = () => {
    const name = skillName.trim();
    if (!name) return;

    // 收集有内容的文件条目，文件名为空时自动生成
    const files: SkillFile[] = entries
      .filter((e) => e.content.trim())
      .map((e, i) => ({
        name:
          e.name.trim() ||
          e.fileName ||
          `${name}-${i + 1}.md`,
        content: e.content.trim(),
      }));

    if (files.length === 0) return;
    onSave(name, category, files);
  };

  if (!open) return null;

  /* ---- 保存按钮状态：有 skill 名 + 有任一文件内容即可 ---- */
  const canSave =
    skillName.trim().length > 0 &&
    entries.some((e) => e.content.trim().length > 0);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="
          w-full max-w-[560px] max-h-[85vh] mx-4
          bg-white rounded-2xl border border-bamboo-200
          shadow-xl shadow-bamboo-800/5
          flex flex-col
        "
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-bamboo-100 shrink-0">
          <h2 className="text-[15px] font-semibold text-bamboo-800">
            {editing ? "编辑 Skill" : "创建 Skill"}
          </h2>
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

        {/* 内容 */}
        <div className="px-5 py-4 space-y-4 overflow-y-auto flex-1">
          {/* Skill 名称 */}
          <div>
            <label className="block text-xs font-medium text-bamboo-700 mb-1.5">
              Skill 名称
            </label>
            <input
              type="text"
              value={skillName}
              onChange={(e) => setSkillName(e.target.value)}
              placeholder="给这个 Skill 起个名字"
              className="
                w-full px-3 py-2 rounded-lg border border-bamboo-200
                text-[13px] text-bamboo-800 placeholder:text-bamboo-400
                bg-bamboo-50/50 outline-none
                focus:border-accent focus:ring-2 focus:ring-accent/10
                transition-shadow
              "
            />
          </div>

          {/* 分类 */}
          <div>
            <label className="block text-xs font-medium text-bamboo-700 mb-1.5">
              适用部门
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SkillCategory)}
              className="
                w-full px-3 py-2 rounded-lg border border-bamboo-200
                text-[13px] text-bamboo-800 bg-bamboo-50/50
                outline-none cursor-pointer
                focus:border-accent focus:ring-2 focus:ring-accent/10
                transition-shadow
              "
            >
              {SKILL_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* 文件列表 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-bamboo-700">
                文件 ({entries.length})
              </label>
              <button
                onClick={addEntry}
                className="text-xs text-accent hover:text-accent-hover font-medium cursor-pointer"
              >
                + 添加文件
              </button>
            </div>

            <div className="space-y-2.5">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-xl border border-bamboo-200 overflow-hidden"
                >
                  {/* 文件名 + 模式切换 + 删除 */}
                  <div className="flex items-center gap-2 px-3 py-2 bg-bamboo-50/50 border-b border-bamboo-100">
                    <input
                      type="text"
                      value={entry.name}
                      onChange={(e) =>
                        updateEntry(entry.id, { name: e.target.value })
                      }
                      placeholder="文件名.md"
                      className="
                        flex-1 bg-transparent
                        text-xs text-bamboo-800 placeholder:text-bamboo-400
                        outline-none
                      "
                    />
                    <select
                      value={entry.mode}
                      onChange={(e) =>
                        updateEntry(entry.id, {
                          mode: e.target.value as "paste" | "file",
                        })
                      }
                      className="text-[10px] text-bamboo-500 bg-transparent outline-none cursor-pointer"
                    >
                      <option value="paste">粘贴</option>
                      <option value="file">选择文件</option>
                    </select>
                    <button
                      onClick={() => removeEntry(entry.id)}
                      disabled={entries.length <= 1}
                      className="text-bamboo-400 hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                        <line x1="3" y1="6" x2="9" y2="6" />
                      </svg>
                    </button>
                  </div>

                  {/* 内容区 */}
                  <div className="p-3">
                    {entry.mode === "paste" ? (
                      <textarea
                        value={entry.content}
                        onChange={(e) =>
                          updateEntry(entry.id, { content: e.target.value })
                        }
                        placeholder="粘贴 Markdown 内容..."
                        rows={5}
                        className="
                          w-full resize-none
                          text-xs text-bamboo-800 placeholder:text-bamboo-400
                          bg-transparent outline-none font-mono
                          leading-relaxed
                        "
                      />
                    ) : (
                      <label className="flex flex-col items-center gap-2 py-4 cursor-pointer text-xs text-bamboo-400 hover:text-accent transition-colors">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14,2 14,8 20,8" />
                        </svg>
                        {entry.fileName ? (
                          <span className="text-accent font-medium">
                            {entry.fileName}
                          </span>
                        ) : (
                          "点击选择 .md 文件"
                        )}
                        <input
                          type="file"
                          accept=".md"
                          onChange={(e) => handleFileSelect(entry.id, e)}
                          className="hidden"
                        />
                      </label>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-bamboo-100 bg-bamboo-50/30 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-bamboo-500 hover:bg-bamboo-100 transition-colors cursor-pointer"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className={`
              px-5 py-2 rounded-xl text-sm font-medium transition-all
              ${
                canSave
                  ? "bg-accent text-white hover:bg-accent-hover cursor-pointer"
                  : "bg-bamboo-200 text-bamboo-400 cursor-not-allowed"
              }
            `}
          >
            保存
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
