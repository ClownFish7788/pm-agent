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


class MiddleAgentType(str, Enum):
    """中层 Agent 的类型标识。

    顶层 Agent 在执行计划中通过这个枚举指定「谁来跑」。
    MVP 阶段只接一个 MarketResearch，其余预留。
    """
    MARKET_RESEARCH = "market_research"       # 市场调研
    COMPETITOR_ANALYSIS = "competitor_analysis"  # 竞品分析【预留】
    PRODUCT_DESIGN = "product_design"         # 产品设计【预留】
    FUTURE_DIRECTION = "future_direction"     # 未来方向【预留】
    CHANGE_PLAN = "change_plan"               # 当下改变【预留】


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


class ExecutionPlan(BaseModel):
    """顶层 Agent 生成的 DAG 执行计划。

    顶层 Agent 读完用户的项目描述后，决定：
    1. 哪些中层需要跑（market / competitor / product / future / change）
    2. 谁先谁后（串行顺序），谁能同时跑（并行）
    3. 谁直接被跳过（比如做一个开源工具类项目，可能不需要竞品分析）

    MVP 阶段：只跑 market_research，其余全部 skipped。
    """
    steps: list[MiddleAgentType] = Field(
        description="按执行顺序排列的中层 Agent 列表。"
                    "相同优先级的可以并行；MVP 只放一个 MARKET_RESEARCH"
    )
    skipped: list[MiddleAgentType] = Field(
        default_factory=list,
        description="被跳过的中层 Agent 列表及跳过原因"
    )
    skip_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="跳过原因映射，key = MiddleAgentType.value，value = 原因文字"
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="本次分析需要重点关注的维度，如 ['市场规模', '用户画像', '商业模式']"
    )
    max_cycles: int = Field(
        default=3,
        description="每个中层最多被驳回几次。MVP 阶段固定为 3 但不启用驳回"
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


class SubAgentOutput(BaseModel):
    """底层搜索 Agent 的标准化输出。

    这是所有底层 Agent 必须遵守的输出格式。中层 Leader 接收这个对象，
    不做任何格式转换，保证接口统一。

    字段说明：
    - summary：一句话总结（≤ 80 字），中层 Leader 第一步先扫描所有 summary 快速定位
    - top_findings：按相关度降序排列的发现列表，最多 5 条
    - total_results：Tavily 返回的原始搜索结果总数（用于参考，不影响分析）
    """
    summary: str = Field(
        description="一句话总结本此搜索的核心发现，≤ 80 字"
    )
    top_findings: list[Finding] = Field(
        default_factory=list,
        description="按相关度(relevance)降序排列的发现列表，最多 5 条"
    )
    total_results: int = Field(
        default=0,
        description="原始搜索返回的总结果数（供中层参考数据量级）"
    )


# =============================================================================
# 驳回机制的数据结构（M——预留，不实现）
# =============================================================================


class ItemScore(BaseModel):
    """单条发现的打分结果。

    【MVP 预留】—— Phase 1 不调用打分逻辑，所有条目默认「通过」。
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

    【MVP 预留】—— Phase 1 不产生驳回。
    只记录驳回原因和重做指令，不保存被驳回的完整输出（旧数据会干扰下一轮判断）。
    40 字节左右的简短记录即可提供足够的审计信息。
    """
    round: int = Field(description="第几轮被驳回（1-indexed）")
    reason: str = Field(description="驳回原因，如「可信度 3.2 < 4，来源为个人博客」")
    instruction: str = Field(description="给底层的改进指令，如「更换搜索词，优先找行业报告」")
    timestamp: str = Field(description="ISO 时间戳")


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
    latest_output: SubAgentOutput | None = Field(
        default=None, description="最新一轮 LLM 输出（只保留最新，旧数据被覆盖）"
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


class MarketResearchState(BaseModel):
    """中层「市场调研」Leader 的完整状态。

    分两层设计：
    - Public 字段（顶层可读）：summary、key_points、overall_confidence、status
    - Internal 字段（中层自己用）：项目信息、子 Agent 槽位、循环计数

    顶层 Leader 汇总时只需要读 key_points，不需要知道底层细节。
    这样修改中层内部逻辑时不会影响顶层。

    MVP 阶段 key_points 限制 ≤ 5 条（后续扩展到 8 条）。
    """
    # ===== Public 接口（顶层 Agent 只读这三个 + status） =====
    summary: str | None = Field(
        default=None,
        description="本部门 ≤ 200 字摘要，供顶层快速了解结论"
    )
    key_points: list[AnalysisPoint] = Field(
        default_factory=list,
        description="≤ 8 条分析要点（MVP 阶段 ≤ 5 条），按重要性降序"
    )
    overall_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="本部门整体可信度（0.0~1.0），基于来源权威度加权"
    )

    # ===== 控制状态 =====
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="本部门当前状态")

    # ===== Internal 字段（顶层不碰，中层自己用） =====
    project: dict = Field(default_factory=dict, description="顶层传入的项目信息（裁剪版）")
    focus_direction: str = Field(default="", description="本中层关注的细分方向")
    sub_agents: dict[str, SubAgentSlot] = Field(
        default_factory=dict,
        description="底层子 Agent 管理槽。key='market_size'/'user_profile'/'business_model' 等"
    )
    cycle_count: int = Field(default=0, description="本部门整体循环/驳回次数，MVP 固定为 0")


# =============================================================================
# 其余中层 State（MVP —— 预留壳子，Phase 2 填充）
# =============================================================================


class CompetitorState(BaseModel):
    """竞品分析中层 State —— 【MVP 预留壳子】"""
    summary: str | None = None
    key_points: list[AnalysisPoint] = Field(default_factory=list)
    overall_confidence: float = 0.0
    status: AgentStatus = AgentStatus.IDLE
    project: dict = Field(default_factory=dict)
    sub_agents: dict[str, SubAgentSlot] = Field(default_factory=dict)
    cycle_count: int = 0


class ProductDesignState(BaseModel):
    """产品设计中层 State —— 【MVP 预留壳子】"""
    summary: str | None = None
    key_points: list[AnalysisPoint] = Field(default_factory=list)
    overall_confidence: float = 0.0
    status: AgentStatus = AgentStatus.IDLE
    project: dict = Field(default_factory=dict)
    sub_agents: dict[str, SubAgentSlot] = Field(default_factory=dict)
    cycle_count: int = 0


class FutureState(BaseModel):
    """未来方向中层 State —— 【MVP 预留壳子】"""
    summary: str | None = None
    key_points: list[AnalysisPoint] = Field(default_factory=list)
    overall_confidence: float = 0.0
    status: AgentStatus = AgentStatus.IDLE
    project: dict = Field(default_factory=dict)
    sub_agents: dict[str, SubAgentSlot] = Field(default_factory=dict)
    cycle_count: int = 0


class ChangeState(BaseModel):
    """当下改变中层 State —— 【MVP 预留壳子】"""
    summary: str | None = None
    key_points: list[AnalysisPoint] = Field(default_factory=list)
    overall_confidence: float = 0.0
    status: AgentStatus = AgentStatus.IDLE
    project: dict = Field(default_factory=dict)
    sub_agents: dict[str, SubAgentSlot] = Field(default_factory=dict)
    cycle_count: int = 0


# =============================================================================
# 全局 State（GlobalState）—— LangGraph 的共享上下文
# =============================================================================


class GlobalState(BaseModel):
    """顶层 Agent 的全局 State，LangGraph 各节点共享。

    设计原则（来自 CLAUDE.md）：
    1. 全局 State 只做「路由索引」—— 顶层不关心中层内部细节
    2. 每个中层有独立子 State —— 字段名不冲突，修改中层不影响其他中层
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

    # ===== 中层结果（顶层只读 Public 字段） =====
    market_research: MarketResearchState | None = Field(
        default=None, description="市场调研结果"
    )
    competitor_analysis: CompetitorState | None = Field(
        default=None, description="竞品分析结果【预留】"
    )
    product_design: ProductDesignState | None = Field(
        default=None, description="产品设计结果【预留】"
    )
    future_direction: FutureState | None = Field(
        default=None, description="未来方向结果【预留】"
    )
    change_plan: ChangeState | None = Field(
        default=None, description="当下改变结果【预留】"
    )

    # ===== 全局控制 =====
    # total_api_calls 用 max reducer：并行节点都写绝对值，取最新值即可
    total_api_calls: Annotated[int, _max_reducer] = Field(
        default=0, description="已消耗的 LLM API 调用次数"
    )
    max_api_calls: int = Field(default=30, description="LLM 调用硬上限（熔断器）")
    current_phase: str = Field(default="init", description="当前执行阶段标识")
    # errors 用 add reducer：并行节点各自追加错误，不会被覆盖
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

    这不是中层数据的简单罗列，而是跨部门交叉分析后的战略级输出。
    """

    executive_summary: str = Field(
        default="", description="≤ 300 字执行摘要，CEO 一句话说清结论"
    )
    overall_score: float = Field(
        default=50.0, description="项目综合可行性评分 0-100"
    )

    # 跨部门交叉洞察
    cross_insights: list[CrossInsight] = Field(
        default_factory=list, description="跨部门交叉洞察（≤ 5 条）"
    )

    # 战略建议
    recommendations: list[Recommendation] = Field(
        default_factory=list, description="按优先级排列的战略建议（≤ 5 条）"
    )

    # 风险
    risks: list[RiskFlag] = Field(
        default_factory=list, description="风险与不确定性（≤ 5 条）"
    )

    # 各维度信心
    dimension_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="各中层部门的整体可信度汇总",
    )


# =============================================================================
# 搜索相关的数据类型
# =============================================================================


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
