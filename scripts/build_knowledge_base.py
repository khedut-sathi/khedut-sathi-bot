"""Load disease knowledge base into Supabase with embeddings. Run once."""
import json
import sys
import time

sys.path.insert(0, ".")

from app.database.connection import supabase
from app.rag.embeddings import embed_disease_entry


def load_and_embed():
    with open("data/diseases/gujarat_diseases.json") as f:
        diseases = json.load(f)

    print(f"Loading {len(diseases)} disease entries...")

    for i, disease in enumerate(diseases):
        print(f"  [{i+1}/{len(diseases)}] {disease['crop']} - {disease['disease_name_en']}...", end=" ")

        embedding = embed_disease_entry(disease)

        row = {
            "crop": disease["crop"],
            "disease_name_en": disease["disease_name_en"],
            "disease_name_gu": disease.get("disease_name_gu"),
            "disease_type": disease.get("disease_type"),
            "causal_organism": disease.get("causal_organism"),
            "symptoms_text": disease["symptoms_text"],
            "symptoms_visual": disease.get("symptoms_visual"),
            "affected_plant_parts": disease.get("affected_plant_parts", []),
            "favorable_conditions": disease.get("favorable_conditions"),
            "critical_crop_stage": disease.get("critical_crop_stage"),
            "season": disease.get("season", []),
            "cultural_management": disease.get("cultural_management"),
            "chemical_management": disease.get("chemical_management"),
            "biological_management": disease.get("biological_management"),
            "prevention": disease.get("prevention"),
            "recommended_pesticides": disease.get("recommended_pesticides"),
            "source": disease.get("source"),
            "embedding": embedding,
        }

        try:
            supabase.table("disease_knowledge").insert(row).execute()
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")

        time.sleep(0.5)

    print(f"\nDone! Loaded {len(diseases)} entries.")

    result = supabase.table("disease_knowledge").select("id, crop, disease_name_en").execute()
    print(f"Verified: {len(result.data)} entries in database")


if __name__ == "__main__":
    load_and_embed()
