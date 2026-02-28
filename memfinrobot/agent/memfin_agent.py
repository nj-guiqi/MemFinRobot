"""MemFinRobot 主智能体 - 基于qwen-agent的FnCallAgent扩展"""

import copy
import logging
import time
from typing import Any, Dict, Iterator, List, Literal, Optional, Union

from qwen_agent import Agent
from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, FUNCTION, Message, SYSTEM, USER
from qwen_agent.tools import BaseTool

from memfinrobot.memory.manager import MemoryManager
from memfinrobot.memory.schemas import RecallResult, SessionState, UserProfile
from memfinrobot.compliance.guard import ComplianceGuard
from memfinrobot.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# 最大LLM调用次数
MAX_LLM_CALL_PER_RUN = 10

# 系统提示词
MEMFIN_SYSTEM_PROMPT = """你是MemFinRobot，一个专业的智能理财顾问助手。你的职责是为用户提供证券投资（基金/股票/债券等）的陪伴式咨询服务。

## 核心原则
1. **决策辅助**：你是决策辅助工具，不是投资决策者。不做具体的买卖指令建议。
2. **风险提示**：始终提供风险提示，不承诺收益。
3. **个性化服务**：基于用户画像和历史对话提供个性化建议。
4. **信息透明**：说明信息来源和时效性，承认不确定性。

## 服务范围
- 行情信息查询与解读
- 产品（基金/股票/债券）信息介绍
- 风险识别与提示
- 资产配置思路讨论
- 投资教育与知识普及

## 禁止行为
- 给出具体买卖点位或指令
- 承诺投资收益
- 声称有内幕消息
- 做出确定性的市场预测

## 回复要求
1. 回复要专业、客观、有理有据
2. 涉及产品或建议时，必须附带风险提示
3. 当用户画像不完整时，适时询问以完善画像
4. 引用历史对话时说明来源"""

RISK_FULL_TRIGGER_KEYWORDS = (
    "基金", "股票", "债券", "etf", "配置", "收益", "回撤", "波动", "资产",
    "仓位", "买入", "卖出", "投资", "理财", "组合", "年化", "估值", "行情",
)
RISK_FACT_QUERY_HINTS = (
    "什么是", "定义", "概念", "含义", "区别", "科普", "解释", "术语", "英文", "缩写",
)
RISK_INTENT_HINTS = (
    "建议", "配置", "收益", "回撤", "买", "卖", "产品", "组合", "风险",
)

RISK_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "no_guaranteed_return": ["不保证收益", "不保证本金", "不保本", "收益不确定"],
    "not_buy_sell_advice": ["不构成买卖建议", "不构成个股买卖建议"],
    "market_uncertainty": ["市场存在不确定性", "市场不确定性", "不确定性", "市场有风险"],
}

RISK_PHRASE_VARIANTS: Dict[str, List[str]] = {
    "no_guaranteed_return": [
        "收益不确定，不保证收益",
        "投资结果受市场影响，不保证本金",
        "任何配置都可能偏离预期，不保本",
        "过往表现不代表未来，不保证收益",
    ],
    "not_buy_sell_advice": [
        "以上分析不构成买卖建议",
        "以上内容不构成个股买卖建议",
        "上述观点不构成买卖建议",
    ],
    "market_uncertainty": [
        "市场存在不确定性",
        "市场波动可能导致结果偏离预期，存在不确定性",
        "市场有风险，短期变化具有不确定性",
    ],
}

RISK_MINIMAL_BLOCK_VARIANTS = [
    "以上仅供信息参考，不构成买卖建议，市场存在不确定性，不保证收益。",
    "以上内容不构成个股买卖建议，市场有风险且存在不确定性，投资不保本。",
    "仅作交流参考，不构成买卖建议；市场不确定性较高，且不保证收益。",
]


class MemFinFnCallAgent(FnCallAgent):
    """
    MemFinRobot 主智能体
    
    基于 qwen-agent 的 FnCallAgent 扩展，集成：
    - 记忆管理（长期/短期/画像）
    - 合规审校
    - 工具调用
    """
    
    def __init__(
        self,
        function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
        system_message: Optional[str] = None,
        name: Optional[str] = "MemFinRobot",
        description: Optional[str] = "面向证券投资的记忆增强型智能理财顾问",
        settings: Optional[Settings] = None,
        memory_manager: Optional[MemoryManager] = None,
        compliance_guard: Optional[ComplianceGuard] = None,
        observer: Optional[Any] = None,
        **kwargs,
    ):
        """
        初始化MemFinRobot智能体
        
        Args:
            function_list: 工具列表
            llm: LLM配置或实例
            system_message: 系统提示词
            name: 智能体名称
            description: 智能体描述
            settings: 配置对象
            memory_manager: 记忆管理器
            compliance_guard: 合规审校器
            observer: 评测观测器（可选）
        """
        # 使用默认系统提示词
        if system_message is None:
            system_message = MEMFIN_SYSTEM_PROMPT
        
        # 初始化父类
        super().__init__(
            function_list=function_list,
            llm=llm,
            system_message=system_message,
            name=name,
            description=description,
            **kwargs,
        )
        
        # 配置
        self.settings = settings or get_settings()
        
        # 记忆管理器
        if memory_manager:
            self.memory_manager = memory_manager
        else:
            self.memory_manager = MemoryManager(
                settings=self.settings,
                llm_client=self.llm,
            )
        
        # 合规审校器
        if compliance_guard:
            self.compliance_guard = compliance_guard
        else:
            self.compliance_guard = ComplianceGuard(
                settings=self.settings,
            )
        
        # 会话状态缓存
        self._sessions: Dict[str, SessionState] = {}
        
        # 可选观测器（用于评测trace）
        self.observer = observer
    
    def _run(
        self,
        messages: List[Message],
        lang: Literal['en', 'zh'] = 'zh',
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Iterator[List[Message]]:
        """
        运行智能体的核心流程
        
        1. 获取/创建会话状态
        2. 调用记忆召回获取上下文
        3. 组装增强后的消息
        4. 进入工具调用循环
        5. 生成后风险表达补足
        6. 合规审校
        7. 更新记忆
        
        Args:
            messages: 输入消息列表
            lang: 语言
            session_id: 会话ID
            user_id: 用户ID
            
        Yields:
            响应消息列表
        """
        messages = copy.deepcopy(messages)
        turn_start_ts = time.perf_counter()
        
        # 1. 获取/创建会话状态
        session_state = self._get_or_create_session(
            session_id=session_id,
            user_id=user_id,
        )
        turn_pair_id = (session_state.turn_count // 2) + 1
        
        # 2. 提取当前查询
        current_query = self._extract_current_query(messages)
        if current_query:
            self._emit_observer(
                event="turn_start",
                payload={
                    "session_id": session_state.session_id,
                    "user_id": session_state.user_id,
                    "turn_pair_id": turn_pair_id,
                    "query": current_query,
                },
            )
        
        # 3. 记忆召回
        memory_context = ""
        if current_query:
            try:
                recall_result = self.memory_manager.recall_for_query(
                    query=current_query,
                    session_state=session_state,
                )
                memory_context = recall_result.packed_context
                self._emit_observer(
                    event="recall_done",
                    payload={
                        "session_id": session_state.session_id,
                        "user_id": session_state.user_id,
                        "turn_pair_id": turn_pair_id,
                        "query": current_query,
                        "short_term_context": recall_result.short_term_context,
                        "short_term_turns": session_state.get_recent_history(n=3),
                        "profile_context": recall_result.profile_context,
                        "packed_context": recall_result.packed_context,
                        "token_count": recall_result.token_count,
                        "recalled_items": [
                            {
                                "id": item.id,
                                "content": item.hierarchical_content or item.content,
                                "score": score,
                                "source": source,
                                "turn_index": item.turn_index,
                                "session_id": item.session_id,
                            }
                            for item, score, source in zip(
                                recall_result.items,
                                recall_result.scores,
                                recall_result.sources,
                            )
                        ],
                    },
                )
            except Exception as e:
                logger.warning(f"Memory recall failed: {e}")
        
        # 4. 注入记忆上下文到系统消息
        if memory_context:
            messages = self._inject_memory_context(messages, memory_context) # 把最近对话 + 召回记忆
        
        # 5. 工具调用循环（继承自FnCallAgent）
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        response = []
        final_content = ""
        
        while num_llm_calls_available > 0:
            num_llm_calls_available -= 1
            
            extra_generate_cfg = {'lang': lang}
            if kwargs.get('seed') is not None:
                extra_generate_cfg['seed'] = kwargs['seed']
            
            output_stream = self._call_llm(
                messages=messages,
                functions=[func.function for func in self.function_map.values()] if self.function_map else None,
                extra_generate_cfg=extra_generate_cfg,
            )
            
            output: List[Message] = []
            for output in output_stream:
                if output:
                    yield response + output
            
            if output:
                response.extend(output)
                messages.extend(output)
                
                used_any_tool = False
                for out in output:
                    use_tool, tool_name, tool_args, text = self._detect_tool(out)
                    if text:
                        final_content = text
                    
                    if use_tool:
                        tool_start = time.perf_counter()
                        tool_result = self._call_tool(tool_name, tool_args, messages=messages, **kwargs)
                        tool_latency_ms = (time.perf_counter() - tool_start) * 1000
                        fn_msg = Message(
                            role=FUNCTION,
                            name=tool_name,
                            content=tool_result,
                        )
                        self._emit_observer(
                            event="tool_called",
                            payload={
                                "session_id": session_state.session_id,
                                "user_id": session_state.user_id,
                                "turn_pair_id": turn_pair_id,
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "tool_result": str(tool_result)[:1000],
                                "latency_ms": tool_latency_ms,
                            },
                        )
                        messages.append(fn_msg)
                        response.append(fn_msg)
                        yield response
                        used_any_tool = True
                
                if not used_any_tool:
                    break
        
        # 6. 生成阶段风险表达补足（在合规审校前）
        if final_content:
            enriched_content = self._ensure_risk_expression_block(
                content=final_content,
                query=current_query,
                turn_pair_id=turn_pair_id,
            )
            if enriched_content != final_content:
                final_content = enriched_content
                if response:
                    response[-1] = Message(
                        role=ASSISTANT,
                        content=final_content,
                        name=self.name,
                    )
                    yield response

        # 7. 合规审校
        if final_content:
            profile = self.memory_manager.get_profile(session_state.user_id)
            
            compliance_result = self.compliance_guard.check(
                content=final_content,
                user_profile=profile,
            )
            
            if compliance_result.needs_modification:
                # 修改最后一条消息
                modified_content = compliance_result.modified_content
                if response:
                    response[-1] = Message(
                        role=ASSISTANT,
                        content=modified_content,
                        name=self.name,
                    )
                final_content = modified_content
                yield response
            self._emit_observer(
                event="compliance_done",
                payload={
                    "session_id": session_state.session_id,
                    "user_id": session_state.user_id,
                    "turn_pair_id": turn_pair_id,
                    "needs_modification": compliance_result.needs_modification,
                    "is_compliant": compliance_result.is_compliant,
                    "violations": compliance_result.violations,
                    "risk_disclaimer_added": compliance_result.risk_disclaimer_added,
                    "suitability_warning": compliance_result.suitability_warning,
                },
            )
        
        # 8. 更新记忆
        if current_query and final_content:
            try:
                # 更新会话历史
                session_state.add_turn("user", current_query)
                session_state.add_turn("assistant", final_content)
                
                # 写入长期记忆
                self.memory_manager.process_turn(
                    session_state=session_state,
                    user_message=current_query,
                    assistant_message=final_content,
                )
                profile_snapshot = self.memory_manager.get_profile(session_state.user_id).to_dict()
                self._emit_observer(
                    event="profile_snapshot",
                    payload={
                        "session_id": session_state.session_id,
                        "user_id": session_state.user_id,
                        "turn_pair_id": turn_pair_id,
                        "profile": profile_snapshot,
                    },
                )
            except Exception as e:
                logger.warning(f"Memory update failed: {e}")
        
        turn_latency_ms = (time.perf_counter() - turn_start_ts) * 1000
        self._emit_observer(
            event="turn_end",
            payload={
                "session_id": session_state.session_id,
                "user_id": session_state.user_id,
                "turn_pair_id": turn_pair_id,
                "query": current_query,
                "final_content": final_content,
                "latency_ms": turn_latency_ms,
            },
        )
        
        yield response
    
    def _get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> SessionState:
        """获取或创建会话状态"""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        
        # 创建新会话
        session = self.memory_manager.create_session(
            user_id=user_id or "default_user",
        )
        
        if session_id:
            session.session_id = session_id
        
        self._sessions[session.session_id] = session
        return session
    
    def _extract_current_query(self, messages: List[Message]) -> str:
        """提取当前用户查询"""
        for msg in reversed(messages):
            if msg.role == USER:
                content = msg.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # 多模态消息，提取文本部分
                    texts = [item.text for item in content if hasattr(item, 'text') and item.text]
                    return " ".join(texts)
        return ""
    
    def _inject_memory_context(
        self,
        messages: List[Message],
        memory_context: str,
    ) -> List[Message]:
        """将记忆上下文注入到消息中"""
        if not memory_context:
            return messages
        
        # 构建记忆上下文块
        memory_block = f"\n\n---\n## 相关历史记忆与用户画像\n{memory_context}\n---\n\n"
        
        # 找到系统消息并追加
        for i, msg in enumerate(messages):
            if msg.role == SYSTEM:
                if isinstance(msg.content, str):
                    messages[i] = Message(
                        role=SYSTEM,
                        content=msg.content + memory_block,
                    )
                break
        else:
            # 没有系统消息，在开头添加
            messages.insert(0, Message(
                role=SYSTEM,
                content=memory_block,
            ))
        
        return messages

    def _contains_any(self, text: str, keywords: Any) -> bool:
        if not text:
            return False
        return any(keyword in text for keyword in keywords)

    def _choose_variant(self, variants: List[str], turn_pair_id: int, salt: int = 0) -> str:
        if not variants:
            return ""
        idx = abs(int(turn_pair_id) + salt) % len(variants)
        return variants[idx]

    def _is_fact_style_query(self, query: str) -> bool:
        q = (query or "").lower()
        if not q:
            return False
        has_fact_hint = self._contains_any(q, RISK_FACT_QUERY_HINTS)
        has_intent_hint = self._contains_any(q, RISK_INTENT_HINTS)
        return has_fact_hint and not has_intent_hint

    def _should_use_full_risk_block(self, query: str, content: str) -> bool:
        if self._is_fact_style_query(query):
            return False
        combined = f"{query}\n{content}".lower()
        if self._contains_any(combined, RISK_FULL_TRIGGER_KEYWORDS):
            return True
        return True

    def _missing_risk_categories(self, content: str) -> List[str]:
        missing: List[str] = []
        for category, keywords in RISK_CATEGORY_KEYWORDS.items():
            if not self._contains_any(content, keywords):
                missing.append(category)
        return missing

    def _build_risk_block(
        self,
        missing_categories: List[str],
        turn_pair_id: int,
        full_mode: bool,
    ) -> str:
        if not missing_categories:
            return ""

        if not full_mode and len(missing_categories) == 3:
            minimal = self._choose_variant(RISK_MINIMAL_BLOCK_VARIANTS, turn_pair_id)
            return f"\n\n补充说明：{minimal}"

        segments: List[str] = []
        for idx, category in enumerate(missing_categories):
            variant = self._choose_variant(RISK_PHRASE_VARIANTS.get(category, []), turn_pair_id, idx)
            if variant:
                segments.append(variant.rstrip("。；; "))
        if not segments:
            return ""

        prefix = "补充风险说明：" if full_mode else "补充说明："
        return "\n\n" + prefix + "；".join(segments) + "。"

    def _ensure_risk_expression_block(
        self,
        content: str,
        query: str,
        turn_pair_id: int,
    ) -> str:
        if not content:
            return content
        missing_categories = self._missing_risk_categories(content)
        if not missing_categories:
            return content

        full_mode = self._should_use_full_risk_block(query, content)
        risk_block = self._build_risk_block(
            missing_categories=missing_categories,
            turn_pair_id=turn_pair_id,
            full_mode=full_mode,
        )
        if not risk_block:
            return content
        return content.rstrip() + risk_block
    
    def handle_turn(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        处理单轮对话的便捷方法
        
        Args:
            user_message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            助手回复
        """
        messages = [Message(role=USER, content=user_message)]
        
        response = ""
        for output in self.run(
            messages=messages,
            session_id=session_id,
            user_id=user_id,
        ):
            if output:
                last_msg = output[-1]
                if hasattr(last_msg, 'content') and last_msg.content:
                    response = last_msg.content
                elif isinstance(last_msg, dict) and last_msg.get('content'):
                    response = last_msg['content']
        
        return response
    
    def get_session_state(self, session_id: str) -> Optional[SessionState]:
        """获取会话状态"""
        return self._sessions.get(session_id)
    
    def get_user_profile(self, user_id: str) -> UserProfile:
        """获取用户画像"""
        return self.memory_manager.get_profile(user_id)
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> UserProfile:
        """更新用户画像"""
        return self.memory_manager.update_profile(user_id, updates)

    def _emit_observer(self, event: str, payload: Dict[str, Any]) -> None:
        """触发观测器事件（失败不影响主流程）"""
        if self.observer is None:
            return
        try:
            if hasattr(self.observer, "on_event"):
                self.observer.on_event(event, payload)
            elif callable(self.observer):
                self.observer(event, payload)
        except Exception as e:
            logger.debug(f"Observer emit failed: {e}")
