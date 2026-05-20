from app.services.gemini import generate
from app.prompts.chat_prompt import FARMING_CHAT_PROMPT


async def farming_chat(question: str, language: str = "gu") -> str:
    lang_name = "Gujarati" if language == "gu" else "Hindi"

    prompt = FARMING_CHAT_PROMPT.format(
        language=lang_name,
        question=question,
    )

    return generate(prompt, temperature=0.5, max_tokens=4000)
