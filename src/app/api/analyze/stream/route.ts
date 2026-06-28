/**
 * SSE Proxy — 转发浏览器请求到 Python FastAPI 后端。
 *
 * 为什么需要 proxy：
 * 1. 同源策略 — 浏览器只和 Next.js :3000 通信，不直接调 FastAPI :8000
 * 2. 隐藏后端地址 — FastAPI URL 不出现在前端代码中
 * 3. 鉴权插槽 — 后续可在此处添加 auth middleware
 *
 * POST /api/analyze/stream
 *   → POST http://localhost:8000/analyze/stream
 *   → 透传 SSE text/event-stream
 */

const BACKEND_URL =
  process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  // ---- 1. 解析请求体 ----
  let body: { description?: string };
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "请求体必须是 JSON" },
      { status: 400 }
    );
  }

  const { description } = body;
  if (!description || typeof description !== "string" || !description.trim()) {
    return Response.json(
      { error: "description 不能为空" },
      { status: 400 }
    );
  }

  // ---- 2. 转发到 FastAPI ----
  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/analyze/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: description.trim() }),
      // Node.js fetch 没有内置超时；后续可加 AbortController
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json(
      {
        error: "无法连接到后端分析服务",
        detail: msg,
        hint: `请确保 FastAPI 已启动: cd agent-backend && uvicorn main:app --port 8000`,
      },
      { status: 502 }
    );
  }

  // ---- 3. 检查后端响应 ----
  if (!backendResponse.ok) {
    // 尝试读取后端错误体
    let detail = "";
    try {
      const errBody = await backendResponse.text();
      detail = errBody.slice(0, 500);
    } catch {
      // ignore
    }
    return Response.json(
      {
        error: `后端返回错误 (${backendResponse.status})`,
        detail,
      },
      { status: 502 }
    );
  }

  // ---- 4. 流式透传 SSE ----
  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
