"""MemFinRobot CLI鍏ュ彛"""

import argparse
import logging
import os
import sys
from typing import Optional

# 娣诲姞椤圭洰鏍圭洰褰曞埌璺緞
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memfinrobot.agent.memfin_agent import MemFinFnCallAgent
from memfinrobot.config.settings import Settings, init_settings
from memfinrobot.tools import get_default_tools

# 閰嶇疆鏃ュ織
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_agent(settings: Settings) -> MemFinFnCallAgent:
    """鍒涘缓鏅鸿兘浣撳疄渚?""
    # 鑾峰彇宸ュ叿鍒楄〃
    tools = get_default_tools(settings=settings)
    
    # 鍒涘缓鏅鸿兘浣?
    agent = MemFinFnCallAgent(
        function_list=tools,
        llm=settings.llm.to_dict(),
        settings=settings,
    )
    
    return agent


def run_interactive(agent: MemFinFnCallAgent, user_id: str = "cli_user"):
    """浜や簰寮忚繍琛?""
    print("\n" + "="*60)
    print("  MemFinRobot - 鏅鸿兘鐞嗚储椤鹃棶鍔╂墜")
    print("  杈撳叆 'quit' 鎴?'exit' 閫€鍑?)
    print("  杈撳叆 'clear' 娓呴櫎瀵硅瘽鍘嗗彶")
    print("="*60 + "\n")
    
    session_id = None
    
    while True:
        try:
            user_input = input("鎮? ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n鍐嶈锛佺鎮ㄦ姇璧勯『鍒╋紒\n")
                break
            
            if user_input.lower() == 'clear':
                session_id = None
                print("\n[瀵硅瘽鍘嗗彶宸叉竻闄\n")
                continue
            
            # 璋冪敤鏅鸿兘浣?
            print("\nMemFinRobot: ", end="", flush=True)
            
            response = agent.handle_turn(
                user_message=user_input,
                session_id=session_id,
                user_id=user_id,
            )
            
            # 鑾峰彇鎴栨洿鏂皊ession_id
            if session_id is None:
                for sid, state in agent._sessions.items():
                    if state.user_id == user_id:
                        session_id = sid
                        break
            
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n\n鍐嶈锛佺鎮ㄦ姇璧勯『鍒╋紒\n")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n[閿欒] {e}\n")


def run_single_query(agent: MemFinFnCallAgent, query: str, user_id: str = "cli_user"):
    """鍗曟鏌ヨ"""
    response = agent.handle_turn(
        user_message=query,
        user_id=user_id,
    )
    print(response)


def main():
    """涓诲嚱鏁?""
    parser = argparse.ArgumentParser(
        description="MemFinRobot - 鏅鸿兘鐞嗚储椤鹃棶鍔╂墜"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="閰嶇疆鏂囦欢璺緞"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="鍗曟鏌ヨ锛堜笉杩涘叆浜や簰妯″紡锛?
    )
    parser.add_argument(
        "--user-id", "-u",
        type=str,
        default="cli_user",
        help="鐢ㄦ埛ID"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="鍚敤璋冭瘯妯″紡"
    )
    
    args = parser.parse_args()
    
    # 璁剧疆鏃ュ織绾у埆
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 鍔犺浇閰嶇疆
    if args.config:
        settings = init_settings(args.config)
    else:
        settings = init_settings()
    
    # 鍒涘缓鏅鸿兘浣?
    try:
        agent = create_agent(settings)
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        print(f"[閿欒] 鏃犳硶鍒涘缓鏅鸿兘浣? {e}")
        print("璇锋鏌ラ厤缃拰API瀵嗛挜璁剧疆")
        sys.exit(1)
    
    # 杩愯
    if args.query:
        run_single_query(agent, args.query, args.user_id)
    else:
        run_interactive(agent, args.user_id)


if __name__ == "__main__":
    main()

