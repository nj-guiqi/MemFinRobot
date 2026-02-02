"""风险提示模板工具"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult


@register_tool("risk_template")
class RiskTemplateTool(MemFinBaseTool):
    """
    风险提示模板工具
    
    根据产品类型、风险等级等生成标准化的风险提示语
    """
    
    name: str = "risk_template"
    description: str = "生成标准化的风险提示语，用于回复中的风险警示"
    parameters: dict = {
        "type": "object",
        "properties": {
            "product_type": {
                "type": "string",
                "enum": ["stock", "fund", "bond", "general"],
                "description": "产品类型"
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "风险等级"
            },
            "template_type": {
                "type": "string",
                "enum": ["short", "standard", "detailed"],
                "description": "模板类型：short（简短）、standard（标准）、detailed（详细）"
            }
        },
        "required": ["product_type"]
    }
    
    # 风险提示模板
    _templates = {
        "general": {
            "short": "【风险提示】投资有风险，入市需谨慎。",
            "standard": "【风险提示】以上内容仅供参考，不构成投资建议。投资有风险，入市需谨慎。请根据自身风险承受能力谨慎决策。",
            "detailed": "【风险提示】以上内容仅供参考，不构成任何投资建议或承诺。市场有风险，投资需谨慎。"
                        "您应充分了解投资风险，在充分了解并清楚知晓相关产品风险收益特征的基础上，"
                        "结合自身的投资目标、期限、投资经验、资产状况等因素独立判断，审慎做出投资决策。"
                        "如有需要，请咨询专业的投资顾问或持牌金融机构。",
        },
        "stock": {
            "short": "【风险提示】股票投资存在价格波动风险，可能导致本金损失。",
            "standard": "【风险提示】股票投资存在市场风险、流动性风险、政策风险等多重风险。"
                        "股票价格可能剧烈波动，投资者可能面临本金损失。请根据自身风险承受能力谨慎投资。",
            "detailed": "【风险提示】股票投资涉及以下主要风险：\n"
                        "1. 市场风险：股票价格受宏观经济、市场情绪等因素影响可能大幅波动\n"
                        "2. 个股风险：公司经营状况变化可能导致股价下跌\n"
                        "3. 流动性风险：部分股票交易不活跃，可能难以按预期价格买卖\n"
                        "4. 政策风险：监管政策变化可能影响股票价值\n"
                        "投资者应充分了解上述风险，审慎决策。",
        },
        "fund": {
            "short": "【风险提示】基金投资有风险，基金的过往业绩不代表未来表现。",
            "standard": "【风险提示】基金投资有风险，基金的过往业绩并不预示其未来表现。"
                        "基金管理人不保证基金一定盈利，也不保证最低收益。请投资者在投资前仔细阅读基金合同、招募说明书等法律文件。",
            "detailed": "【风险提示】基金投资涉及以下主要风险：\n"
                        "1. 市场风险：基金投资的证券市场价格波动会影响基金净值\n"
                        "2. 管理风险：基金经理的投资决策可能导致基金表现不佳\n"
                        "3. 流动性风险：市场流动性不足可能影响基金的变现能力\n"
                        "4. 申赎风险：大额申购赎回可能影响基金运作\n"
                        "基金的过往业绩并不预示其未来表现，请仔细阅读基金法律文件后审慎决策。",
        },
        "bond": {
            "short": "【风险提示】债券投资存在信用风险和利率风险。",
            "standard": "【风险提示】债券投资存在信用风险、利率风险、流动性风险等。"
                        "债券价格会随市场利率变化而波动，发行人信用状况变化可能导致违约风险。请审慎投资。",
            "detailed": "【风险提示】债券投资涉及以下主要风险：\n"
                        "1. 信用风险：发行人可能无法按时支付利息或偿还本金\n"
                        "2. 利率风险：市场利率上升会导致债券价格下跌\n"
                        "3. 流动性风险：部分债券交易不活跃，变现可能困难\n"
                        "4. 再投资风险：利息收入的再投资收益可能低于预期\n"
                        "请充分了解债券投资风险后审慎决策。",
        },
    }
    
    # 高风险额外提示
    _high_risk_addon = "\n\n⚠️ 特别提示：该产品风险等级较高，请确保您具备相应的风险承受能力。"
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """生成风险提示"""
        product_type = params.get("product_type", "general")
        risk_level = params.get("risk_level", "medium")
        template_type = params.get("template_type", "standard")
        
        # 获取模板
        templates = self._templates.get(product_type, self._templates["general"])
        template = templates.get(template_type, templates["standard"])
        
        # 高风险产品添加额外提示
        if risk_level == "high":
            template += self._high_risk_addon
        
        return ToolResult(
            success=True,
            data={
                "risk_disclaimer": template,
                "product_type": product_type,
                "risk_level": risk_level,
                "template_type": template_type,
            },
            source="risk_template",
            asof=datetime.now(),
        )
