"""
进度追踪器 —— SSE 流式推送和一次性恢复的数据中枢。

贯穿全链路（Top → Middle → Bottom），每个关键节点调用 tracker.emit() 发出
ProgressEvent。SSE 模式下通过 asyncio.Queue 实时推送，非 SSE 模式下仅累积到
events 列表供一次性返回。

使用方式：
    # SSE 模式
    tracker = ProgressTracker(use_queue=True)
    # ... DAG 执行 ...
    async for event in tracker.stream():  # FastAPI SSE 端点用
        yield event

    # 非 SSE 模式
    tracker = ProgressTracker(use_queue=False)
    # ... DAG 执行 ...
    return tracker.snapshot()  # {"events": [...], "final_report": ...}

    # 恢复
    old_tracker = _sessions.get(thread_id)
    return old_tracker.snapshot()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from schemas import BottomReport, FinalReport, ProgressEvent, SSEEventType


class ProgressTracker:
    """全链路进度追踪器。

    属性：
        events: list[ProgressEvent] — 全量事件累积（供一次性返回 / 恢复）
        final_report: FinalReport | None — CEO 汇总报告（done 事件后填充）
        _queue: asyncio.Queue | None — SSE 推送队列（非 SSE 模式为 None）
    """

    def __init__(self, use_queue: bool = False) -> None:
        """初始化追踪器。

        Args:
            use_queue: True = SSE 模式（emit 时同时推送到 queue）
                       False = 非 SSE 模式（仅累积到 events 列表）
        """
        self.events: list[ProgressEvent] = []
        self.final_report: FinalReport | None = None
        self._queue: asyncio.Queue[ProgressEvent] | None = (
            asyncio.Queue() if use_queue else None
        )

    # ------------------------------------------------------------------
    # 核心 API
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: SSEEventType,
        message: str = "",
        *,
        phase: str | None = None,
        department: str | None = None,
        agent_id: str | None = None,
        data: dict | None = None,
        call_count: int = 0,
    ) -> ProgressEvent:
        """发出一个进度事件。

        事件同时写入 events 列表和 SSE queue（如启用）。不抛异常。

        Args:
            event_type: 事件类型枚举
            message: 人类可读消息
            phase: 当前阶段名
            department: 部门名（如 "market_research"）
            agent_id: 子 Agent ID（如 "market_query_1"）
            data: 结构化 payload
            call_count: 当前 LLM 调用计数

        Returns:
            创建出的 ProgressEvent（调用方通常不需要）
        """
        event = ProgressEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message=message,
            phase=phase,
            department=department,
            agent_id=agent_id,
            data=data or {},
            call_count=call_count,
        )
        self.events.append(event)

        if self._queue is not None:
            # queue.put_nowait：SSE 消费者在异步循环里读，不会阻塞
            self._queue.put_nowait(event)

        return event

    def set_final_report(self, report: FinalReport) -> None:
        """设置最终报告（CEO 汇总完成后调用）。"""
        self.final_report = report

    def snapshot(self) -> dict:
        """返回当前完整快照——供 POST /analyze 和 GET /analyze/{thread_id} 使用。

        Returns:
            {"events": [...], "final_report": {...} | None}
        """
        return {
            "events": [e.model_dump() for e in self.events],
            "final_report": self.final_report.model_dump() if self.final_report else None,
        }

    # ------------------------------------------------------------------
    # SSE 流式迭代器
    # ------------------------------------------------------------------

    async def stream(self):
        """SSE 事件迭代器 —— 逐个 yield ProgressEvent 直到 done 事件发出。

        用于 FastAPI StreamingResponse。消费者从这个生成器读事件，
        读到 DONE 类型的事件后退出。

        Yields:
            ProgressEvent 实例
        """
        while True:
            event = await self._queue.get()
            yield event
            if event.event_type == SSEEventType.DONE:
                break

    # ------------------------------------------------------------------
    # 便捷方法 —— 封装常见 emit 模式，减少调用方重复代码
    # ------------------------------------------------------------------

    def plan_generated(self, plan_data: dict, call_count: int) -> None:
        """Top Agent 产出执行计划。"""
        self.emit(
            SSEEventType.PLAN_GENERATED,
            message=f"执行计划已生成：{plan_data.get('task_count', '?')} 个部门，"
                    f"跳过 {plan_data.get('skipped_count', '?')} 个",
            phase="planning",
            data=plan_data,
            call_count=call_count,
        )

    def department_start(self, dept: str, focus_areas: list[str], call_count: int) -> None:
        """中层部门开始执行。"""
        self.emit(
            SSEEventType.DEPARTMENT_START,
            message=f"部门启动: {dept}",
            phase="execution",
            department=dept,
            data={"focus_areas": focus_areas},
            call_count=call_count,
        )

    def department_skip(self, dept: str, reason: str, call_count: int) -> None:
        """中层部门被跳过。"""
        self.emit(
            SSEEventType.DEPARTMENT_SKIP,
            message=f"跳过 {dept}: {reason}",
            phase="execution",
            department=dept,
            data={"reason": reason},
            call_count=call_count,
        )

    def sub_agent_start(self, dept: str, agent_id: str, search_query: str, call_count: int) -> None:
        """底层 Agent 启动搜索。"""
        self.emit(
            SSEEventType.SUB_AGENT_START,
            message=f"搜索启动: {agent_id}",
            phase="execution",
            department=dept,
            agent_id=agent_id,
            data={"search_query": search_query},
            call_count=call_count,
        )

    def sub_agent_search(self, dept: str, agent_id: str, result_count: int, call_count: int) -> None:
        """Tavily 搜索完成。"""
        self.emit(
            SSEEventType.SUB_AGENT_SEARCH,
            message=f"搜索完成: {agent_id} ({result_count} 条结果)",
            phase="execution",
            department=dept,
            agent_id=agent_id,
            data={"result_count": result_count},
            call_count=call_count,
        )

    def sub_agent_done(
        self, dept: str, agent_id: str, report_summary: str, findings_count: int, call_count: int
    ) -> None:
        """底层 LLM 筛选+分析完成。"""
        self.emit(
            SSEEventType.SUB_AGENT_DONE,
            message=f"报告完成: {agent_id} ({findings_count} 条发现)",
            phase="execution",
            department=dept,
            agent_id=agent_id,
            data={
                "report_summary": report_summary[:200],
                "findings_count": findings_count,
            },
            call_count=call_count,
        )

    def sub_agent_review(
        self,
        dept: str,
        agent_id: str,
        verdict: str,
        overall: float,
        credibility: float,
        reason: str,
        call_count: int,
    ) -> None:
        """审核结果。"""
        self.emit(
            SSEEventType.SUB_AGENT_REVIEW,
            message=f"审核: {agent_id} → {verdict} (overall={overall:.1f})",
            phase="execution",
            department=dept,
            agent_id=agent_id,
            data={
                "verdict": verdict,
                "overall_score": overall,
                "credibility": credibility,
                "reason": reason,
            },
            call_count=call_count,
        )

    def department_done(
        self,
        dept: str,
        summary: str,
        key_points_count: int,
        confidence: float,
        status: str,
        call_count: int,
    ) -> None:
        """中层综合分析完成。"""
        self.emit(
            SSEEventType.DEPARTMENT_DONE,
            message=f"部门完成: {dept} ({key_points_count} 条要点, 可信度 {confidence:.0%})",
            phase="execution",
            department=dept,
            data={
                "summary": summary[:200] if summary else "",
                "key_points_count": key_points_count,
                "overall_confidence": confidence,
                "status": status,
            },
            call_count=call_count,
        )

    def final_report_done(self, report: FinalReport, call_count: int) -> None:
        """CEO 汇总完成 —— 推送完整 FinalReport JSON，然后标记 done。"""
        self.set_final_report(report)
        report_dict = report.model_dump()
        self.emit(
            SSEEventType.FINAL_REPORT,
            message=f"综合分析完成，评分 {report.overall_score:.0f}/100",
            phase="completed",
            data=report_dict,
            call_count=call_count,
        )
        self.emit(
            SSEEventType.DONE,
            message="分析流程结束",
            phase="completed",
            call_count=call_count,
        )

    def error(
        self,
        error_msg: str,
        *,
        phase: str | None = None,
        department: str | None = None,
        agent_id: str | None = None,
        call_count: int = 0,
    ) -> None:
        """非致命错误。"""
        self.emit(
            SSEEventType.ERROR,
            message=error_msg,
            phase=phase,
            department=department,
            agent_id=agent_id,
            data={"error": error_msg},
            call_count=call_count,
        )

    def budget(self, total: int, max_calls: int) -> None:
        """LLM 调用计数更新。"""
        self.emit(
            SSEEventType.BUDGET_UPDATE,
            message=f"LLM 调用: {total}/{max_calls}",
            phase="budget",
            data={"total_calls": total, "max_calls": max_calls},
            call_count=total,
        )
