import logging
from datetime import datetime, timezone, timedelta
import asyncio
import requests
import httpx
from app.config import settings
from app.database.connection import supabase

logger = logging.getLogger(__name__)

CROP_NAME_MAP = {
    # Cotton
    "cotton": "Cotton", "kapas": "Cotton", "કપાસ": "Cotton", "कपास": "Cotton",
    "coton": "Cotton", "cottn": "Cotton", "cottom": "Cotton", "kapss": "Cotton",
    "kapaas": "Cotton", "કપાશ": "Cotton", "કપાષ": "Cotton", "રૂ": "Cotton",
    # Groundnut
    "groundnut": "Groundnut", "મગફળી": "Groundnut", "मूंगफली": "Groundnut",
    "singdana": "Groundnut", "સીંગદાણા": "Groundnut", "peanut": "Groundnut",
    "groundnt": "Groundnut", "groudnut": "Groundnut", "groundnuts": "Groundnut",
    "mungfali": "Groundnut", "moongfali": "Groundnut", "singtel": "Groundnut",
    # Wheat
    "wheat": "Wheat", "ઘઉં": "Wheat", "गेहूं": "Wheat",
    "ghau": "Wheat", "gahu": "Wheat", "gehun": "Wheat", "gehu": "Wheat",
    "wheet": "Wheat", "whaat": "Wheat",
    # Cumin
    "cumin": "Cumin(Jeera)", "jeera": "Cumin(Jeera)", "જીરું": "Cumin(Jeera)", "जीरा": "Cumin(Jeera)",
    "jiru": "Cumin(Jeera)", "jira": "Cumin(Jeera)", "zeera": "Cumin(Jeera)",
    "cummin": "Cumin(Jeera)", "cumon": "Cumin(Jeera)", "jeeru": "Cumin(Jeera)",
    # Castor
    "castor": "Castor Seed", "દિવેલા": "Castor Seed", "अरंडी": "Castor Seed",
    "divela": "Castor Seed", "diwela": "Castor Seed", "arandi": "Castor Seed",
    "erandi": "Castor Seed", "castorseed": "Castor Seed", "casterseed": "Castor Seed",
    "caster": "Castor Seed", "દિવેલ": "Castor Seed",
    # Bajra
    "bajra": "Bajra(Pearl Millet)", "બાજરી": "Bajra(Pearl Millet)", "बाजरा": "Bajra(Pearl Millet)",
    "bajri": "Bajra(Pearl Millet)", "bajro": "Bajra(Pearl Millet)", "millet": "Bajra(Pearl Millet)",
    "pearl millet": "Bajra(Pearl Millet)", "bajara": "Bajra(Pearl Millet)",
    # Mung
    "mung": "Green Gram (Moong)", "moong": "Green Gram (Moong)", "મગ": "Green Gram (Moong)",
    "moog": "Green Gram (Moong)", "mung bean": "Green Gram (Moong)", "mag": "Green Gram (Moong)",
    "moong dal": "Green Gram (Moong)", "mungbean": "Green Gram (Moong)",
    "green gram": "Green Gram (Moong)", "मूंग": "Green Gram (Moong)",
    # Sesame
    "sesame": "Sesamum(Sesame,Gingelly)", "til": "Sesamum(Sesame,Gingelly)",
    "તલ": "Sesamum(Sesame,Gingelly)", "तिल": "Sesamum(Sesame,Gingelly)",
    "tal": "Sesamum(Sesame,Gingelly)", "gingelly": "Sesamum(Sesame,Gingelly)",
    "seasame": "Sesamum(Sesame,Gingelly)", "sesme": "Sesamum(Sesame,Gingelly)",
    # Rice / Paddy
    "rice": "Paddy(Dhan)", "paddy": "Paddy(Dhan)", "ડાંગર": "Paddy(Dhan)", "धान": "Paddy(Dhan)",
    "dhan": "Paddy(Dhan)", "chawal": "Paddy(Dhan)", "ચોખા": "Paddy(Dhan)",
    "dangr": "Paddy(Dhan)", "dangar": "Paddy(Dhan)",
    # Onion
    "onion": "Onion", "ડુંગળી": "Onion", "प्याज": "Onion",
    "dungri": "Onion", "dungali": "Onion", "kanda": "Onion",
    # Potato
    "potato": "Potato", "બટાટા": "Potato", "आलू": "Potato",
    "batata": "Potato", "bataka": "Potato", "aloo": "Potato",
    # Soyabean
    "soyabean": "Soyabean", "soybean": "Soyabean", "સોયાબીન": "Soyabean",
    "soya": "Soyabean",
    # Chana
    "chana": "Bengal Gram(Gram)(Whole)", "channa": "Bengal Gram(Gram)(Whole)",
    "ચણા": "Bengal Gram(Gram)(Whole)", "chickpea": "Bengal Gram(Gram)(Whole)",
    "gram": "Bengal Gram(Gram)(Whole)",
    # Mustard
    "mustard": "Mustard", "rai": "Mustard", "રાઈ": "Mustard", "sarso": "Mustard",
    "સરસવ": "Mustard",
}

DISTRICT_MAP = {
    "rajkot": "Rajkot", "રાજકોટ": "Rajkot", "राजकोट": "Rajkot",
    "junagadh": "Junagadh", "જૂનાગઢ": "Junagadh", "जूनागढ़": "Junagadh",
    "gondal": "Rajkot", "ગોંડલ": "Rajkot",
    "ahmedabad": "Ahmedabad", "અમદાવાદ": "Ahmedabad", "अहमदाबाद": "Ahmedabad",
    "amreli": "Amreli", "અમરેલી": "Amreli",
    "bhavnagar": "Bhavnagar", "ભાવનગર": "Bhavnagar",
    "jamnagar": "Jamnagar", "જામનગર": "Jamnagar",
    "surendranagar": "Surendranagar", "સુરેન્દ્રનગર": "Surendranagar",
    "kodinar": "Gir Somnath", "કોડીનાર": "Gir Somnath",
    "morbi": "Morbi", "મોરબી": "Morbi",
    "kutch": "Kachchh", "કચ્છ": "Kachchh",
    "mehsana": "Mahesana", "મહેસાણા": "Mahesana",
    "banaskantha": "Banaskantha", "બનાસકાંઠા": "Banaskantha",
    "patan": "Patan", "પાટણ": "Patan",
    "anand": "Anand", "આણંદ": "Anand",
    "vadodara": "Vadodara", "વડોદરા": "Vadodara",
    "surat": "Surat", "સુરત": "Surat",
}

CROP_NAME_GU = {
    "Cotton": "કપાસ", "Groundnut": "મગફળી", "Wheat": "ઘઉં",
    "Cumin(Jeera)": "જીરું", "Castor Seed": "દિવેલા",
    "Bajra(Pearl Millet)": "બાજરી", "Green Gram (Moong)": "મગ",
    "Sesamum(Sesame,Gingelly)": "તલ", "Paddy(Dhan)": "ડાંગર",
}

CROP_NAME_HI = {
    "Cotton": "कपास", "Groundnut": "मूंगफली", "Wheat": "गेहूं",
    "Cumin(Jeera)": "जीरा", "Castor Seed": "अरंडी",
    "Bajra(Pearl Millet)": "बाजरा", "Green Gram (Moong)": "मूंग",
    "Sesamum(Sesame,Gingelly)": "तिल", "Paddy(Dhan)": "धान",
}


async def fetch_mandi_prices_api(commodity: str, state: str = "Gujarat") -> list[dict]:
    """Fetch live mandi prices from data.gov.in API."""
    api_key = settings.data_gov_api_key
    if not api_key:
        return await fetch_from_cache(commodity, state)

    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 50,
        "filters[state]": state,
        "filters[commodity]": commodity,
    }

    import subprocess, json as _json, urllib.parse

    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    def _fetch():
        result = subprocess.run(
            ["curl", "-s", "--max-time", "45", full_url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        return _json.loads(result.stdout)

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _fetch)

        records = data.get("records", [])
        prices = []
        for r in records:
            variety = r.get("variety", "")
            if variety and variety.lower() not in ("other", ""):
                variety_label = f" ({variety})"
            else:
                variety_label = ""
            prices.append({
                "market": r.get("market", "") + variety_label,
                "district": r.get("district", ""),
                "commodity": r.get("commodity", ""),
                "variety": variety,
                "min_price": r.get("min_price", "N/A"),
                "max_price": r.get("max_price", "N/A"),
                "modal_price": r.get("modal_price", "N/A"),
                "arrival_date": r.get("arrival_date", ""),
            })

        if prices:
            await cache_prices(prices)

        return prices
    except Exception as e:
        logger.error(f"data.gov.in API error: {e}")
        return await fetch_from_cache(commodity, state)


async def fetch_from_cache(commodity: str, state: str = "Gujarat") -> list[dict]:
    """Fallback: fetch from cached Supabase data."""
    try:
        result = (
            supabase.table("mandi_prices")
            .select("*")
            .eq("crop_name", commodity)
            .order("price_date", desc=True)
            .limit(20)
            .execute()
        )
        return [
            {
                "market": r["market_name"],
                "district": r["district"],
                "commodity": r["crop_name"],
                "min_price": str(r["min_price"]),
                "max_price": str(r["max_price"]),
                "modal_price": str(r["modal_price"]),
                "arrival_date": str(r["price_date"]),
            }
            for r in result.data
        ] if result.data else []
    except Exception:
        return []


async def cache_prices(prices: list[dict]):
    """Cache fetched prices into Supabase."""
    try:
        for p in prices[:20]:
            row = {
                "crop_name": p["commodity"],
                "crop_name_gu": CROP_NAME_GU.get(p["commodity"], ""),
                "district": p["district"],
                "market_name": p["market"],
                "min_price": float(p["min_price"]) if p["min_price"] != "N/A" else 0,
                "max_price": float(p["max_price"]) if p["max_price"] != "N/A" else 0,
                "modal_price": float(p["modal_price"]) if p["modal_price"] != "N/A" else 0,
                "price_date": p.get("arrival_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            supabase.table("mandi_prices").upsert(
                row, on_conflict="crop_name,district,market_name,price_date"
            ).execute()
    except Exception as e:
        logger.error(f"Cache prices error: {e}")


def _fuzzy_score(a: str, b: str) -> float:
    """Simple character-overlap similarity score between two strings."""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    matches = sum(1 for c in a if c in b)
    return (2.0 * matches) / (len(a) + len(b))


def resolve_crop(text: str) -> str | None:
    text_lower = text.lower().strip()

    # Exact / substring match first
    for key, value in CROP_NAME_MAP.items():
        if key in text_lower:
            return value

    # Fuzzy match on individual words
    words = text_lower.split()
    best_score = 0.0
    best_match = None
    for word in words:
        if len(word) < 3:
            continue
        for key, value in CROP_NAME_MAP.items():
            score = _fuzzy_score(word, key)
            if score > best_score and score >= 0.65:
                best_score = score
                best_match = value

    return best_match


def resolve_district(text: str) -> str | None:
    text_lower = text.lower().strip()

    for key, value in DISTRICT_MAP.items():
        if key in text_lower:
            return value

    words = text_lower.split()
    best_score = 0.0
    best_match = None
    for word in words:
        if len(word) < 3:
            continue
        for key, value in DISTRICT_MAP.items():
            score = _fuzzy_score(word, key)
            if score > best_score and score >= 0.65:
                best_score = score
                best_match = value

    return best_match


def format_price_response(prices: list[dict], crop: str, district: str | None, language: str = "gu") -> str:
    """Format mandi prices into a readable Telegram message."""
    if not prices:
        if language == "gu":
            return f"❌ {CROP_NAME_GU.get(crop, crop)} માટે કોઈ ભાવ મળ્યા નથી. કૃપા કરીને પાક/જિલ્લાનું નામ ચેક કરો."
        else:
            return f"❌ {CROP_NAME_HI.get(crop, crop)} के लिए कोई भाव नहीं मिले। कृपया फसल/जिले का नाम चेक करें।"

    if district:
        prices = [p for p in prices if p["district"].lower() == district.lower()] or prices

    crop_gu = CROP_NAME_GU.get(crop, crop)
    crop_hi = CROP_NAME_HI.get(crop, crop)

    if language == "gu":
        lines = [f"💰 *{crop_gu} — મંડી ભાવ*\n"]
        for p in prices[:10]:
            lines.append(
                f"📍 *{p['market']}* ({p['district']})\n"
                f"   ન્યૂનતમ: ₹{p['min_price']}/ક્વિ\n"
                f"   મહત્તમ: ₹{p['max_price']}/ક્વિ\n"
                f"   મોડલ: ₹{p['modal_price']}/ક્વિ\n"
                f"   તારીખ: {p['arrival_date']}\n"
            )
        lines.append("_સ્ત્રોત: data.gov.in / AGMARKNET_")
    else:
        lines = [f"💰 *{crop_hi} — मंडी भाव*\n"]
        for p in prices[:10]:
            lines.append(
                f"📍 *{p['market']}* ({p['district']})\n"
                f"   न्यूनतम: ₹{p['min_price']}/क्विं\n"
                f"   अधिकतम: ₹{p['max_price']}/क्विं\n"
                f"   मॉडल: ₹{p['modal_price']}/क्विं\n"
                f"   तारीख: {p['arrival_date']}\n"
            )
        lines.append("_स्रोत: data.gov.in / AGMARKNET_")

    return "\n".join(lines)
