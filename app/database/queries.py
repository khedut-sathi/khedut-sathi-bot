from datetime import datetime, timezone
from app.database.connection import supabase


def get_or_create_user(telegram_id: int, first_name: str = "", language: str = "gu") -> dict:
    result = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()

    if result.data:
        supabase.table("users").update(
            {"last_active": datetime.now(timezone.utc).isoformat()}
        ).eq("telegram_id", telegram_id).execute()
        return result.data[0]

    new_user = {
        "telegram_id": telegram_id,
        "first_name": first_name,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_active": datetime.now(timezone.utc).isoformat(),
    }
    result = supabase.table("users").insert(new_user).execute()
    return result.data[0]


def update_user_language(telegram_id: int, language: str) -> dict:
    result = (
        supabase.table("users")
        .update({"language": language})
        .eq("telegram_id", telegram_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def update_user_district(telegram_id: int, district: str) -> dict:
    result = (
        supabase.table("users")
        .update({"district": district})
        .eq("telegram_id", telegram_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def log_analytics(user_id: int, event_type: str, metadata: dict = None):
    supabase.table("analytics").insert(
        {
            "user_id": user_id,
            "event_type": event_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
