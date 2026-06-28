"use client";

import { scoreColor } from "@/types/history";

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
}

/**
 * SVG 环形评分图。
 * 绿(≥70) / 黄(40-69) / 红(<40)，背景为 bamboo-200 灰绿轨道。
 */
export default function ScoreRing({ score, size = 52, strokeWidth = 4 }: ScoreRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(1, score / 100)) * circumference;
  const color = scoreColor(score);
  const center = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0"
      role="img"
      aria-label={`评分 ${score} 分`}
    >
      {/* 底色轨道 */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="#DCE8E0"
        strokeWidth={strokeWidth}
      />
      {/* 评分弧 */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={`${progress} ${circumference - progress}`}
        transform={`rotate(-90 ${center} ${center})`}
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
      {/* 中心数字 */}
      <text
        x={center}
        y={center}
        textAnchor="middle"
        dominantBaseline="central"
        className="font-bold"
        style={{
          fontSize: size * 0.28,
          fill: "#1C2621",
          fontFamily: "var(--font-geist-mono), monospace",
        }}
      >
        {score}
      </text>
    </svg>
  );
}
