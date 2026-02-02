"""合规审校器 - 确保输出符合监管要求"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from memfinrobot.memory.schemas import UserProfile, RiskLevel
from memfinrobot.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    """合规检查结果"""
    is_compliant: bool = True
    needs_modification: bool = False
    original_content: str = ""
    modified_content: str = ""
    violations: List[Dict[str, Any]] = field(default_factory=list)
    risk_disclaimer_added: bool = False
    suitability_warning: Optional[str] = None


class ComplianceGuard:
    """
    合规审校器
    
    职责：
    1. 适当性检查：用户风险等级 vs 建议内容风险等级
    2. 禁语/高风险表达过滤
    3. 强制添加风险提示
    """
    
    # 禁语列表及其处理方式
    FORBIDDEN_PATTERNS = [
        # (正则模式, 违规类型, 替换建议)
        (r"保证.*?收益", "promise_return", "投资收益不确定，无法保证"),
        (r"稳赚|必涨|必赚", "guarantee", "投资存在风险，不能保证盈利"),
        (r"内幕|小道消息", "insider", "请以公开信息为依据"),
        (r"荐股|推荐.*?(买入|卖出)", "recommendation", "以上仅供参考，不构成投资建议"),
        (r"(买入|卖出|建仓|加仓|减仓|清仓).*?(点位|价格)", "trading_advice", "具体交易决策请您自行判断"),
        (r"一定(会|能|涨|跌)", "certainty", "市场存在不确定性"),
        (r"绝对(安全|没问题)", "absolute", "任何投资都存在风险"),
    ]
    
    # 风险提示模板
    DEFAULT_RISK_DISCLAIMER = (
        "\n\n【风险提示】以上内容仅供参考，不构成投资建议。"
        "投资有风险，入市需谨慎。请根据自身风险承受能力谨慎决策。"
    )
    
    # 适当性提示模板
    SUITABILITY_TEMPLATES = {
        "high_risk_to_low_user": (
            "\n\n⚠️ 温馨提示：您当前的风险承受能力评估为较低水平，"
            "而上述提及的产品/策略风险等级较高。建议您充分了解相关风险后再做决定，"
            "或考虑风险等级更匹配的投资方式。"
        ),
        "incomplete_profile": (
            "\n\n💡 为了提供更适合您的建议，您是否方便告诉我：\n"
            "1. 您的投资经验如何？\n"
            "2. 您能接受的最大亏损是多少？\n"
            "3. 您的投资期限大概是多久？"
        ),
    }
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        forbidden_phrases: Optional[List[str]] = None,
    ):
        """
        初始化合规审校器
        
        Args:
            settings: 配置对象
            forbidden_phrases: 额外的禁语列表
        """
        self.settings = settings or get_settings()
        
        # 合并禁语列表
        self.forbidden_phrases = list(self.settings.compliance.forbidden_phrases)
        if forbidden_phrases:
            self.forbidden_phrases.extend(forbidden_phrases)
        
        # 编译正则表达式
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), vtype, replacement)
            for pattern, vtype, replacement in self.FORBIDDEN_PATTERNS
        ]
    
    def check(
        self,
        content: str,
        user_profile: Optional[UserProfile] = None,
        content_risk_level: Optional[str] = None,
        force_disclaimer: bool = True,
    ) -> ComplianceResult:
        """
        执行合规检查
        
        Args:
            content: 要检查的内容
            user_profile: 用户画像
            content_risk_level: 内容涉及的风险等级
            force_disclaimer: 是否强制添加风险提示
            
        Returns:
            ComplianceResult 包含检查结果和修改建议
        """
        result = ComplianceResult(
            original_content=content,
            modified_content=content,
        )
        
        # 1. 检查禁语
        self._check_forbidden_phrases(result)
        
        # 2. 检查禁语模式
        self._check_forbidden_patterns(result)
        
        # 3. 适当性检查
        if user_profile:
            self._check_suitability(result, user_profile, content_risk_level)
        
        # 4. 检查/添加风险提示
        if force_disclaimer:
            self._ensure_risk_disclaimer(result)
        
        # 更新合规状态
        result.is_compliant = len(result.violations) == 0
        result.needs_modification = (
            result.modified_content != result.original_content
        )
        
        return result
    
    def _check_forbidden_phrases(self, result: ComplianceResult) -> None:
        """检查简单禁语"""
        content = result.modified_content
        
        for phrase in self.forbidden_phrases:
            if phrase in content:
                result.violations.append({
                    "type": "forbidden_phrase",
                    "phrase": phrase,
                    "severity": "high",
                })
                # 替换禁语
                content = content.replace(phrase, f"[{phrase}（已删除）]")
        
        result.modified_content = content
    
    def _check_forbidden_patterns(self, result: ComplianceResult) -> None:
        """检查禁语模式"""
        content = result.modified_content
        
        for pattern, vtype, replacement in self.compiled_patterns:
            matches = pattern.findall(content)
            if matches:
                for match in matches:
                    result.violations.append({
                        "type": vtype,
                        "match": match if isinstance(match, str) else match[0],
                        "severity": "medium",
                    })
                # 添加修正说明
                content = pattern.sub(f"（{replacement}）", content)
        
        result.modified_content = content
    
    def _check_suitability(
        self,
        result: ComplianceResult,
        user_profile: UserProfile,
        content_risk_level: Optional[str] = None,
    ) -> None:
        """适当性检查"""
        # 检测内容风险等级（简化版本）
        if content_risk_level is None:
            content_risk_level = self._detect_content_risk_level(result.modified_content)
        
        # 用户风险等级
        user_risk = user_profile.risk_level
        
        # 适当性匹配检查
        if content_risk_level == "high" and user_risk == RiskLevel.LOW:
            result.suitability_warning = self.SUITABILITY_TEMPLATES["high_risk_to_low_user"]
            result.violations.append({
                "type": "suitability_mismatch",
                "user_risk": user_risk.value,
                "content_risk": content_risk_level,
                "severity": "warning",
            })
        
        # 画像不完整提示
        if user_risk == RiskLevel.UNKNOWN:
            # 检查是否已有询问画像的内容
            if "风险承受" not in result.modified_content and "投资经验" not in result.modified_content:
                result.suitability_warning = self.SUITABILITY_TEMPLATES["incomplete_profile"]
    
    def _detect_content_risk_level(self, content: str) -> str:
        """检测内容涉及的风险等级（简化版本）"""
        high_risk_keywords = ["股票", "期货", "期权", "杠杆", "高波动", "高风险"]
        medium_risk_keywords = ["混合型", "偏股", "指数基金", "ETF"]
        low_risk_keywords = ["货币基金", "债券", "银行理财", "存款", "低风险"]
        
        content_lower = content.lower()
        
        high_count = sum(1 for kw in high_risk_keywords if kw in content_lower)
        medium_count = sum(1 for kw in medium_risk_keywords if kw in content_lower)
        low_count = sum(1 for kw in low_risk_keywords if kw in content_lower)
        
        if high_count > 0 and high_count >= medium_count:
            return "high"
        elif medium_count > 0:
            return "medium"
        elif low_count > 0:
            return "low"
        else:
            return "unknown"
    
    def _ensure_risk_disclaimer(self, result: ComplianceResult) -> None:
        """确保包含风险提示"""
        content = result.modified_content
        
        # 检查是否已有风险提示
        disclaimer_keywords = ["风险提示", "投资有风险", "入市需谨慎"]
        has_disclaimer = any(kw in content for kw in disclaimer_keywords)
        
        if not has_disclaimer:
            # 添加风险提示
            content = content.rstrip() + self.settings.compliance.risk_disclaimer
            result.risk_disclaimer_added = True
        
        # 添加适当性警告（如果有）
        if result.suitability_warning:
            content = content.rstrip() + result.suitability_warning
        
        result.modified_content = content
    
    def filter_response(
        self,
        content: str,
        user_profile: Optional[UserProfile] = None,
    ) -> str:
        """
        过滤响应内容的便捷方法
        
        Args:
            content: 原始内容
            user_profile: 用户画像
            
        Returns:
            过滤后的内容
        """
        result = self.check(content, user_profile)
        return result.modified_content
