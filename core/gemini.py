"""
Gemini API 封装：客户端、模型列表、对话调用
"""
import os
import re
import tempfile
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

from core.config import get_api_key, FALLBACK_MODELS

# ============================================================
# 客户端
# ============================================================
@st.cache_resource
def get_client():
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ 请在 Streamlit Secrets 配置 GEMINI_API_KEY")
        st.stop()
    return genai.Client(api_key=api_key)


# ============================================================
# 模型列表（动态拉取 + 排序）
# ============================================================
def _pretty_name(model_id: str) -> str:
    name = model_id.replace("models/", "").replace("-", " ")
    parts = []
    for word in name.split():
        if re.match(r"^\d", word):
            parts.append(word)
        else:
            parts.append(word.capitalize())
    return " ".join(parts)


def _model_priority(model_id: str) -> tuple:
    mid = model_id.lower()
    version_match = re.search(r"gemini-(\d+(?:\.\d+)?)", mid)
    version = float(version_match.group(1)) if version_match else 0.0

    if "flash-lite" in mid:
        tier = 2
    elif "pro" in mid:
        tier = 0
    elif "flash" in mid:
        tier = 1
    else:
        tier = 3

    is_unstable = 1 if ("preview" in mid or "exp" in mid) else 0
    return (-version, tier, is_unstable, mid)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_available_models() -> dict[str, str]:
    """拉取可用于对话的 Gemini 模型，缓存 1 小时"""
    try:
        client = get_client()
        models = client.models.list()
    except Exception as e:
        st.warning(f"拉取模型列表失败：{e}")
        return FALLBACK_MODELS

    result: dict[str, str] = {}
    for m in models:
        model_id = m.name.replace("models/", "")
        mid_lower = model_id.lower()

        if not mid_lower.startswith("gemini"):
            continue

        actions = (
            getattr(m, "supported_actions", None)
            or getattr(m, "supported_generation_methods", None)
            or []
        )
        if actions and "generateContent" not in actions:
            continue

        skip = ["embedding", "embed", "tts", "image-generation",
                "image-preview", "live", "native-audio", "aqa",
                "thinking-exp"]
        if any(kw in mid_lower for kw in skip):
            continue

        if re.match(r"^gemini-1\.", mid_lower):
            continue

        result[_pretty_name(model_id)] = model_id

    if not result:
        return FALLBACK_MODELS

    sorted_items = sorted(result.items(), key=lambda kv: _model_priority(kv[1]))
    return dict(sorted_items)


# ============================================================
# 文件转 parts
# ============================================================
def files_to_parts(files) -> tuple[list, list[bytes], list[str]]:
    """
    把 Streamlit 上传的文件转成 Gemini parts。
    返回 (parts, image_previews_bytes, file_names)
    """
    if not files:
        return [], [], []

    client = get_client()
    parts, image_previews, file_names = [], [], []

    for f in files:
        file_bytes = f.read()
        f.seek(0)
        file_names.append(f.name)
        is_image = f.type and f.type.startswith("image/")

        if is_image and len(file_bytes) < 7 * 1024 * 1024:
            parts.append(
                types.Part.from_bytes(data=file_bytes, mime_type=f.type)
            )
            image_previews.append(file_bytes)
        else:
            suffix = Path(f.name).suffix or ""
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                uploaded = client.files.upload(file=tmp_path)
                parts.append(uploaded)
                if is_image:
                    image_previews.append(file_bytes)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return parts, image_previews, file_names


# ============================================================
# 调用 Gemini（流式 + 返回 token 用量）
# ============================================================
def stream_chat(
    model_id: str,
    contents: list,
    system_prompt: str = "",
    temperature: float = 1.0,
    max_tokens: int = 8192,
    tools: list | None = None,
):
    """
    流式调用 Gemini。
    yield (chunk_text, is_final, usage_metadata)
    其中 usage_metadata 只在 is_final=True 时返回完整数据。
    """
    client = get_client()

    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": int(max_tokens),
    }
    if system_prompt and system_prompt.strip():
        config_kwargs["system_instruction"] = system_prompt.strip()
    if tools:
        config_kwargs["tools"] = tools

    config = types.GenerateContentConfig(**config_kwargs)

    last_usage = None
    try:
        stream = client.models.generate_content_stream(
            model=model_id,
            contents=contents,
            config=config,
        )
        for chunk in stream:
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                last_usage = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                    "output_tokens": (
                        getattr(usage, "candidates_token_count", 0) or 0
                    ),
                    "total_tokens": getattr(usage, "total_token_count", 0) or 0,
                }
            text = chunk.text if hasattr(chunk, "text") else None
            if text:
                yield text, False, None

        yield "", True, last_usage

    except Exception as e:
        yield f"\n\n❌ 调用出错：`{e}`", True, None


# ============================================================
# 一次性生成（非流式，用于摘要、命名等场景）
# ============================================================
def quick_generate(
    model_id: str,
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 200,
) -> str:
    """简单生成（不流式），用于自动命名对话、生成摘要等"""
    client = get_client()
    config_kwargs = {"max_output_tokens": max_tokens, "temperature": 0.5}
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt
    try:
        resp = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return (resp.text or "").strip()
    except Exception:
        return ""


def auto_title_for(first_user_msg: str, model_id: str) -> str:
    """根据第一条用户消息自动生成对话标题"""
    if not first_user_msg.strip():
        return "新对话"
    # 用便宜的 lite 模型生成
    cheap_model = "gemini-2.5-flash-lite"
    title = quick_generate(
        model_id=cheap_model,
        prompt=f"为以下对话起一个简短标题（不超过15字，只输出标题本身，不要引号或多余说明）：\n\n{first_user_msg[:500]}",
        max_tokens=50,
    )
    title = title.strip().strip('"').strip("'").strip("《》").strip()
    if not title:
        title = first_user_msg[:20]
    return title[:30]
