"""工具基类 - 统一的工具结果封装"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from qwen_agent.tools.base import BaseTool, register_tool
from memfinrobot.memory.schemas import ToolResult


class MemFinBaseTool(BaseTool, ABC):
    """
    MemFinRobot工具基类
    
    扩展qwen-agent的BaseTool，提供：
    - 统一的结果封装（ToolResult）
    - 来源和时间戳记录
    - 错误处理
    """
    
    def call(self, params: Union[str, dict], **kwargs) -> str:
        """
        工具调用入口
        
        Args:
            params: 参数（字符串或字典）
            
        Returns:
            JSON格式的结果字符串
        """
        import json
        
        try:
            # 解析参数
            params_dict = self._verify_json_format_args(params)
            
            # 执行具体逻辑
            result = self._call_impl(params_dict, **kwargs)
            
            # 封装结果
            if isinstance(result, ToolResult):
                return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            else:
                tool_result = ToolResult(
                    success=True,
                    data=result,
                    source=self.name,
                    asof=datetime.now(),
                )
                return json.dumps(tool_result.to_dict(), ensure_ascii=False, indent=2)
                
        except Exception as e:
            error_result = ToolResult(
                success=False,
                data=None,
                source=self.name,
                errors=[str(e)],
            )
            return json.dumps(error_result.to_dict(), ensure_ascii=False, indent=2)
    
    @abstractmethod
    def _call_impl(self, params: dict, **kwargs) -> Union[ToolResult, Any]:
        """
        具体的工具实现
        
        子类需要实现此方法
        
        Args:
            params: 参数字典
            
        Returns:
            ToolResult或原始数据
        """
        raise NotImplementedError
