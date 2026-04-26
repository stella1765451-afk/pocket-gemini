"""
数据库路由：
- 配置了 SUPABASE_URL + SUPABASE_KEY → 用 Supabase（云端持久化）
- 否则 → 用 SQLite（本地）

对外接口完全相同，调用方无需关心底层。
"""
from core.config import is_supabase_enabled

if is_supabase_enabled():
    from core.db_supabase import (
        create_conversation,
        list_conversations,
        get_conversation,
        rename_conversation,
        update_conversation_settings,
        delete_conversation,
        touch_conversation,
        add_message,
        get_messages,
        delete_message,
        delete_messages_after,
        get_total_token_usage,
    )
    BACKEND = "supabase"
else:
    from core.db_sqlite import (
        create_conversation,
        list_conversations,
        get_conversation,
        rename_conversation,
        update_conversation_settings,
        delete_conversation,
        touch_conversation,
        add_message,
        get_messages,
        delete_message,
        delete_messages_after,
        get_total_token_usage,
    )
    BACKEND = "sqlite"


__all__ = [
    "BACKEND",
    "create_conversation",
    "list_conversations",
    "get_conversation",
    "rename_conversation",
    "update_conversation_settings",
    "delete_conversation",
    "touch_conversation",
    "add_message",
    "get_messages",
    "delete_message",
    "delete_messages_after",
    "get_total_token_usage",
]
