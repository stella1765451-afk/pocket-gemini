"""
Supabase 持久化存储
和 db.py（SQLite）接口完全一致，可以无缝切换。

表结构（在 Supabase SQL Editor 里执行）：

CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新对话',
    model_id TEXT,
    system_prompt TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX idx_messages_conv ON messages(conversation_id);
CREATE INDEX idx_conv_updated ON conversations(updated_at DESC);
"""
import time
import json
from typing import Any
import streamlit as st

from core.config import get_supabase_url, get_supabase_key


# ============================================================
# 客户端
# ============================================================
@st.cache_resource
def get_supabase():
    from supabase import create_client
    return create_client(get_supabase_url(), get_supabase_key())


# ============================================================
# 对话操作
# ============================================================
def create_conversation(
    title: str = "新对话",
    model_id: str = "",
    system_prompt: str = "",
) -> int:
    sb = get_supabase()
    now = time.time()
    resp = sb.table("conversations").insert({
        "title": title,
        "model_id": model_id,
        "system_prompt": system_prompt,
        "created_at": now,
        "updated_at": now,
    }).execute()
    return int(resp.data[0]["id"])


def list_conversations(limit: int = 50) -> list[dict]:
    sb = get_supabase()
    resp = (
        sb.table("conversations")
        .select("id, title, model_id, updated_at")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    convs = resp.data or []
    if not convs:
        return []

    # 批量统计每个对话的消息数
    conv_ids = [c["id"] for c in convs]
    msg_resp = (
        sb.table("messages")
        .select("conversation_id")
        .in_("conversation_id", conv_ids)
        .execute()
    )
    counts = {}
    for m in (msg_resp.data or []):
        cid = m["conversation_id"]
        counts[cid] = counts.get(cid, 0) + 1

    for c in convs:
        c["msg_count"] = counts.get(c["id"], 0)
    return convs


def get_conversation(conv_id: int) -> dict | None:
    sb = get_supabase()
    resp = (
        sb.table("conversations")
        .select("*")
        .eq("id", conv_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def rename_conversation(conv_id: int, title: str):
    sb = get_supabase()
    sb.table("conversations").update({
        "title": title,
        "updated_at": time.time(),
    }).eq("id", conv_id).execute()


def update_conversation_settings(
    conv_id: int, model_id: str = None, system_prompt: str = None
):
    update = {"updated_at": time.time()}
    if model_id is not None:
        update["model_id"] = model_id
    if system_prompt is not None:
        update["system_prompt"] = system_prompt
    if len(update) == 1:
        return
    sb = get_supabase()
    sb.table("conversations").update(update).eq("id", conv_id).execute()


def delete_conversation(conv_id: int):
    """ON DELETE CASCADE 会自动清理 messages"""
    sb = get_supabase()
    sb.table("conversations").delete().eq("id", conv_id).execute()


def touch_conversation(conv_id: int):
    sb = get_supabase()
    sb.table("conversations").update({
        "updated_at": time.time(),
    }).eq("id", conv_id).execute()


# ============================================================
# 消息操作
# ============================================================
def add_message(
    conv_id: int,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> int:
    sb = get_supabase()
    resp = sb.table("messages").insert({
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "meta": meta or {},
        "created_at": time.time(),
    }).execute()
    touch_conversation(conv_id)
    return int(resp.data[0]["id"])


def get_messages(conv_id: int) -> list[dict]:
    sb = get_supabase()
    resp = (
        sb.table("messages")
        .select("id, role, content, meta, created_at")
        .eq("conversation_id", conv_id)
        .order("id", desc=False)
        .execute()
    )
    rows = resp.data or []
    # meta 已是 dict（jsonb），统一处理
    for r in rows:
        if isinstance(r.get("meta"), str):
            try:
                r["meta"] = json.loads(r["meta"])
            except json.JSONDecodeError:
                r["meta"] = {}
        elif r.get("meta") is None:
            r["meta"] = {}
    return rows


def delete_message(msg_id: int):
    sb = get_supabase()
    sb.table("messages").delete().eq("id", msg_id).execute()


def delete_messages_after(conv_id: int, msg_id: int):
    sb = get_supabase()
    sb.table("messages").delete().eq(
        "conversation_id", conv_id
    ).gte("id", msg_id).execute()


def get_total_token_usage(conv_id: int) -> tuple[int, int, float]:
    sb = get_supabase()
    resp = (
        sb.table("messages")
        .select("meta")
        .eq("conversation_id", conv_id)
        .eq("role", "assistant")
        .execute()
    )
    in_total, out_total, cost_total = 0, 0, 0.0
    for r in (resp.data or []):
        meta = r.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        in_total += meta.get("input_tokens", 0)
        out_total += meta.get("output_tokens", 0)
        cost_total += meta.get("cost", 0.0)
    return in_total, out_total, cost_total
