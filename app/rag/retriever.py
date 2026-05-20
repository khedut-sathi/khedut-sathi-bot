from app.database.connection import supabase
from app.rag.embeddings import embed_text


def find_matching_diseases(symptom_description: str, crop: str = None, top_k: int = 3) -> list[dict]:
    query_embedding = embed_text(symptom_description)

    result = supabase.rpc("match_diseases", {
        "query_embedding": query_embedding,
        "match_crop": crop,
        "match_count": top_k,
    }).execute()

    return result.data if result.data else []
