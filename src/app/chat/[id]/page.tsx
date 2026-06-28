/**
 * Chat 页 —— Agent 协作过程可视化。
 *
 * 硬编码阶段：用 MOCK_ANALYSIS 数据渲染完整 UI。
 * 后续替换为 useSSE(url, body) → analysisReducer → AnalysisView。
 */

import AnalysisView from "@/components/AnalysisView";
import { MOCK_ANALYSIS } from "@/data/mockAnalysis";

export default function ChatPage() {
  return <AnalysisView state={MOCK_ANALYSIS} />;
}
