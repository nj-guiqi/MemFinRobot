"""窗口内容精炼器 - 将选中的历史片段精炼为可写入长期记忆的条目"""

import logging
from typing import Any, Dict, List, Optional

from memfinrobot.memory.schemas import RefinedMemory

logger = logging.getLogger(__name__)


# 精炼提示词模板
REFINE_PROMPT = """你是一个对话记忆精炼助手。给定一段与当前查询相关的历史对话，你需要提取出关键信息要点。

任务：将历史对话精炼为简洁的要点列表，保留对理解当前查询最重要的信息。

规则：
1. 提取关键事实、偏好、约束等信息
2. 保持简洁，每个要点一句话
3. 返回JSON列表格式，如 ["要点1", "要点2"]
4. 如果没有重要信息需要提取，返回 []

历史对话:
{selected_content}

当前查询: {current_query}

请返回精炼后的要点列表:"""


class WindowRefiner:
    """
    窗口内容精炼器
    
    将选中的窗口内容变成"可写入长期记忆的干净条目"
    对选中的窗口内容进行"指令化/要点化"提炼，减少噪声、提升可复用性
    """
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_refine_length: int = 2000,
    ):
        """
        初始化精炼器
        
        Args:
            llm_client: LLM客户端
            max_refine_length: 最大精炼文本长度
        """
        self.llm_client = llm_client
        self.max_refine_length = max_refine_length
    
    def refine(
        self,
        selected_texts: List[str],
        current_query: str,
        source_indices: Optional[List[int]] = None,
    ) -> RefinedMemory:
        """
        精炼选中的窗口内容
        
        Args:
            selected_texts: 选中的历史对话文本列表
            current_query: 当前查询
            source_indices: 来源轮次索引
            
        Returns:
            RefinedMemory 包含精炼后的文本和引用信息
        """
        if not selected_texts:
            return RefinedMemory(
                refined_texts=[],
                citations=[],
                source_indices=source_indices or [],
            )
        
        # 如果没有LLM客户端，使用简单的回退策略
        if self.llm_client is None:
            return self._fallback_refine(selected_texts, source_indices)
        
        try:
            refined_texts = self._llm_refine(selected_texts, current_query)
            
            # 构建引用信息
            citations = [
                {"index": idx, "original": text}
                for idx, text in zip(source_indices or range(len(selected_texts)), selected_texts)
            ]
            
            return RefinedMemory(
                refined_texts=refined_texts,
                citations=citations,
                source_indices=source_indices or list(range(len(selected_texts))),
            )
            
        except Exception as e:
            logger.warning(f"Refine failed: {e}, using fallback")
            return self._fallback_refine(selected_texts, source_indices)
    
    def _llm_refine(
        self,
        selected_texts: List[str],
        current_query: str,
    ) -> List[str]:
        """使用LLM精炼"""
        # 格式化选中的内容
        selected_content = "\n".join([
            f"[{idx}] {text}" for idx, text in enumerate(selected_texts)
        ])
        
        # 截断过长的内容
        if len(selected_content) > self.max_refine_length:
            selected_content = selected_content[:self.max_refine_length] + "..."
        
        prompt = REFINE_PROMPT.format(
            selected_content=selected_content,
            current_query=current_query,
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        response = self.llm_client.chat(
            messages=messages,
            stream=False,
            extra_generate_cfg={"temperature": 0.2},
        )
        
        # 解析响应
        if hasattr(response, '__iter__'):
            for r in response:
                if r:
                    response_text = r[-1].content if hasattr(r[-1], 'content') else str(r[-1])
                    break
        else:
            response_text = str(response)
        
        try:
            import json
            result = json.loads(response_text.strip())
            if isinstance(result, list):
                return [str(item) for item in result]
        except Exception:
            pass
        
        try:
            result = eval(response_text.strip())
            if isinstance(result, list):
                return [str(item) for item in result]
        except Exception:
            pass
        
        # 如果解析失败，返回原始响应作为单个要点
        return [response_text.strip()] if response_text.strip() else []
    
    def _fallback_refine(
        self,
        selected_texts: List[str],
        source_indices: Optional[List[int]] = None,
    ) -> RefinedMemory:
        """回退策略：直接返回原文（截断过长的内容）"""
        refined_texts = []
        for text in selected_texts:
            if len(text) > 200:
                refined_texts.append(text[:200] + "...")
            else:
                refined_texts.append(text)
        
        citations = [
            {"index": idx, "original": text}
            for idx, text in zip(source_indices or range(len(selected_texts)), selected_texts)
        ]
        
        return RefinedMemory(
            refined_texts=refined_texts,
            citations=citations,
            source_indices=source_indices or list(range(len(selected_texts))),
        )
    
    def build_hierarchical_content(
        self,
        refined_memory: RefinedMemory,
        current_content: str,
    ) -> str:
        """
        构建分层表征内容
        
        将"精炼记忆 | [context] | 当前轮内容"拼接为层级文本
        
        Args:
            refined_memory: 精炼后的记忆
            current_content: 当前轮内容
            
        Returns:
            分层表征字符串
        """
        if not refined_memory.refined_texts:
            return current_content
        
        refined_str = " ".join(refined_memory.refined_texts)
        return f"{refined_str} | [context] | {current_content}"
