import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from app.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

_models = {name: genai.GenerativeModel(name) for name in MODEL_CHAIN}


def generate(contents, temperature: float = 0.5, max_tokens: int = 4000) -> str:
    config = genai.GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    last_error = None
    for model_name in MODEL_CHAIN:
        try:
            response = _models[model_name].generate_content(
                contents,
                generation_config=config,
            )
            logger.info(f"Used model: {model_name}")
            return response.text
        except ResourceExhausted as e:
            logger.warning(f"{model_name} quota exhausted, trying next...")
            last_error = e
            continue

    raise last_error
