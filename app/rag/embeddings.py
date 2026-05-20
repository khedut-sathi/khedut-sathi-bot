import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.gemini_api_key)

EMBEDDING_DIMENSION = 768


def embed_text(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        output_dimensionality=EMBEDDING_DIMENSION,
    )
    return result["embedding"]


def embed_disease_entry(entry: dict) -> list[float]:
    text = (
        f"{entry['crop']} disease. {entry['disease_name_en']}. "
        f"Symptoms: {entry['symptoms_text']} "
        f"Visual: {entry.get('symptoms_visual', '')} "
        f"Affects: {', '.join(entry.get('affected_plant_parts', []))}. "
        f"Conditions: {entry.get('favorable_conditions', '')}"
    )
    return embed_text(text)
