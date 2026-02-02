"""通用工具函数"""

import json
import re
from datetime import datetime
from typing import Any, Optional


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def estimate_tokens(text: str, chars_per_token: float = 2.5) -> int:
    """
    估算文本的token数量
    
    Args:
        text: 文本内容
        chars_per_token: 每token对应的字符数（中文约2-3）
        
    Returns:
        估算的token数量
    """
    return int(len(text) / chars_per_token)


def format_datetime(
    dt: Optional[datetime] = None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    格式化日期时间
    
    Args:
        dt: 日期时间对象，默认为当前时间
        fmt: 格式字符串
        
    Returns:
        格式化后的字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全的JSON解析
    
    Args:
        text: JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            # 尝试作为Python字面量解析
            return eval(text)
        except Exception:
            return default


def extract_code_blocks(text: str) -> list:
    """
    从文本中提取代码块
    
    Args:
        text: 包含代码块的文本
        
    Returns:
        代码块列表
    """
    pattern = r'```(?:\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches


def clean_llm_response(response: str) -> str:
    """
    清理LLM响应中的格式问题
    
    Args:
        response: 原始响应
        
    Returns:
        清理后的响应
    """
    # 移除多余的空行
    response = re.sub(r'\n{3,}', '\n\n', response)
    
    # 移除首尾空白
    response = response.strip()
    
    return response


def is_valid_stock_code(code: str) -> bool:
    """
    验证股票代码格式
    
    Args:
        code: 股票代码
        
    Returns:
        是否有效
    """
    # A股代码：6位数字
    if re.match(r'^[0-9]{6}$', code):
        return True
    return False


def is_valid_fund_code(code: str) -> bool:
    """
    验证基金代码格式
    
    Args:
        code: 基金代码
        
    Returns:
        是否有效
    """
    # 基金代码：6位数字
    if re.match(r'^[0-9]{6}$', code):
        return True
    return False
