import logging
from app.services.gemini import generate
from app.rag.retriever import find_matching_diseases
from app.prompts.disease_prompt import (
    SYMPTOM_EXTRACTION_PROMPT,
    DIAGNOSIS_PROMPT,
    DIAGNOSIS_NO_MATCH_PROMPT,
)

logger = logging.getLogger(__name__)


async def extract_symptoms(image_bytes: bytes) -> dict:
    """Use Gemini Vision to describe crop symptoms from photo."""
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    symptoms_text = generate(
        [SYMPTOM_EXTRACTION_PROMPT, image_part],
        temperature=0.3,
        max_tokens=1000,
    )

    crop = None
    crop_keywords = {
        "cotton": "cotton", "kapas": "cotton",
        "groundnut": "groundnut", "peanut": "groundnut",
        "wheat": "wheat",
        "cumin": "cumin", "jeera": "cumin",
        "castor": "castor",
        "bajra": "bajra", "pearl millet": "bajra",
        "mung": "mung", "moong": "mung",
        "sesame": "sesame", "til": "sesame",
        "rice": "rice", "paddy": "rice",
    }

    lower_text = symptoms_text.lower()
    for keyword, crop_name in crop_keywords.items():
        if keyword in lower_text:
            crop = crop_name
            break

    return {"symptoms": symptoms_text, "crop": crop}


async def diagnose_disease(image_bytes: bytes, crop_hint: str = None, language: str = "gu") -> str:
    """Full RAG pipeline: image → symptoms → vector search → diagnosis."""
    result = await extract_symptoms(image_bytes)
    symptoms = result["symptoms"]
    detected_crop = crop_hint or result["crop"]

    lang_name = "Gujarati" if language == "gu" else "Hindi"

    matches = find_matching_diseases(
        symptom_description=symptoms,
        crop=detected_crop,
        top_k=3,
    )

    if matches and matches[0].get("similarity", 0) > 0.3:
        rag_context = ""
        for i, m in enumerate(matches, 1):
            rag_context += f"""
Disease {i}: {m['disease_name_en']} ({m.get('disease_name_gu', '')})
Type: {m.get('disease_type', 'unknown')}
Symptoms: {m.get('symptoms_text', '')}
Chemical Treatment: {m.get('chemical_management', 'N/A')}
Cultural Management: {m.get('cultural_management', 'N/A')}
Biological Management: {m.get('biological_management', 'N/A')}
Prevention: {m.get('prevention', 'N/A')}
Similarity: {m.get('similarity', 0):.2f}
---"""

        prompt = DIAGNOSIS_PROMPT.format(
            symptoms=symptoms,
            rag_results=rag_context,
            language=lang_name,
        )
    else:
        prompt = DIAGNOSIS_NO_MATCH_PROMPT.format(
            symptoms=symptoms,
            language=lang_name,
        )

    return generate(prompt, temperature=0.4, max_tokens=4000)
