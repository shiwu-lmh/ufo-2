"""Check connectivity to the configured OpenAI-compatible model endpoint.

Run from the UFO directory:
    python test_qwen_connection.py

The script reads HOST_AGENT from config/ufo/agents.yaml and never prints the
API key.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from openai import OpenAI


CONFIG_PATH = Path(__file__).parent / "config" / "ufo" / "agents.yaml"


def load_agent(agent_name: str) -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    agent = config.get(agent_name)
    if not isinstance(agent, dict):
        raise ValueError(f"配置中没有找到代理: {agent_name}")

    api_base = str(agent.get("API_BASE", "")).strip()
    api_key = str(agent.get("API_KEY", "")).strip()
    model = str(agent.get("API_MODEL", "")).strip()
    if not api_base or api_base.startswith("YOUR_"):
        raise ValueError("请先在 agents.yaml 中填写 API_BASE")
    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError("请先在 agents.yaml 中填写 API_KEY")
    if not model or model.startswith("YOUR_"):
        raise ValueError("请先在 agents.yaml 中填写 API_MODEL")

    return {"api_base": api_base.rstrip("/"), "api_key": api_key, "model": model}


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 UFO 模型接口连通性")
    parser.add_argument(
        "--agent",
        default="HOST_AGENT",
        choices=("HOST_AGENT", "APP_AGENT", "BACKUP_AGENT", "EVALUATION_AGENT"),
        help="要测试的代理配置，默认 HOST_AGENT",
    )
    args = parser.parse_args()

    try:
        settings = load_agent(args.agent)
        print(f"正在测试: {args.agent}")
        print(f"接口地址: {settings['api_base']}")
        print(f"模型: {settings['model']}")

        client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["api_base"],
            timeout=30,
        )
        response = client.chat.completions.create(
            model=settings["model"],
            messages=[{"role": "user", "content": "只回复：连接成功"}],
            max_tokens=32,
            temperature=0,
        )
        answer = (response.choices[0].message.content or "").strip()
        print("连接成功")
        print(f"模型回复: {answer}")
        return 0
    except Exception as exc:
        print(f"连接失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
