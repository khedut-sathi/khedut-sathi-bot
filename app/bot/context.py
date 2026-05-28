"""Session context manager — remembers crop, topic, and conversation flow."""


def get_session(context) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {
            "current_crop": None,
            "current_topic": None,
            "last_disease": None,
        }
    return context.user_data["session"]


def set_crop(context, crop: str):
    session = get_session(context)
    session["current_crop"] = crop


def get_crop(context, db_user: dict = None) -> str | None:
    session = get_session(context)
    if session["current_crop"]:
        return session["current_crop"]
    if db_user and db_user.get("crops"):
        return db_user["crops"][0]
    return None


def set_topic(context, topic: str):
    session = get_session(context)
    session["current_topic"] = topic


def set_last_disease(context, disease: str):
    session = get_session(context)
    session["last_disease"] = disease


def get_context_summary(context, db_user: dict = None) -> str:
    """Build a context string for Gemini to understand the conversation."""
    session = get_session(context)
    parts = []

    if db_user:
        name = db_user.get("first_name", "")
        district = db_user.get("district", "")
        crops = db_user.get("crops", [])
        if name:
            parts.append(f"Farmer name: {name}")
        if district:
            parts.append(f"Location: {district}, Gujarat")
        if crops:
            parts.append(f"Farmer's crops: {', '.join(crops)}")

    if session.get("current_crop"):
        parts.append(f"Currently discussing: {session['current_crop']}")
    if session.get("last_disease"):
        parts.append(f"Last diagnosed disease: {session['last_disease']}")

    return "\n".join(parts) if parts else ""
