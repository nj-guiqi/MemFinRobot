"""LLM适配层 - 统一不同模型的调用方式"""

import os
from typing import Any, Dict, Optional, Union

from qwen_agent.llm import get_chat_model, BaseChatModel

from memfinrobot.config.settings import Settings, LLMConfig, get_settings


def create_llm_config(
    model: str = "qwen-plus",
    model_server: str = "dashscope",
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    **kwargs,
) -> Dict[str, Any]:
    """
    创建LLM配置字典
    
    Args:
        model: 模型名称
        model_server: 模型服务器类型
        api_key: API密钥
        temperature: 采样温度
        max_tokens: 最大token数
        
    Returns:
        qwen-agent兼容的配置字典
    """
    # 获取API密钥
    if api_key is None:
        if model_server == "dashscope":
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
        elif model_server == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
    
    config = {
        "model": model,
        "model_server": model_server,
        "api_key": api_key,
        "generate_cfg": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
    }
    
    return config


def get_llm_client(
    config: Optional[Union[Dict, LLMConfig, Settings]] = None,
) -> BaseChatModel:
    """
    获取LLM客户端实例
    
    Args:
        config: 配置对象或字典
        
    Returns:
        BaseChatModel实例
    """
    if config is None:
        settings = get_settings()
        config = settings.llm.to_dict()
    elif isinstance(config, Settings):
        config = config.llm.to_dict()
    elif isinstance(config, LLMConfig):
        config = config.to_dict()
    
    return get_chat_model(config)


class LLMAdapter:
    """
    LLM适配器
    
    提供统一的LLM调用接口，屏蔽底层差异
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        config: Optional[Dict] = None,
    ):
        """
        初始化适配器
        
        Args:
            settings: 全局配置
            config: LLM配置字典
        """
        if config:
            self.config = config
        elif settings:
            self.config = settings.llm.to_dict()
        else:
            self.config = get_settings().llm.to_dict()
        
        self._client = None
    
    @property
    def client(self) -> BaseChatModel:
        """获取LLM客户端（延迟初始化）"""
        if self._client is None:
            self._client = get_chat_model(self.config)
        return self._client
    
    def chat(
        self,
        messages: list,
        stream: bool = True,
        functions: Optional[list] = None,
        **kwargs,
    ):
        """
        调用LLM聊天接口
        
        Args:
            messages: 消息列表
            stream: 是否流式输出
            functions: 函数定义列表
            
        Returns:
            响应生成器或响应对象
        """
        return self.client.chat(
            messages=messages,
            stream=stream,
            functions=functions,
            **kwargs,
        )
    
    def generate(
        self,
        prompt: str,
        **kwargs,
    ) -> str:
        """
        简单的文本生成接口
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本
        """
        messages = [{"role": "user", "content": prompt}]
        
        response = ""
        for output in self.chat(messages, stream=False, **kwargs):
            if output:
                last_msg = output[-1]
                if hasattr(last_msg, 'content'):
                    response = last_msg.content
                elif isinstance(last_msg, dict):
                    response = last_msg.get('content', '')
        
        return response
