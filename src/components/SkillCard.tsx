"use client";

/**
 * Skill 方形卡片 —— 展示名字 + 开头内容 + 分类标签。
 * 点击查看全部文件，悬停显示删除按钮。
 */

import type { Skill } from "@/types/skill";
import { CATEGORY_LABEL } from "@/types/skill";

interface SkillCardProps {
  skill: Skill;
  onView: (skill: Skill) => void;
  onDelete: (skill: Skill) => void;
}

export default function SkillCard({ skill, onView, onDelete }: SkillCardProps) {
  const firstFile = skill.files[0];
  const preview =
    firstFile?.content.slice(0, 120).replace(/\n/g, " ") + (firstFile?.content && firstFile.content.length > 120 ? "..." : "");
  const fileCount = skill.files.length;

  return (
    <button
      onClick={() => onView(skill)}
      className="
        group relative
        aspect-square
        w-full
        rounded-2xl
        border border-bamboo-200
        bg-white
        hover:border-bamboo-300 hover:shadow-md
        transition-all duration-200
        flex flex-col
        p-5
        text-left
        cursor-pointer
        overflow-hidden
      "
    >
      {/* 分类标签 */}
      <span className="text-[10px] font-medium text-bamboo-400 bg-bamboo-50 px-2 py-0.5 rounded-full self-start mb-3">
        {CATEGORY_LABEL[skill.category]}
      </span>

      {/* 名称 */}
      <h3 className="text-[15px] font-semibold text-bamboo-800 leading-snug mb-2 line-clamp-2">
        {skill.name}
      </h3>

      {/* 内容预览 */}
      {preview ? (
        <p className="text-xs text-bamboo-400 leading-relaxed flex-1 line-clamp-3">
          {preview}
        </p>
      ) : (
        <p className="text-xs text-bamboo-300 italic flex-1">
          {fileCount} 个文件
        </p>
      )}

      {/* 底部信息 */}
      <div className="flex items-center justify-between mt-auto pt-2">
        <span className="text-[10px] text-bamboo-400">
          {fileCount} 个文件
        </span>
      </div>

      {/* 删除按钮（hover 出现） */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(skill);
        }}
        className="
          absolute top-3 right-3
          w-7 h-7 rounded-lg
          flex items-center justify-center
          bg-white border border-bamboo-200
          text-bamboo-400 hover:text-red-500 hover:border-red-200
          opacity-0 group-hover:opacity-100
          transition-all duration-150
          cursor-pointer
        "
        title="删除 Skill"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <line x1="3" y1="3" x2="9" y2="9" />
          <line x1="9" y1="3" x2="3" y2="9" />
        </svg>
      </button>
    </button>
  );
}
