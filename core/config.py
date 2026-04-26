"""全局配置：API Key、模型列表、价格表、Supabase 配置"""
import os
import streamlit as st

# ============================================================
# API Key
# ============================================================
def get_api_key() -> str | None:
    return st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))


def get_access_password() -> str | None:
    return st.secrets.get("ACCESS_PASSWORD", os.getenv("ACCESS_PASSWORD"))


# ============================================================
# Supabase 配置
# ============================================================
def get_supabase_url() -> str | None:
    return st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))


def get_supabase_key() -> str | None:
    """用 service_role key（后端权限），简化部署"""
    return st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))


def is_supabase_enabled() -> bool:
    return bool(get_supabase_url() and get_supabase_key())


# ============================================================
# 模型兜底列表
# ============================================================
FALLBACK_MODELS = {
    "Gemini 3.1 Pro Preview (最强)": "gemini-3.1-pro-preview",
    "Gemini 3.1 Flash Lite Preview (快)": "gemini-3.1-flash-lite-preview",
    "Gemini 2.5 Pro": "gemini-2.5-pro",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 2.5 Flash-Lite": "gemini-2.5-flash-lite",
}

# ============================================================
# 模型价格（USD per 1M tokens）— 2026 年 4 月
# ============================================================
MODEL_PRICING = {
    "gemini-3.1-pro-preview": (1.25, 10.00),
    "gemini-3.1-flash-lite-preview": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    if model_id not in MODEL_PRICING:
        in_price, out_price = 1.25, 10.00
    else:
        in_price, out_price = MODEL_PRICING[model_id]
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


# ============================================================
# 应用元数据
# ============================================================
APP_NAME = "Gemini Chat"
APP_ICON = "✨"
APP_DESCRIPTION = "你的私人 Gemini 对话工具"
