"""
PM Agent 系统的全部数据模型定义。

这个文件是「唯一真源」(Single Source of Truth)：
- 所有 Agent 之间通信都使用这里定义的 Pydantic 类型
- 可以理解为所有 Agent 签订的「合同」——输入/输出格式以这里为准
- 新增字段或类型必须在这里改，不允许 Agent 自己发明数据格式

层级关系：
    GlobalState（顶层状态，LangGraph 全局共享）
    ├── ProjectInfo（用户输入的项目信息）
    ├── ExecutionPlan（顶层 Agent 生成的执行计划）
    ├── MarketResearchState（中层：市场调研）
    │   └── SubAgentSlot[]（底层子 Agent 管理槽）
    │       └── SubAgentOutput（子 Agent 输出）
    │           └── Finding[]（单条发现）
    ├── CompetitorState（中层：竞品分析）【Phase 2】
    ├── ProductDesignState（中层：产品设计）【Phase 2】
    ├── FutureState（中层：未来方向）【Phase 2】
    └── ChangeState（中层：当下改变）【Phase 2】

状态流转：
    用户输入 → Top Agent 生成计划 → 各中层并行/串行执行 → 顶层汇总 → 输出报告
"""

from __future__ import annotations

from enum import Enum
from operator import add as _op_add
from typing import Literal, TypedDict, Annotated

from pydantic import BaseModel, Field


# =============================================================================
# LangGraph 并行节点 Reducer 辅助函数
# =============================================================================

def _max_reducer(a: int, b: int) -> int:
    """并行节点写入 int 字段时取最大值（call_count 只增不减）。"""
    return max(a, b)


# =============================================================================
# 枚举类型（Enums）—— 限定可选值，防止拼写错误
# =============================================================================


class AgentStatus(str, Enum):
    """中层 / 底层 Agent 的当前状态"""
    RUNNING = "running"        # 正在执行（LangGraph 中）
    PASSED = "passed"          # 已通过（打分 ≥ 阈值，MVP 阶段默认通过）
    REJECTED = "rejected"      # 被驳回（需要重新执行）【MVP 预留，暂不使用】
    UNCERTAIN = "uncertain"    # 多次驳回仍不达标，标记「存疑」，放弃重试【MVP 预留】
    SKIPPED = "skipped"        # 被顶层计划跳过（该分析方向不适用于当前项目）
    IDLE = "idle"              # 尚未被调度


# =============================================================================
# 已知部门类型常量（发给 Top LLM 做推荐选项，Top 可自主增减）
# =============================================================================

KNOWN_DEPARTMENT_TYPES: list[str] = [
    "market_research",        # 市场调研
    "competitor_analysis",    # 竞品分析
    "product_design",         # 产品设计
    "future_direction",       # 未来方向
    "change_plan",            # 当下改变
]

KNOWN_DEPARTMENT_NAMES: dict[str, str] = {
    "market_research": "市场调研",
    "competitor_analysis": "竞品分析",
    "product_design": "产品设计",
    "future_direction": "未来方向",
    "change_plan": "当下改变",
}


class SourceType(str, Enum):
    """搜索来源的类型分类。

    用于底层 Agent 标注每条发现的数据来源类型，
    后续多源验证时会根据来源类型调整权重。
    """
    DATA = "data"            # 统计数据 / 行业报告 / 官方数据
    REPORT = "report"        # 媒体报道 / 分析文章
    OPINION = "opinion"      # 个人观点 / 博客 / 论坛帖子


# =============================================================================
# 基础数据类型 —— 用户输入 & 对话
# =============================================================================


class ProjectInfo(BaseModel):
    """用户输入的项目信息。

    顶层 Agent 在第一步接收这个对象，根据 completeness（完整度）
    决定是否追问更多边界条件。MVP 阶段假设用户输入已足够。
    """
    description: str = Field(
        default="",
        description="用户对项目/产品想法的原始描述，≤ 500 字"
    )
    target_market: str | None = Field(
        default=None,
        description="目标市场，如「中国市场」「北美 SaaS」。None = 用户没说，顶层需要追问"
    )
    budget_range: str | None = Field(
        default=None,
        description="预算范围，如「< 50 万」「未定」。None = 需要追问"
    )
    competitors_known: list[str] = Field(
        default_factory=list,
        description="用户已知的竞品名称列表。空列表 = 未提供"
    )
    extra_context: str | None = Field(
        default=None,
        description="用户补充的任何额外上下文"
    )


class Message(BaseModel):
    """对话历史中的一条消息。

    保留对话上下文用，顶层 Agent 在多轮追问时会读取历史消息。
    """
    role: Literal["user", "assistant", "system"] = Field(
        description="消息发送者角色"
    )
    content: str = Field(description="消息正文")


# =============================================================================
# 顶层 Agent 的输出 —— 执行计划
# =============================================================================


class DepartmentTask(BaseModel):
    """顶层 Agent 给一个中层部门下达的专属任务。

    Top LLM 为每个部门生成完整的任务描述 + 考核指标 + 搜索主题。
    """

    agent_type: str = Field(
        description="部门类型标识。预置值见 KNOWN_DEPARTMENT_TYPES，"
                    "Top LLM 可自创（如 'supply_chain_analysis'），最长 40 字符"
    )
    display_name: str = Field(
        default="",
        description="部门中文名，如 '市场调研'、'供应链分析'。Top LLM 自创部门时必须填写"
    )
    task_description: str = Field(
        default="",
        description="该部门的详细任务描述（≤ 200 字）。必须包含："
                    "① 分析什么 ② 为什么需要 ③ 至少 3 个具体分析方向。"
                    "中层拿到这个就能直接生成搜索策略"
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="该部门专属的关注维度，如 ['二手教材市场规模', '大学生购书渠道偏好']"
    )
    metrics: list[str] = Field(
        default_factory=list,
        description="Top 设定的考核指标（3-5 条），每条 ≤ 80 字。"
                    "中层分析时对照自评，CEO 汇总时审阅完成度。"
                    "如 '二手教材年交易额（中国高校）'、'学生购书渠道偏好数据'"
    )
    instruction: str = Field(
        default="",
        description="特别指令。Phase 2 驳回时由中层回写改进方向，"
                    "下一轮搜索时 LLM 读取以调整策略"
    )
    core_topic: str = Field(
        default="",
        description="搜索核心关键词（2-3 个词），如 '二手教材交易平台'，供搜索引擎拼接"
    )


class ExecutionPlan(BaseModel):
    """顶层 Agent 生成的 DAG 执行计划。

    顶层 Agent 读完用户的项目描述后，为每个需要跑的中层部门，
    各自生成专属的 DepartmentTask（含 focus_areas 和 instruction）。

    Phase 2 时：
    - 条件边根据 tasks 决定谁跑谁跳过
    - 驳回时修改对应 DepartmentTask 的 instruction
    """
    tasks: list[DepartmentTask] = Field(
        default_factory=list,
        description="需要执行的中层任务列表，每个任务专属一个部门"
    )
    skipped: list[str] = Field(
        default_factory=list,
        description="被跳过的部门类型标识列表，如 ['competitor_analysis']"
    )
    skip_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="跳过原因，key = 部门类型标识"
    )
    max_cycles: int = Field(
        default=3,
        description="每个中层最多被驳回几次"
    )


# =============================================================================
# 底层 Agent 的输出 —— 搜索结果 & 发现
# =============================================================================


class Finding(BaseModel):
    """底层搜索 Agent 返回的单条关键发现。

    每个底层 Agent 最多返回 5 条 Finding（由 prompts/templates.py 约束）。

    字段说明：
    - insight：核心发现，≤ 150 字。这是给中层 Leader 看的关键信息摘要
    - sourceUrl：来源 URL。防幻觉第一原则——每个结论必须有出处
    - sourceType：来源类型（data / report / opinion），影响可信度权重
    - relevance：相关度自评（1-10），< 5 的由底层自行丢弃，不上传
    - confidence：可信度自评（1-10），来自底层 Agent 对数据质量的判断
    """
    insight: str = Field(
        description="关键发现，≤ 150 字。一句话说清发现了什么、数据是多少"
    )
    source_url: str = Field(
        description="来源 URL。防幻觉底线——没有 URL 就不能输出这条发现"
    )
    source_type: SourceType = Field(
        description="来源类型：'data'(数据/报告) | 'report'(媒体/分析) | 'opinion'(个人观点)"
    )
    relevance: int = Field(
        ge=1, le=10,
        description="与任务的相关度自评（1-10），< 5 底层应自行过滤"
    )
    confidence: int = Field(
        ge=1, le=10,
        description="数据可信度自评（1-10），越高越可信"
    )


class BottomReport(BaseModel):
    """底层研究员产出的调研报告。

    不再是纯数据提取（SubAgentOutput），而是：
    1. 筛选：去掉低质、重复、广告
    2. 归类：按主题聚合相关结果
    3. 报告：撰写 ≤500 字综合判断
    4. 索引：保留每条发现的 source_url，中层可回查

    中层 Leader 收到这个后，既能看到底层的研究结论（report），
    也能核实原始数据（key_findings）。
    """
    report: str = Field(
        default="",
        description="底层研究员撰写的综合分析报告，≤ 500 字"
    )
    key_findings: list[Finding] = Field(
        default_factory=list,
        description="按相关度降序的关键发现，最多 5 条，每条含 source_url"
    )
    total_sources: int = Field(
        default=0,
        description="本次搜索返回的原始结果总数（含被筛选掉的）"
    )


# =============================================================================
# 驳回 + 打分机制
# =============================================================================


class ItemScore(BaseModel):
    """单条发现的打分结果。

    Phase 2 启用后，中层 Leader 对每条 Finding 进行四维打分，
    综合分 < 5 或可信度 < 4 触发驳回。

    四个维度的含义：
    - completeness（完整度）：信息是否充分、是否有关键数据缺失
    - credibility（可信度）：来源是否可靠（.gov > 头部媒体 > 个人博客）
    - freshness（时效性）：数据是否过时（看发布时间）
    - relevance（相关度）：与当前分析任务的匹配程度
    """
    completeness: float = Field(default=0.0, ge=0, le=10, description="完整度 0-10")
    credibility: float = Field(default=0.0, ge=0, le=10, description="可信度 0-10")
    freshness: float = Field(default=0.0, ge=0, le=10, description="时效性 0-10")
    relevance: float = Field(default=0.0, ge=0, le=10, description="相关度 0-10")

    @property
    def overall(self) -> float:
        """综合得分 = 四个维度的平均值"""
        return (self.completeness + self.credibility + self.freshness + self.relevance) / 4

    @property
    def is_rejected(self) -> bool:
        """判断是否应该被驳回：综合 < 5 或 可信度 < 4"""
        return self.overall < 5.0 or self.credibility < 4.0


class RejectionEntry(BaseModel):
    """一次驳回记录。

    只记录驳回原因和重做指令，不保存被驳回的完整输出（旧数据会干扰下一轮判断）。
    40 字节左右的简短记录即可提供足够的审计信息。
    """
    round: int = Field(description="第几轮被驳回（1-indexed）")
    reason: str = Field(description="驳回原因，如「可信度 3.2 < 4，来源为个人博客」")
    instruction: str = Field(description="给底层的改进指令，如「更换搜索词，优先找行业报告」")
    timestamp: str = Field(description="ISO 时间戳")


class SubAgentReview(BaseModel):
    """中层 Reviewer 对单个底层报告的审核结果。

    中层 Leader 在收集底层报告后，调 LLM 以 reviewer 角色审核每份报告的质量。
    低分触发驳回 → 用 improved_query 重新搜索（最多 3 轮）。
    """
    sub_id: str = Field(description="被审核的子 Agent ID")
    overall_score: float = Field(default=0.0, ge=0, le=10, description="综合分 0-10（四维平均）")
    completeness: float = Field(default=0.0, ge=0, le=10, description="完整度 0-10")
    credibility: float = Field(default=0.0, ge=0, le=10, description="可信度 0-10")
    freshness: float = Field(default=0.0, ge=0, le=10, description="时效性 0-10")
    relevance: float = Field(default=0.0, ge=0, le=10, description="相关度 0-10")
    verdict: Literal["passed", "rejected", "abandon"] = Field(
        default="passed",
        description="审核结论：passed=通过 | rejected=驳回 | abandon=放弃（多次重搜仍不达标）"
    )
    reason: str = Field(
        default="",
        description="驳回原因（≤ 100 字），如「来源均为个人博客，无权威数据」"
    )
    improved_query: str = Field(
        default="",
        description="改进后的搜索关键词（被驳回时必填），解决当前报告的短板"
    )


class ReviewResult(BaseModel):
    """一次审核的批量结果——LLM 审核所有待审子 Agent 后一次性输出。"""
    reviews: list[SubAgentReview] = Field(
        default_factory=list,
        description="每个待审子 Agent 一条审核结果"
    )


# =============================================================================
# 底层 Agent 的管理槽 —— SubAgentSlot
# =============================================================================

class SubAgentSlot(BaseModel):
    """管理一个底层子 Agent 的「卡槽」。

    中层 Leader 通过一个 dict[str, SubAgentSlot] 管理所有底层子 Agent：
    - key = Agent 的 ID（如 "market_size_query"）
    - value = SubAgentSlot（最新输出 + 状态 + 驳回日志）

    设计要点：
    - 只存最新一轮的输出（latest_output），旧数据被驳回后直接覆盖
    - 驳回不存完整历史数据，只在 rejection_log 里记原因摘要
    - 这样中层在决策时只看当前有效数据，不会被旧数据混淆

    MVP 阶段：
    - 每个子 Agent 只执行一次，不触发驳回
    - status 永远是 PASSED（通过）或 SKIPPED（跳过）
    """
    sub_id: str = Field(description="子 Agent 的唯一标识，如 'market_size_query'")
    search_query: str = Field(default="", description="当前使用的搜索关键词")
    latest_output: BottomReport | None = Field(
        default=None, description="最新一轮底层研究报告（只保留最新，旧数据被覆盖）"
    )
    round_number: int = Field(default=1, description="当前是第几轮（1-indexed），MVP 固定为 1")
    rejection_log: list[RejectionEntry] = Field(
        default_factory=list, description="驳回原因链（按时间顺序），MVP 为空列表"
    )
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="本轮状态")


# =============================================================================
# 中层 Agent 的 State 定义
# =============================================================================


class AnalysisPoint(BaseModel):
    """中层 Leader 输出的单条分析要点。

    中层 Leader 整理完底层发现后，输出 ≤ 8 条 AnalysisPoint。
    每条 ≤ 200 字，包含结论和来源支撑。
    """
    title: str = Field(description="分析要点标题，≤ 30 字")
    content: str = Field(description="分析内容，≤ 200 字，必须包含数据或来源支撑")
    confidence_level: Literal["high", "medium", "low", "uncertain"] = Field(
        description="该结论的可信度等级：high(多源印证) | medium(单源但可靠) | low(存疑) | uncertain(数据不足)"
    )
    source_count: int = Field(default=0, description="支撑该结论的独立来源数量")
    related_finding_indices: list[int] = Field(
        default_factory=list,
        description="关联的底层 Finding 索引（方便溯源）"
    )


class DepartmentState(BaseModel):
    """单个中层部门的完整状态 —— 预置和自定义部门共用。

    分两层设计：
    - Public 字段（顶层可读）：summary、key_points、overall_confidence、status
    - Internal 字段（中层自己用）：项目信息、子 Agent 槽位、循环计数

    设计要点：顶层 Leader 汇总时只需要读 key_points，不需要知道底层细节。
    """

    # ===== Public 接口（CEO 汇总读取） =====
    summary: str | None = Field(
        default=None,
        description="本部门 ≤ 200 字摘要"
    )
    key_points: list[AnalysisPoint] = Field(
        default_factory=list,
        description="≤ 8 条分析要点，按重要性降序"
    )
    overall_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="本部门整体可信度（0.0~1.0），基于来源权威度加权"
    )

    # ===== 部门判断（CEO 读取的决策级输出） =====
    conclusion: str = Field(
        default="",
        description="部门结论（≤ 200 字）。不是数据复述，而是该领域专家的核心判断——"
                    "「基于以上数据，我认为...」"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="部门给 CEO 的建议（≤ 3 条），每条 ≤ 100 字"
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="本部门数据缺口（≤ 3 条），明确标注哪些维度数据不足"
    )
    metrics_coverage: dict[str, str] = Field(
        default_factory=dict,
        description="Top 设定的考核指标完成情况。key=指标原文，value=完成状态"
                    "（'已覆盖'/'部分覆盖'/'未覆盖'）"
    )

    # ===== 控制状态 =====
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="本部门当前状态")

    # ===== Internal 字段（顶层不碰，中层自己用） =====
    project: dict = Field(default_factory=dict, description="顶层传入的项目信息（裁剪版）")
    focus_direction: str = Field(default="", description="本中层关注的细分方向")
    sub_agents: dict[str, SubAgentSlot] = Field(
        default_factory=dict,
        description="底层子 Agent 管理槽。key 如 'market_size' / 'user_profile'"
    )
    cycle_count: int = Field(default=0, description="本部门整体循环/驳回次数")
    department_type: str = Field(default="", description="部门类型标识（如 'market_research'）")


# =============================================================================
# 内层审核子图 State（LangGraph 管理每部门内的 search → review 循环）
# =============================================================================


class AgentSlot(BaseModel):
    """单个底层子 Agent 的完整状态槽 —— review 每次覆盖，round 独立计数。

    设计要点：
    - 每个 agent 有自己的 round 计数器（不像全局 cycle_count 一刀切）
    - review 每次覆盖（不保留历史），report 在审核完成后覆盖（无论 passed/rejected）
    - key_findings_summary 保留 ≤5 条摘要供中层综合分析引用
    """

    sub_id: str = Field(description="子 Agent ID，如 'marketresearch_2'")
    search_query: str = Field(default="", description="当前搜索关键词（rejected 时更新为 improved_query）")
    report: BottomReport | None = Field(default=None, description="最新搜索报告（审核后覆盖）")
    review: SubAgentReview | None = Field(default=None, description="最新审核结果（每次覆盖）")
    key_findings_summary: list[str] = Field(
        default_factory=list,
        description="本轮 ≤5 条关键发现摘要（≤150 字/条），供中层分析引用"
    )
    round: int = Field(default=0, description="当前轮次（1-indexed），独立于其他 agent")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="本轮状态")


class ReviewState(BaseModel):
    """内层审核子图的全局 State —— 一个部门内的 search→review 循环。

    LangGraph 的 checkpoint 保存此 State，支持：
    - 暂停 → 注入 task.instruction 或 agent_slots 的 search_query
    - 恢复 → agent 从各自的 round 断点继续
    """

    # ===== 部门上下文 =====
    dept_key: str = Field(default="", description="部门标识，如 'market_research'")
    display_name: str = Field(default="", description="部门中文名")
    project_summary: str = Field(default="", description="项目描述摘要")
    task: DepartmentTask | None = Field(default=None, description="顶层下发的任务（暂停时可改 instruction）")

    # ===== 子 Agent 结果槽 =====
    agent_slots: dict[str, AgentSlot] = Field(
        default_factory=dict,
        description="所有底层子 Agent 的状态槽，key=sub_id"
    )
    max_rounds_per_agent: int = Field(default=5, description="单 agent 最大重试轮数（防死循环）")

    @property
    def unresolved_ids(self) -> list[str]:
        """返回还需处理的 agent ID（IDLE 或 REJECTED）。"""
        return [
            sid for sid, slot in self.agent_slots.items()
            if slot.status in (AgentStatus.IDLE, AgentStatus.REJECTED)
        ]

    @property
    def is_done(self) -> bool:
        """所有 agent 都已 PASSED 或 UNCERTAIN（abandon）→ 子图结束。"""
        return len(self.unresolved_ids) == 0


# =============================================================================
# 全局 State（GlobalState）—— LangGraph 的共享上下文
# =============================================================================


class GlobalState(BaseModel):
    """顶层 Agent 的全局 State，LangGraph 各节点共享。

    设计原则（来自 CLAUDE.md）：
    1. 全局 State 只做「路由索引」—— 顶层不关心中层内部细节
    2. department_results 以 dict 管理所有部门结果 —— key = department_type，增删灵活
    3. 顶层读中层时只看 .summary / .key_points / .overall_confidence / .status
    4. 驳回不存历史数据，只存最新一轮输出 + 驳回原因链

    控制字段：
    - total_api_calls / max_api_calls：Token 预算熔断器
    - current_phase：当前执行阶段，用于 SSE 推送进度
    - errors：收集非致命错误，最后汇入报告
    """

    # ===== 用户输入 =====
    project: ProjectInfo = Field(default_factory=ProjectInfo, description="用户的项目信息")
    conversation_history: list[Message] = Field(
        default_factory=list, description="对话历史（多轮追问用）"
    )

    # ===== 顶层执行计划 =====
    execution_plan: ExecutionPlan | None = Field(
        default=None, description="顶层 Agent 生成的执行计划（决定谁跑、谁跳过）"
    )

    # ===== 中层结果 —— dict 管理，key = department_type，增删部门灵活 =====
    department_results: dict[str, DepartmentState] = Field(
        default_factory=dict,
        description="所有中层部门的执行结果。key='market_research' 等，value=DepartmentState"
    )

    # ===== 全局控制 =====
    total_api_calls: Annotated[int, _max_reducer] = Field(
        default=0, description="已消耗的 LLM API 调用次数"
    )
    max_api_calls: int = Field(default=60, description="LLM 调用硬上限（熔断器）")
    current_phase: str = Field(default="init", description="当前执行阶段标识")
    errors: Annotated[list[str], _op_add] = Field(
        default_factory=list, description="非致命错误收集"
    )


# =============================================================================
# CEO 汇总报告类型（Top Agent 交叉分析产出）
# =============================================================================


class CrossInsight(BaseModel):
    """跨部门交叉洞察 —— 两个以上中层结论的交叉点。

    不是单部门结论的复述，而是「市场说 X + 竞品说 Y → 所以 Z」。
    """

    title: str = Field(..., description="洞察标题（≤ 30 字）")
    insight: str = Field(..., description="交叉分析内容（≤ 200 字）")
    involved_dimensions: list[str] = Field(
        default_factory=list,
        description="涉及的中层部门，如 ['market_research', 'competitor_analysis']",
    )
    confidence: float = Field(default=0.5, description="交叉验证后的综合置信度 0-1")


class Recommendation(BaseModel):
    """战略建议 —— 基于数据的产品/业务行动建议。"""

    priority: int = Field(default=1, description="优先级，1=最高")
    title: str = Field(..., description="建议标题（≤ 30 字）")
    rationale: str = Field(..., description="建议理由（≤ 200 字），基于哪些数据")
    related_dimensions: list[str] = Field(
        default_factory=list,
        description="支撑此建议的中层部门",
    )


class RiskFlag(BaseModel):
    """风险标记 —— 数据不足、部门矛盾、可信度低等问题。"""

    severity: Literal["high", "medium", "low"] = Field(
        default="medium", description="严重程度"
    )
    title: str = Field(..., description="风险标题（≤ 30 字）")
    description: str = Field(..., description="风险描述（≤ 150 字）")
    related_dimension: str = Field(
        default="", description="来源部门，如 'market_research'"
    )


class FinalReport(BaseModel):
    """Top Agent（CEO）综合各中层结果后产出的最终报告。

    结构：执行摘要 → 各部门报告 → 交叉洞察 → 战略建议 → 风险 → 评分。
    不是中层数据的简单罗列，而是跨部门交叉分析后的战略级输出。
    """

    # ===== 一、执行摘要（300~800 字） =====
    executive_summary: str = Field(
        default="",
        description="执行摘要（300~800 字），包含：项目概述、核心市场判断、"
                    "最关键的机会与风险、综合结论。不是一句话，而是完整的决策摘要",
    )

    # ===== 二、各部门报告（CEO 对每个部门的提炼 + 部门自己的判断） =====
    department_summaries: dict[str, str] = Field(
        default_factory=dict,
        description="各部门摘要。key=部门名，value=CEO提炼的该部门要点（含部门结论和建议，≤300字/部门）",
    )

    # ===== 三、综合评分 =====
    overall_score: float = Field(
        default=50.0, description="项目综合可行性评分 0-100"
    )

    # ===== 四、跨部门交叉洞察 =====
    cross_insights: list[CrossInsight] = Field(
        default_factory=list, description="跨部门交叉洞察（≤ 5 条）"
    )

    # ===== 五、战略建议 =====
    recommendations: list[Recommendation] = Field(
        default_factory=list, description="按优先级排列的战略建议（≤ 5 条）"
    )

    # ===== 六、风险与不确定性 =====
    risks: list[RiskFlag] = Field(
        default_factory=list, description="风险与不确定性（≤ 5 条）"
    )

    # ===== 七、各部门可信度 =====
    dimension_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="各中层部门的整体可信度汇总",
    )


# =============================================================================
# 搜索相关的数据类型
# =============================================================================


class SearchStrategy(BaseModel):
    """中层 LLM 自主生成的搜索策略 —— 替代硬编码字符串拼接。

    中层 Leader 收到 DepartmentTask 后，调 LLM 输出此 schema，
    决定：搜索什么、搜几个方向、为什么。
    """

    queries: list[str] = Field(
        default_factory=list,
        min_items=1, max_items=5,
        description="搜索关键词列表（1-5 个），按优先级降序。每个词 ≤ 80 字符"
    )
    reasoning: str = Field(
        default="",
        description="选这些搜索方向的原因（≤ 100 字），供中层 Leader 理解搜索意图"
    )


class SearchOptions(BaseModel):
    """搜索参数配置。

    传给 SearchProvider.search() 的选项，控制搜索行为。
    """
    max_results: int = Field(default=5, description="最大返回结果数，默认 5")
    include_domains: list[str] = Field(
        default_factory=list, description="限定搜索域名（如 ['tradingeconomics.com']）"
    )
    exclude_domains: list[str] = Field(
        default_factory=list, description="排除域名（如 ['zhihu.com'] 排除中文社区）"
    )
    search_depth: Literal["basic", "advanced"] = Field(
        default="basic", description="搜索深度：basic(快速) | advanced(深度，耗时更长)"
    )


class SearchResult(BaseModel):
    """Search Provider 返回的单条搜索结果。

    这是 Provider 无关的通用格式——无论 Tavily、Google、Bing，
    返回的结果都统一转换成这个格式。
    """
    title: str = Field(description="搜索结果标题")
    url: str = Field(description="结果 URL")
    content: str = Field(description="搜索结果摘要/正文片段")
    score: float = Field(default=0.0, description="搜索相关度得分（Provider 返回的原始值）")
    published_date: str | None = Field(default=None, description="发布时间（如有）")


# =============================================================================
# SSE 进度事件类型
# =============================================================================


class SSEEventType(str, Enum):
    """SSE 推送的事件类型枚举 —— 覆盖全链路关键节点。"""
    PLAN_GENERATED = "plan_generated"           # Top Agent 产出 ExecutionPlan
    DEPARTMENT_START = "department_start"        # 某中层开始执行
    DEPARTMENT_SKIP = "department_skip"          # 某中层被计划跳过
    SUB_AGENT_START = "sub_agent_start"          # 底层 SearchAgent 启动搜索
    SUB_AGENT_SEARCH = "sub_agent_search"        # Tavily 搜索完成（返回条数）
    SUB_AGENT_DONE = "sub_agent_done"            # LLM 筛选+分析完成（含报告摘要）
    SUB_AGENT_REVIEW = "sub_agent_review"        # 审核结果（passed/rejected + 四维分）
    DEPARTMENT_DONE = "department_done"          # 中层综合分析完成
    FINAL_REPORT = "final_report"                # CEO 汇总 FinalReport JSON
    BUDGET_UPDATE = "budget_update"              # LLM 调用计数更新
    ERROR = "error"                              # 非致命错误
    DONE = "done"                                # 分析流程结束


class ProgressEvent(BaseModel):
    """SSE 流式推送的进度事件。

    每个关键节点发出一个 ProgressEvent，前端可据此渲染进度条、搜索动画、
    部门卡片等实时 UI。data 字段的 key 因 event_type 而异，文档详见每个 emit 点。
    """
    event_type: SSEEventType = Field(description="事件类型")
    timestamp: str = Field(description="ISO 8601 时间戳")
    message: str = Field(default="", description="人类可读消息")
    phase: str | None = Field(default=None, description="当前阶段")
    department: str | None = Field(default=None, description="部门名")
    agent_id: str | None = Field(default=None, description="子 Agent ID")
    data: dict = Field(default_factory=dict, description="结构化 payload")
    call_count: int = Field(default=0, description="当前 LLM API 调用计数")
