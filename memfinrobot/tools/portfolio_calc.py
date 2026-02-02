"""组合计算工具"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import math

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult


@register_tool("portfolio_calc")
class PortfolioCalcTool(MemFinBaseTool):
    """
    组合与风险计算工具
    
    提供投资组合相关的计算功能：
    - 收益率计算
    - 波动率估算
    - 最大回撤
    - 夏普比率
    """
    
    name: str = "portfolio_calc"
    description: str = "计算投资组合的风险收益指标，包括收益率、波动率、最大回撤、夏普比率等"
    parameters: dict = {
        "type": "object",
        "properties": {
            "calc_type": {
                "type": "string",
                "enum": ["return", "volatility", "max_drawdown", "sharpe"],
                "description": "计算类型：return（收益率）、volatility（波动率）、max_drawdown（最大回撤）、sharpe（夏普比率）"
            },
            "values": {
                "type": "array",
                "items": {"type": "number"},
                "description": "数值序列（如净值序列或收益率序列）"
            },
            "initial_value": {
                "type": "number",
                "description": "初始值（用于收益率计算）"
            },
            "final_value": {
                "type": "number",
                "description": "最终值（用于收益率计算）"
            },
            "risk_free_rate": {
                "type": "number",
                "description": "无风险利率（年化，用于夏普比率计算），默认0.02"
            }
        },
        "required": ["calc_type"]
    }
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """执行计算"""
        calc_type = params.get("calc_type")
        values = params.get("values", [])
        initial_value = params.get("initial_value")
        final_value = params.get("final_value")
        risk_free_rate = params.get("risk_free_rate", 0.02)
        
        try:
            if calc_type == "return":
                result = self._calc_return(initial_value, final_value)
            elif calc_type == "volatility":
                result = self._calc_volatility(values)
            elif calc_type == "max_drawdown":
                result = self._calc_max_drawdown(values)
            elif calc_type == "sharpe":
                result = self._calc_sharpe(values, risk_free_rate)
            else:
                return ToolResult(
                    success=False,
                    errors=[f"未知的计算类型: {calc_type}"],
                )
            
            return ToolResult(
                success=True,
                data=result,
                source="portfolio_calc",
                asof=datetime.now(),
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                errors=[f"计算错误: {str(e)}"],
            )
    
    def _calc_return(
        self,
        initial_value: Optional[float],
        final_value: Optional[float],
    ) -> Dict[str, Any]:
        """计算收益率"""
        if initial_value is None or final_value is None:
            raise ValueError("需要提供initial_value和final_value")
        
        if initial_value <= 0:
            raise ValueError("初始值必须大于0")
        
        total_return = (final_value - initial_value) / initial_value
        
        return {
            "calc_type": "return",
            "initial_value": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "total_return_pct": f"{total_return * 100:.2f}%",
            "explanation": f"从{initial_value}到{final_value}的总收益率为{total_return * 100:.2f}%",
        }
    
    def _calc_volatility(self, values: List[float]) -> Dict[str, Any]:
        """计算波动率（年化）"""
        if len(values) < 2:
            raise ValueError("需要至少2个数据点")
        
        # 计算日收益率
        returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                r = (values[i] - values[i-1]) / values[i-1]
                returns.append(r)
        
        if not returns:
            raise ValueError("无法计算有效收益率")
        
        # 计算标准差
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        daily_vol = math.sqrt(variance)
        
        # 年化（假设252个交易日）
        annual_vol = daily_vol * math.sqrt(252)
        
        return {
            "calc_type": "volatility",
            "data_points": len(values),
            "daily_volatility": daily_vol,
            "annual_volatility": annual_vol,
            "annual_volatility_pct": f"{annual_vol * 100:.2f}%",
            "explanation": f"基于{len(values)}个数据点，年化波动率约为{annual_vol * 100:.2f}%",
        }
    
    def _calc_max_drawdown(self, values: List[float]) -> Dict[str, Any]:
        """计算最大回撤"""
        if len(values) < 2:
            raise ValueError("需要至少2个数据点")
        
        max_value = values[0]
        max_drawdown = 0
        peak_idx = 0
        trough_idx = 0
        current_peak_idx = 0
        
        for i, value in enumerate(values):
            if value > max_value:
                max_value = value
                current_peak_idx = i
            
            drawdown = (max_value - value) / max_value if max_value > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                peak_idx = current_peak_idx
                trough_idx = i
        
        return {
            "calc_type": "max_drawdown",
            "data_points": len(values),
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": f"{max_drawdown * 100:.2f}%",
            "peak_index": peak_idx,
            "trough_index": trough_idx,
            "explanation": f"最大回撤为{max_drawdown * 100:.2f}%，发生在第{peak_idx}到第{trough_idx}个数据点之间",
        }
    
    def _calc_sharpe(
        self,
        values: List[float],
        risk_free_rate: float = 0.02,
    ) -> Dict[str, Any]:
        """计算夏普比率"""
        if len(values) < 2:
            raise ValueError("需要至少2个数据点")
        
        # 计算日收益率
        returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                r = (values[i] - values[i-1]) / values[i-1]
                returns.append(r)
        
        if not returns:
            raise ValueError("无法计算有效收益率")
        
        # 计算年化收益率
        mean_daily_return = sum(returns) / len(returns)
        annual_return = mean_daily_return * 252
        
        # 计算年化波动率
        variance = sum((r - mean_daily_return) ** 2 for r in returns) / len(returns)
        annual_vol = math.sqrt(variance) * math.sqrt(252)
        
        # 计算夏普比率
        if annual_vol > 0:
            sharpe = (annual_return - risk_free_rate) / annual_vol
        else:
            sharpe = 0
        
        return {
            "calc_type": "sharpe",
            "data_points": len(values),
            "annual_return": annual_return,
            "annual_return_pct": f"{annual_return * 100:.2f}%",
            "annual_volatility": annual_vol,
            "annual_volatility_pct": f"{annual_vol * 100:.2f}%",
            "risk_free_rate": risk_free_rate,
            "sharpe_ratio": sharpe,
            "explanation": f"夏普比率为{sharpe:.2f}，年化收益{annual_return * 100:.2f}%，年化波动{annual_vol * 100:.2f}%",
        }
