"use client";

/**
 * 战略建议列表 —— 按优先级排列，P1 视觉最重，依次递减。
 * 每条建议包含优先级序号、标题、理由、依据部门。
 */

import type { Recommendation } from "@/types/schemas";
import { DEPARTMENT_LABELS } from "@/types/history";

interface RecommendationListProps {
  recommendations: Recommendation[];
}

export default function RecommendationList({ recommendations }: RecommendationListProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-bamboo-800 mb-4 tracking-tight">
        战略建议
      </h2>

      <div className="space-y-3">
        {recommendations.map((rec) => {
          const isP1 = rec.priority === 1;

          return (
            <div
              key={rec.priority}
              className="rounded-xl border border-bamboo-200 bg-white overflow-hidden hover:shadow-sm transition-all"
              style={{
                borderLeftWidth: isP1 ? 4 : 3,
                borderLeftColor: isP1 ? "#219C5B" : rec.priority === 2 ? "#5B7B68" : "#B8D0BE",
              }}
            >
              <div className="p-4">
                {/* 优先级 + 标题 */}
                <div className="flex items-start gap-3">
                  <span
                    className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                      isP1
                        ? "bg-accent text-white"
                        : rec.priority === 2
                          ? "bg-bamboo-600 text-white"
                          : "bg-bamboo-200 text-bamboo-600"
                    }`}
                  >
                    P{rec.priority}
                  </span>

                  <div className="flex-1 min-w-0">
                    <h4
                      className={`${
                        isP1 ? "text-[15px] font-semibold" : "text-sm font-medium"
                      } text-bamboo-800 leading-snug`}
                    >
                      {rec.title}
                    </h4>

                    <p
                      className={`mt-1 ${
                        isP1 ? "text-[13px]" : "text-xs"
                      } text-bamboo-600 leading-relaxed`}
                    >
                      {rec.rationale}
                    </p>

                    {/* 依据部门 */}
                    {rec.related_dimensions.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {rec.related_dimensions.map((dim) => (
                          <span
                            key={dim}
                            className="text-[10px] px-2 py-0.5 rounded-full bg-bamboo-50 text-bamboo-500"
                          >
                            依据：{DEPARTMENT_LABELS[dim as keyof typeof DEPARTMENT_LABELS] ?? dim}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
