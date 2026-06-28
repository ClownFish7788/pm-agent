# PM Agent Backend API 文档

Base URL: `http://localhost:8000`

---

## 端点总览

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/analyze` | 非 SSE：阻塞等待完成后一次性返回全部事件 + 报告 |
| `POST` | `/analyze/stream` | SSE：实时流式推送每个进度事件 |
| `GET` | `/analyze/{thread_id}` | 中断恢复 / 进度查询 |

---

## GET /health

健康检查，前端发起分析前确认后端存活。

**Response 200:**
```json
{
  "status": "ok",
  "service": "pm-agent-backend",
  "version": "0.2.0"
}
```

---

## POST /analyze

非 SSE 模式，阻塞等待全部分析完成，一次性返回所有事件和最终报告。  
适用于不支持 SSE 的客户端或轮询模式。

**Request Body:**
```json
{
  "description": "我想做一个宠物社交App，连接同城的宠物主人"
}
```

**Response 200:**
```json
{
  "events": [
    {
      "event_type": "plan_generated",
      "timestamp": "2026-06-28T12:00:01.000Z",
      "message": "执行计划已生成：5 个部门，跳过 0 个",
      "phase": "planning",
      "department": null,
      "agent_id": null,
      "data": {
        "task_count": 5,
        "skipped_count": 0,
        "tasks": {"market_research": ["..."], ...},
        "skipped": []
      },
      "call_count": 1
    }
  ],
  "final_report": {
    "executive_summary": "...",
    "department_summaries": {...},
    "overall_score": 72.5,
    "cross_insights": [...],
    "recommendations": [...],
    "risks": [...],
    "dimension_confidence": {...}
  }
}
```

---

## POST /analyze/stream

SSE 流式推送，实时输出每个分析节点的进度事件。  
前端可据此渲染进度条、搜索动画、部门卡片等实时 UI。

**Request Body:**
```json
{
  "description": "我想做一个宠物社交App，连接同城的宠物主人"
}
```

**Response:** `text/event-stream`

```sse
event: plan_generated
data: {"event_type":"plan_generated","timestamp":"...","message":"...","phase":"planning","department":null,"agent_id":null,"data":{...},"call_count":1}

event: budget_update
data: {"event_type":"budget_update","timestamp":"...","message":"...","data":{"total_calls":1,"max_calls":30},"call_count":1}

event: department_start
data: {"event_type":"department_start","timestamp":"...","message":"部门启动: market_research","department":"market_research","data":{"focus_areas":["市场规模","用户画像"]},"call_count":1}

event: sub_agent_start
data: {"event_type":"sub_agent_start","timestamp":"...","message":"搜索启动: market_query_1","department":"market_research","agent_id":"market_query_1","data":{"search_query":"宠物社交App 市场规模"},"call_count":1}

event: sub_agent_search
data: {"event_type":"sub_agent_search","timestamp":"...","message":"搜索完成: market_query_1 (5 条结果)","department":"market_research","agent_id":"market_query_1","data":{"result_count":5},"call_count":1}

event: sub_agent_done
data: {"event_type":"sub_agent_done","timestamp":"...","message":"报告完成: market_query_1 (3 条发现)","department":"market_research","agent_id":"market_query_1","data":{"report_summary":"...","findings_count":3},"call_count":2}

event: sub_agent_review
data: {"event_type":"sub_agent_review","timestamp":"...","message":"审核: market_query_1 → passed (overall=7.5)","department":"market_research","agent_id":"market_query_1","data":{"verdict":"passed","overall_score":7.5,"credibility":7.0,"reason":""},"call_count":3}

event: department_done
data: {"event_type":"department_done","timestamp":"...","message":"部门完成: market_research (4 条要点, 可信度 75%)","department":"market_research","data":{"summary":"...","key_points_count":4,"overall_confidence":0.75,"status":"passed"},"call_count":4}

...（5 个部门各自完整事件流）...

event: budget_update
data: {"event_type":"budget_update","message":"...","data":{"total_calls":14,"max_calls":30},"call_count":14}

event: final_report
data: {"event_type":"final_report","timestamp":"...","message":"综合分析完成，评分 72/100","phase":"completed","data":{"executive_summary":"...","overall_score":72.5,...},"call_count":15}

event: done
data: {"event_type":"done","timestamp":"...","message":"分析流程结束","phase":"completed","data":{},"call_count":15}
```

### SSE 事件类型说明

| 事件类型 | 触发时机 | 关键 data 字段 |
|----------|---------|---------------|
| `plan_generated` | Top Agent 产出执行计划 | `task_count`, `skipped_count`, `tasks`, `skipped` |
| `budget_update` | LLM 调用计数变化 | `total_calls`, `max_calls` |
| `department_start` | 某中层部门开始执行 | `focus_areas` |
| `department_skip` | 某中层被计划跳过 | `reason` |
| `sub_agent_start` | 底层 SearchAgent 启动 | `search_query` |
| `sub_agent_search` | Tavily 搜索完成 | `result_count` |
| `sub_agent_done` | LLM 筛选分析完成 | `report_summary`, `findings_count` |
| `sub_agent_review` | 中层审核结果 | `verdict`, `overall_score`, `credibility`, `reason` |
| `department_done` | 部门综合分析完成 | `summary`, `key_points_count`, `overall_confidence`, `status` |
| `final_report` | CEO 综合报告完成 | **完整 FinalReport JSON**（含 executive_summary, overall_score 等全部字段） |
| `error` | 非致命错误 | `error` |
| `done` | 分析流程结束（**流关闭信号**） | 空 |

---

## GET /analyze/{thread_id}

中断恢复 / 进度查询端点。返回指定会话当前的所有事件和最终报告。

**使用场景：**
- SSE 连接中断后，用 `thread_id` 拉取当前进度
- 轮询模式下定期查询分析进度

**Response 200:**
```json
{
  "events": [...],
  "final_report": {"executive_summary": "...", ...}
}
```

**Response 404:**
```json
{
  "error": "会话不存在: sse-1719500000",
  "hint": "会话可能已过期或服务已重启"
}
```

> **注意：** 会话存储在内存中，服务重启后全部丢失。`thread_id` 在服务重启后无法恢复。
