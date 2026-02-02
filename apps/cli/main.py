"""MemFinRobot CLI入口"""

import argparse
import logging
import os
import sys
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memfinrobot.agent.memfin_agent import MemFinFnCallAgent
from memfinrobot.config.settings import Settings, init_settings
from memfinrobot.tools import get_default_tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_agent(settings: Settings) -> MemFinFnCallAgent:
    """创建智能体实例"""
    # 获取工具列表
    tools = get_default_tools()
    
    # 创建智能体
    agent = MemFinFnCallAgent(
        function_list=tools,
        llm=settings.llm.to_dict(),
        settings=settings,
    )
    
    return agent


def run_interactive(agent: MemFinFnCallAgent, user_id: str = "cli_user"):
    """交互式运行"""
    print("\n" + "="*60)
    print("  MemFinRobot - 智能理财顾问助手")
    print("  输入 'quit' 或 'exit' 退出")
    print("  输入 'clear' 清除对话历史")
    print("="*60 + "\n")
    
    session_id = None
    
    while True:
        try:
            user_input = input("您: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n再见！祝您投资顺利！\n")
                break
            
            if user_input.lower() == 'clear':
                session_id = None
                print("\n[对话历史已清除]\n")
                continue
            
            # 调用智能体
            print("\nMemFinRobot: ", end="", flush=True)
            
            response = agent.handle_turn(
                user_message=user_input,
                session_id=session_id,
                user_id=user_id,
            )
            
            # 获取或更新session_id
            if session_id is None:
                for sid, state in agent._sessions.items():
                    if state.user_id == user_id:
                        session_id = sid
                        break
            
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n\n再见！祝您投资顺利！\n")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n[错误] {e}\n")


def run_single_query(agent: MemFinFnCallAgent, query: str, user_id: str = "cli_user"):
    """单次查询"""
    response = agent.handle_turn(
        user_message=query,
        user_id=user_id,
    )
    print(response)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MemFinRobot - 智能理财顾问助手"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="配置文件路径"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="单次查询（不进入交互模式）"
    )
    parser.add_argument(
        "--user-id", "-u",
        type=str,
        default="cli_user",
        help="用户ID"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="启用调试模式"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 加载配置
    if args.config:
        settings = init_settings(args.config)
    else:
        settings = init_settings()
    
    # 创建智能体
    try:
        agent = create_agent(settings)
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        print(f"[错误] 无法创建智能体: {e}")
        print("请检查配置和API密钥设置")
        sys.exit(1)
    
    # 运行
    if args.query:
        run_single_query(agent, args.query, args.user_id)
    else:
        run_interactive(agent, args.user_id)


if __name__ == "__main__":
    main()
