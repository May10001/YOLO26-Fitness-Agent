"""
Simple script to test the remote DashScope API (Qwen2.5-7B).
Uses OpenAI-compatible mode — no local GPU / model download needed.

Usage:
    python scripts/test_remote_api.py
    python scripts/test_remote_api.py --query "如何做标准俯卧撑？"
"""
import argparse
import json
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "data" / "api_config.json"

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

SYSTEM_PROMPT = (
    "你是一个活泼可爱善于鼓励但又严厉的AI健身助手教练，拥有运动科学、运动解剖学和营养学背景。"
    "请用中文回答，保持专业且易懂，鼓舞人心，多使用连续的感叹号。"
)


def load_config() -> dict:
    """Load API config from data/api_config.json (gitignored)."""
    if not CONFIG_PATH.exists():
        print(f"[ERROR] 配置文件不存在: {CONFIG_PATH}")
        print("请在GUI设置面板中填写API Key和模型Code，或手动创建该文件。")
        print(f"参考模板: {BASE_DIR / 'data' / 'api_config.example.json'}")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if not cfg.get("api_key") or not cfg.get("model_code"):
        print("[ERROR] 配置文件中缺少 api_key 或 model_code")
        sys.exit(1)

    return cfg


def chat(api_key: str, model_code: str, user_message: str) -> str:
    """Send a single chat message and return the reply."""
    client = OpenAI(
        api_key=api_key,
        base_url=DASHSCOPE_BASE_URL,
    )

    completion = client.chat.completions.create(
        model=model_code,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=800,
    )

    return completion.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Test remote DashScope API")
    parser.add_argument(
        "--query", "-q",
        default="你好！请介绍一下自己！",
        help="User message to send (default: greeting)",
    )
    parser.add_argument(
        "--multi-turn", "-m",
        action="store_true",
        help="Enter interactive multi-turn chat mode",
    )
    args = parser.parse_args()

    cfg = load_config()
    api_key = cfg["api_key"]
    model_code = cfg["model_code"]

    print(f"Base URL : {DASHSCOPE_BASE_URL}")
    print(f"Model    : {model_code}")
    print(f"API Key  : {api_key[:8]}...{api_key[-4:]}")
    print("-" * 50)

    if args.multi_turn:
        print("多轮对话模式 (输入 /quit 退出)\n")
        client = OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break
            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "/q"):
                print("再见！")
                break

            messages.append({"role": "user", "content": user_input})
            print("AI: ", end="", flush=True)

            completion = client.chat.completions.create(
                model=model_code,
                messages=messages,
                temperature=0.7,
                max_tokens=800,
            )
            reply = completion.choices[0].message.content
            print(reply)
            messages.append({"role": "assistant", "content": reply})
    else:
        print(f"User: {args.query}")
        print("AI: ", end="", flush=True)
        reply = chat(api_key, model_code, args.query)
        print(reply)


if __name__ == "__main__":
    main()
