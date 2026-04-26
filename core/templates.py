"""加载 Prompt 模板"""
import json
from pathlib import Path
import streamlit as st


@st.cache_data
def load_templates() -> list[dict]:
    """加载 prompts/templates.json"""
    path = Path(__file__).parent.parent / "prompts" / "templates.json"
    if not path.exists():
        return [{"name": "通用助手", "prompt": ""}]
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return [{"name": "通用助手", "prompt": ""}]


def get_template_names() -> list[str]:
    return [t["name"] for t in load_templates()]


def get_template_prompt(name: str) -> str:
    for t in load_templates():
        if t["name"] == name:
            return t["prompt"]
    return ""
