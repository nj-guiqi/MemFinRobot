"""记忆管理器：统一管理记忆读写、召回与画像更新。"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from memfinrobot.memory.schemas import (
    InvestmentGoal,
    InvestmentHorizon,
    LiquidityNeed,
    MemoryItem,
    RecallResult,
    RefinedMemory,
    RiskLevel,
    SessionState,
    UserProfile,
    WindowSelectionResult,
)
from memfinrobot.memory.window_selector import WindowSelector
from memfinrobot.memory.window_refiner import WindowRefiner
from memfinrobot.memory.memory_writer import MemoryWriter
from memfinrobot.memory.recall import MemoryRecall, ContextPacker
from memfinrobot.memory.rerank import MemoryReranker, deduplicate_memories
from memfinrobot.memory.embedding import EmbeddingModel, get_embedding_model
from memfinrobot.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

PROFILE_PATCH_PROMPT = """你是用户画像信息抽取器。请根据最新用户发言、近期对话和当前画像，提取可更新的画像补丁。
输出要求：
1) 只输出 JSON，不要输出任何解释。
2) JSON 必须包含以下所有字段，字段名不可缺失：
{{
  "risk_level": {{"value": "low|medium|high|null", "confidence": 0.0, "evidence": ""}},
  "investment_horizon": {{"value": "short|medium|long|null", "confidence": 0.0, "evidence": ""}},
  "liquidity_need": {{"value": "low|medium|high|null", "confidence": 0.0, "evidence": ""}},
  "investment_goal": {{"value": "stable_growth|cash_flow|theme_investment|learning|null", "confidence": 0.0, "evidence": ""}},
  "max_acceptable_loss": {{"value": null, "confidence": 0.0, "evidence": ""}},
  "preferred_topics_add": [{{"value": "", "confidence": 0.0, "evidence": ""}}],
  "forbidden_assets_add": [{{"value": "", "confidence": 0.0, "evidence": ""}}]
}}

抽取原则：
- 只在用户表达明确时更新，避免过度猜测。
- 信息不确定时，value 设为 null，confidence 保持较低。
- max_acceptable_loss 输出 0~1 的小数（例如 10% 输出 0.1）。
- 优先覆盖评测关注字段：风险等级、投资期限、流动性需求、投资目标、约束、偏好、最大可接受亏损。

当前画像：
{current_profile}

近期对话：
{recent_history}

最新用户发言：
{user_message}
"""


class MemoryManager:
    """统一管理记忆写入、召回和用户画像更新。"""
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[Any] = None,
        embedding_model: Optional[EmbeddingModel] = None,
    ):
        """初始化记忆相关组件，并接入可选 LLM 客户端。"""
        self.settings = settings or get_settings()
        self.llm_client = llm_client
        if embedding_model:
            self.embedding_model = embedding_model
        else:
            self.embedding_model = get_embedding_model(
                model_path=self.settings.embedding.model_path,
                device=self.settings.embedding.device,
            )
        self.window_selector = WindowSelector(
            llm_client=llm_client,
            max_window_size=self.settings.memory.max_window_size,
            vote_times=self.settings.memory.vote_times,
            confidence_threshold=self.settings.memory.confidence_threshold,
        )
        
        self.window_refiner = WindowRefiner(
            llm_client=llm_client,
        )
        
        self.memory_writer = MemoryWriter(
            storage_path=self.settings.memory.storage_path,
            embedding_model=self.embedding_model,
            storage_backend=self.settings.memory.storage_backend,
        )
        
        self.memory_recall = MemoryRecall(
            embedding_model=self.embedding_model,
            top_k=self.settings.memory.top_k_recall,
        )
        
        self.memory_reranker = MemoryReranker(
            reranker_model_path=self.settings.reranker.model_path,
            device=self.settings.reranker.device,
            threshold=self.settings.reranker.threshold,
        )
        
        self.context_packer = ContextPacker(
            max_tokens=self.settings.memory.max_ref_token,
        )
        self._profiles: Dict[str, UserProfile] = {}
    
    def process_turn(
        self,
        session_state: SessionState,
        user_message: str,
        assistant_message: str,
    ) -> List[str]:
        """处理一轮对话：写入长期记忆，并尝试更新画像。"""
        dialogue_history = [
            turn["content"] for turn in session_state.dialogue_history
            if turn["role"] in ["user", "assistant"]
        ]
        current_content = f"user: {user_message}\nassistant: {assistant_message}"
        selection_result = self.window_selector.select(
            dialogue_history=dialogue_history,
            current_query=user_message,
        )
        selected_texts = [
            dialogue_history[idx]
            for idx in selection_result.selected_indices
            if 0 <= idx < len(dialogue_history)
        ]
        refined_memory = self.window_refiner.refine(
            selected_texts=selected_texts,
            current_query=user_message,
            source_indices=selection_result.selected_indices,
        )
        hierarchical_content = self.window_refiner.build_hierarchical_content(
            refined_memory=refined_memory,
            current_content=current_content,
        )
        entities = self._extract_entities(current_content)
        topics = self._extract_topics(current_content)
        memory_ids = self.memory_writer.write(
            refined_memory=refined_memory,
            current_content=current_content,
            hierarchical_content=hierarchical_content,
            session_id=session_state.session_id,
            user_id=session_state.user_id,
            turn_index=session_state.turn_count,
            topics=topics,
            entities=entities,
        )
        session_state.memory_ids.extend(memory_ids)
        try:
            updates = self._infer_profile_patch_with_llm(
                session_state=session_state,
                user_message=user_message,
            )
            if updates:
                self.update_profile(session_state.user_id, updates)
                logger.info(f"Updated profile for user={session_state.user_id}: {list(updates.keys())}")
        except Exception as e:
            logger.warning(f"Profile patch update failed: {e}")
        
        logger.info(
            f"Processed turn {session_state.turn_count}, "
            f"selected {len(selection_result.selected_indices)} windows, "
            f"confidence: {selection_result.confidence:.2f}"
        )
        
        return memory_ids
    
    def recall_for_query(
        self,
        query: str,
        session_state: SessionState,
        include_short_term: bool = True,
    ) -> RecallResult:
        """针对查询召回记忆，并打包最终上下文。"""
        memory_items = self.memory_writer.get_all_memories(
            user_id=session_state.user_id
        )
        profile = self.get_profile(session_state.user_id)
        recall_result = self.memory_recall.recall(
            query=query,
            memory_items=memory_items,
            embeddings=self.memory_writer._embeddings,
            user_profile=profile,
            session_id=session_state.session_id,
        )
        recall_result = self.memory_reranker.rerank(
            query=query,
            recall_result=recall_result,
        )
        items, scores = deduplicate_memories(
            recall_result.items,
            recall_result.scores,
        )
        recall_result.items = items
        recall_result.scores = scores
        recall_result.sources = recall_result.sources[:len(items)]
        short_term_context = None
        if include_short_term:
            recent_history = session_state.get_recent_history(n=6)
            if recent_history:
                short_term_context = "\n".join([
                    f"{turn['role']}: {turn['content']}"
                    for turn in recent_history
                ])
        packed_result = self.context_packer.pack(
            recall_result=recall_result,
            profile=profile,
            short_term_context=short_term_context,
        )
        
        return packed_result
    
    def get_profile(self, user_id: str) -> UserProfile:
        """获取用户画像（不存在时自动创建默认画像）。"""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]
    
    def update_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
    ) -> UserProfile:
        """将更新字段合并到用户画像。"""
        profile = self.get_profile(user_id)
        
        for key, value in updates.items():
            if key == "risk_level":
                risk_level = self._normalize_risk_level(value)
                if risk_level is not None:
                    profile.risk_level = risk_level
            elif key == "investment_horizon":
                horizon = self._normalize_investment_horizon(value)
                if horizon is not None:
                    profile.investment_horizon = horizon
            elif key == "liquidity_need":
                liquidity = self._normalize_liquidity_need(value)
                if liquidity is not None:
                    profile.liquidity_need = liquidity
            elif key == "investment_goal":
                goal = self._normalize_investment_goal(value)
                if goal is not None:
                    profile.investment_goal = goal
            elif key == "risk_level_confidence":
                try:
                    profile.risk_level_confidence = float(value)
                except Exception:
                    pass
            elif key == "investment_horizon_confidence":
                try:
                    profile.investment_horizon_confidence = float(value)
                except Exception:
                    pass
            elif key == "liquidity_need_confidence":
                try:
                    profile.liquidity_need_confidence = float(value)
                except Exception:
                    pass
            elif key == "risk_level_evidence_add":
                evidence = str(value).strip()
                if evidence and evidence not in profile.risk_level_evidence:
                    profile.risk_level_evidence.append(evidence)
                    profile.risk_level_evidence = profile.risk_level_evidence[-20:]
            elif key == "preferred_topics":
                merged = profile.preferred_topics + [str(v).strip() for v in (value or []) if str(v).strip()]
                profile.preferred_topics = list(dict.fromkeys(merged))
            elif key == "forbidden_assets":
                merged = profile.forbidden_assets + [str(v).strip() for v in (value or []) if str(v).strip()]
                profile.forbidden_assets = list(dict.fromkeys(merged))
            elif key == "max_acceptable_loss":
                parsed = self._parse_max_acceptable_loss(value)
                if parsed is not None:
                    profile.max_acceptable_loss = parsed
            elif hasattr(profile, key):
                setattr(profile, key, value)
        
        from datetime import datetime
        profile.updated_at = datetime.now()
        
        return profile

    def _infer_profile_patch_with_llm(
        self,
        session_state: SessionState,
        user_message: str,
    ) -> Dict[str, Any]:
        """调用 LLM 抽取结构化画像补丁。"""
        if self.llm_client is None:
            return {}
        if not user_message or not user_message.strip():
            return {}
        
        profile = self.get_profile(session_state.user_id)
        recent_history = session_state.get_recent_history(n=3)
        recent_lines = "\n".join(
            f"{turn.get('role', '')}: {turn.get('content', '')}" for turn in recent_history
        )
        prompt = PROFILE_PATCH_PROMPT.format(
            current_profile=json.dumps(profile.to_dict(), ensure_ascii=False),
            recent_history=recent_lines,
            user_message=user_message.strip(),
        )
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(
            messages=messages,
            stream=True,
            extra_generate_cfg={"temperature": 0.1},
        )
        text = self._extract_llm_response_text(response)
        patch = self._parse_json_object(text)
        if not patch:
            return {}
        
        return self._build_profile_updates_from_patch(patch)

    def _extract_llm_response_text(self, response: Any) -> str:
        """从 llm_client.chat 返回值中提取文本内容。"""
        if isinstance(response, str):
            return response
        if isinstance(response, list):
            for r in reversed(response):
                if hasattr(r, "content") and r.content:
                    return str(r.content)
                if isinstance(r, dict) and r.get("content"):
                    return str(r["content"])
            return str(response)
        if hasattr(response, "__iter__"):
            last_text = ""
            for r in response:
                if r:
                    last = r[-1] if isinstance(r, list) else r
                    if hasattr(last, "content") and last.content:
                        last_text = str(last.content)
                    elif isinstance(last, dict) and last.get("content"):
                        last_text = str(last["content"])
                    else:
                        last_text = str(last)
            return last_text
        return str(response)

    def _parse_json_object(self, raw_text: str) -> Dict[str, Any]:
        """从模型输出中尽可能解析 JSON 对象。"""
        text = (raw_text or "").strip()
        if not text:
            return {}

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start:end + 1]
            try:
                obj = json.loads(candidate)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}

        return {}

    def _build_profile_updates_from_patch(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """将 LLM patch 转换为可写入画像的更新字段。"""
        updates: Dict[str, Any] = {}
        
        self._apply_scalar_patch(
            patch=patch,
            key="risk_level",
            updates=updates,
            confidence_threshold=0.8,
            normalize_fn=self._normalize_risk_level_value,
            confidence_key="risk_level_confidence",
            evidence_key="risk_level_evidence_add",
        )
        self._apply_scalar_patch(
            patch=patch,
            key="investment_horizon",
            updates=updates,
            confidence_threshold=0.8,
            normalize_fn=self._normalize_investment_horizon_value,
            confidence_key="investment_horizon_confidence",
        )
        self._apply_scalar_patch(
            patch=patch,
            key="liquidity_need",
            updates=updates,
            confidence_threshold=0.8,
            normalize_fn=self._normalize_liquidity_need_value,
            confidence_key="liquidity_need_confidence",
        )
        self._apply_scalar_patch(
            patch=patch,
            key="investment_goal",
            updates=updates,
            confidence_threshold=0.8,
            normalize_fn=self._normalize_investment_goal_value,
        )
        
        max_loss_patch = patch.get("max_acceptable_loss") or {}
        if isinstance(max_loss_patch, dict):
            try:
                conf = float(max_loss_patch.get("confidence") or 0.0)
            except Exception:
                conf = 0.0
            if conf >= 0.8:
                parsed = self._parse_max_acceptable_loss(max_loss_patch.get("value"))
                if parsed is not None:
                    updates["max_acceptable_loss"] = parsed
        
        updates["preferred_topics"] = self._extract_list_patch_values(
            patch.get("preferred_topics_add"),
            confidence_threshold=0.7,
        )
        updates["forbidden_assets"] = self._extract_list_patch_values(
            patch.get("forbidden_assets_add"),
            confidence_threshold=0.7,
        )
        if not updates.get("preferred_topics"):
            updates.pop("preferred_topics", None)
        if not updates.get("forbidden_assets"):
            updates.pop("forbidden_assets", None)
        
        return updates

    def _apply_scalar_patch(
        self,
        patch: Dict[str, Any],
        key: str,
        updates: Dict[str, Any],
        confidence_threshold: float,
        normalize_fn: Any,
        confidence_key: Optional[str] = None,
        evidence_key: Optional[str] = None,
    ) -> None:
        value_patch = patch.get(key) or {}
        if not isinstance(value_patch, dict):
            return
        try:
            conf = float(value_patch.get("confidence") or 0.0)
        except Exception:
            conf = 0.0
        if conf < confidence_threshold:
            return
        normalized = normalize_fn(value_patch.get("value"))
        if normalized is None:
            return
        updates[key] = normalized
        if confidence_key:
            updates[confidence_key] = conf
        if evidence_key:
            evidence = str(value_patch.get("evidence") or "").strip()
            if evidence:
                updates[evidence_key] = evidence

    def _extract_list_patch_values(
        self,
        raw_items: Any,
        confidence_threshold: float = 0.7,
    ) -> List[str]:
        values: List[str] = []
        if not isinstance(raw_items, list):
            return values
        for item in raw_items:
            if isinstance(item, dict):
                try:
                    conf = float(item.get("confidence") or 0.0)
                except Exception:
                    conf = 0.0
                if conf < confidence_threshold:
                    continue
                value = str(item.get("value") or "").strip()
            else:
                conf = 1.0
                value = str(item).strip()
            if value:
                values.append(value)
        return list(dict.fromkeys(values))

    def _normalize_risk_level_value(self, value: Any) -> Optional[str]:
        if isinstance(value, RiskLevel):
            return value.value
        v = str(value or "").strip().lower()
        mapping = {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "保守": "low",
            "稳健": "medium",
            "进取": "high",
        }
        return mapping.get(v)
    def _normalize_investment_horizon_value(self, value: Any) -> Optional[str]:
        if isinstance(value, InvestmentHorizon):
            return value.value
        v = str(value or "").strip().lower()
        mapping = {
            "short": "short",
            "medium": "medium",
            "long": "long",
            "<=6月": "short",
            "6-24月": "medium",
            "2年以上": "long",
            "短期": "short",
            "中期": "medium",
            "长期": "long",
        }
        return mapping.get(v)
    def _normalize_liquidity_need_value(self, value: Any) -> Optional[str]:
        if isinstance(value, LiquidityNeed):
            return value.value
        v = str(value or "").strip().lower()
        mapping = {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "低": "low",
            "中": "medium",
            "高": "high",
        }
        return mapping.get(v)
    def _normalize_investment_goal_value(self, value: Any) -> Optional[str]:
        if isinstance(value, InvestmentGoal):
            return value.value
        v = str(value or "").strip().lower()
        mapping = {
            "stable_growth": "stable_growth",
            "cash_flow": "cash_flow",
            "theme_investment": "theme_investment",
            "learning": "learning",
        }
        return mapping.get(v)

    def _normalize_risk_level(self, value: Any) -> Optional[RiskLevel]:
        normalized = self._normalize_risk_level_value(value)
        return RiskLevel(normalized) if normalized else None

    def _normalize_investment_horizon(self, value: Any) -> Optional[InvestmentHorizon]:
        normalized = self._normalize_investment_horizon_value(value)
        return InvestmentHorizon(normalized) if normalized else None

    def _normalize_liquidity_need(self, value: Any) -> Optional[LiquidityNeed]:
        normalized = self._normalize_liquidity_need_value(value)
        return LiquidityNeed(normalized) if normalized else None

    def _normalize_investment_goal(self, value: Any) -> Optional[InvestmentGoal]:
        normalized = self._normalize_investment_goal_value(value)
        return InvestmentGoal(normalized) if normalized else None

    def _parse_max_acceptable_loss(self, value: Any) -> Optional[float]:
        """将最大可接受亏损解析为 [0,1] 小数。"""
        try:
            if value is None:
                return None
            if isinstance(value, str):
                m = re.search(r"(\d+(?:\.\d+)?)", value)
                if not m:
                    return None
                value = float(m.group(1))
                if "%" in m.string:
                    value = value / 100.0
            value = float(value)
            if value > 1.0 and value <= 100.0:
                value = value / 100.0
            if 0.0 <= value <= 1.0:
                return value
        except Exception:
            return None
        return None
    
    def _extract_entities(self, content: str) -> List[str]:
        """提取粗粒度实体（如 6 位代码）。"""
        import re

        entities = []
        stock_codes = re.findall(r"\b\d{6}\b", content)
        entities.extend(stock_codes)
        fund_codes = re.findall(r"\b\d{6}\b", content)
        entities.extend([f"F{code}" for code in fund_codes if code not in stock_codes])

        return list(set(entities))

    def _extract_topics(self, content: str) -> List[str]:
        """通过关键词匹配提取粗粒度金融主题。"""
        topics = []

        topic_keywords = {
            "股票": ["stock", "a-share", "股票", "个股", "股价"],
            "基金": ["fund", "etf", "基金", "指数基金", "货基"],
            "债券": ["bond", "债券", "国债", "转债", "利率"],
            "行情": ["market", "行情", "涨跌", "走势", "k线"],
            "风险": ["risk", "风险", "亏损", "回撤", "波动"],
            "配置": ["allocation", "配置", "仓位", "分散", "组合"],
        }

        content_lower = content.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in content_lower for kw in keywords):
                topics.append(topic)

        return topics

    def create_session(self, user_id: str) -> SessionState:
        """为用户创建新的会话状态。"""
        return SessionState(user_id=user_id)
    
    def clear_session_memories(self, session_id: str) -> int:
        """删除某个会话的全部记忆。"""
        memories = self.memory_writer.get_session_memories(session_id)
        count = 0
        for memory in memories:
            if self.memory_writer.delete_memory(memory.id):
                count += 1
        return count
