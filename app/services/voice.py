import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio using OpenAI Whisper API."""
    api_key = settings.openai_api_key
    if not api_key:
        return None

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    mime = "audio/ogg" if filename.endswith(".ogg") else "audio/mpeg"
    files = {
        "file": (filename, audio_bytes, mime),
    }
    data = {
        "model": "whisper-1",
        "language": "gu",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            result = resp.json()
            return result.get("text", "")
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None
