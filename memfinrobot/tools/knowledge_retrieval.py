"""知识库检索工具"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult


@register_tool("knowledge_retrieval")
class KnowledgeRetrievalTool(MemFinBaseTool):
    """
    知识库检索工具
    
    检索金融领域知识，包括：
    - 监管规则
    - 产品规则
    - 投教材料
    - 研报摘要
    
    V0版本使用预置知识
    """
    
    name: str = "knowledge_retrieval"
    description: str = "检索金融领域知识库，获取监管规则、产品规则、投资教育材料等信息"
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索查询"
            },
            "category": {
                "type": "string",
                "enum": ["regulation", "product_rule", "education", "research"],
                "description": "知识类别：regulation（监管规则）、product_rule（产品规则）、education（投教）、research（研报）"
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认3"
            }
        },
        "required": ["query"]
    }
    
    # 预置知识库（简化版）
    _knowledge_base = [
        {
            "category": "regulation",
            "title": "证券投资基金销售适当性要求",
            "content": "基金销售机构应当根据投资者的风险承受能力，推荐与其风险承受能力相匹配的基金产品。"
                       "高风险产品不应向低风险承受能力的投资者推荐。",
            "source": "证监会《证券投资基金销售管理办法》",
        },
        {
            "category": "regulation",
            "title": "投资者适当性管理办法",
            "content": "经营机构向投资者销售产品或者提供服务时，应当了解投资者的相关信息，"
                       "评估其风险承受能力，并根据评估结果推介适当的产品或服务。",
            "source": "证监会《证券期货投资者适当性管理办法》",
        },
        {
            "category": "education",
            "title": "基金投资入门",
            "content": "基金是一种间接投资方式，由专业基金经理管理。投资者通过购买基金份额，"
                       "间接持有基金所投资的证券组合。基金分为股票型、债券型、混合型、货币型等多种类型，"
                       "风险和收益特征各不相同。",
            "source": "投资者教育材料",
        },
        {
            "category": "education",
            "title": "风险与收益的关系",
            "content": "在金融投资中，风险与收益通常成正比。高收益往往伴随高风险，"
                       "投资者应根据自身风险承受能力选择合适的投资产品。不存在低风险高收益的投资机会，"
                       "警惕此类宣传以防上当受骗。",
            "source": "投资者教育材料",
        },
        {
            "category": "product_rule",
            "title": "ETF交易规则",
            "content": "ETF（交易型开放式指数基金）可在证券交易所像股票一样买卖。"
                       "交易时间为交易日9:30-11:30、13:00-15:00。ETF实行T+1交易，"
                       "当日买入需次日才能卖出。ETF无印花税，交易费用仅为券商佣金。",
            "source": "产品规则说明",
        },
        {
            "category": "product_rule",
            "title": "基金申购赎回规则",
            "content": "开放式基金的申购赎回按未知价原则，以申请当日收市后计算的基金份额净值为基准进行计算。"
                       "一般T日申请，T+1日确认份额，货币基金除外。赎回款项一般T+3至T+7日到账。",
            "source": "产品规则说明",
        },
    ]
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """检索知识库"""
        query = params.get("query", "")
        category = params.get("category")
        top_k = params.get("top_k", 3)
        
        # 简单的关键词匹配检索
        results = []
        query_lower = query.lower()
        
        for item in self._knowledge_base:
            # 类别过滤
            if category and item["category"] != category:
                continue
            
            # 关键词匹配
            content_lower = (item["title"] + item["content"]).lower()
            score = sum(1 for word in query_lower.split() if word in content_lower)
            
            if score > 0:
                results.append({
                    **item,
                    "relevance_score": score,
                })
        
        # 按相关度排序
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:top_k]
        
        # 移除内部分数
        for r in results:
            r.pop("relevance_score", None)
        
        if results:
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "total": len(results),
                },
                source="knowledge_base",
                asof=datetime.now(),
            )
        else:
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": [],
                    "total": 0,
                },
                source="knowledge_base",
                warnings=["未找到相关知识，请尝试更换关键词"],
            )
