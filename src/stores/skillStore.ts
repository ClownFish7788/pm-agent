/**
 * Skill 存储 —— localStorage CRUD + 订阅。
 */

import type { Skill, SkillCategory } from "@/types/skill";

const STORAGE_KEY = "pm-agent-skills";

function load(): Skill[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as Skill[];
  } catch { /* ignore */ }
  return [];
}

function save(skills: Skill[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(skills));
  } catch { /* ignore */ }
}

let _skills = load();
const _listeners = new Set<() => void>();

function notify(): void {
  for (const fn of _listeners) fn();
}

export const skillStore = {
  getAll(): Skill[] {
    return _skills;
  },

  getByCategory(cat: SkillCategory | "all"): Skill[] {
    if (cat === "all") return _skills;
    return _skills.filter((s) => s.category === cat);
  },

  getById(id: string): Skill | undefined {
    return _skills.find((s) => s.id === id);
  },

  add(skill: Skill): void {
    _skills = [skill, ..._skills];
    save(_skills);
    notify();
  },

  update(id: string, patch: Partial<Omit<Skill, "id" | "createdAt">>): void {
    _skills = _skills.map((s) => (s.id === id ? { ...s, ...patch } : s));
    save(_skills);
    notify();
  },

  delete(id: string): void {
    _skills = _skills.filter((s) => s.id !== id);
    save(_skills);
    notify();
  },

  /** 批量导入（去重按 name） */
  importMany(skills: Skill[]): void {
    const existing = new Set(_skills.map((s) => s.name));
    const fresh = skills.filter((s) => !existing.has(s.name));
    _skills = [...fresh, ..._skills];
    save(_skills);
    notify();
  },

  subscribe(fn: () => void): () => void {
    _listeners.add(fn);
    return () => _listeners.delete(fn);
  },
};
