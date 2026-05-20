import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

CITY_MAP = {
    "rajkot": "Rajkot,IN", "રાજકોટ": "Rajkot,IN", "राजकोट": "Rajkot,IN",
    "junagadh": "Junagadh,IN", "જૂનાગઢ": "Junagadh,IN",
    "ahmedabad": "Ahmedabad,IN", "અમદાવાદ": "Ahmedabad,IN",
    "gondal": "Gondal,IN", "ગોંડલ": "Gondal,IN",
    "amreli": "Amreli,IN", "અમરેલી": "Amreli,IN",
    "bhavnagar": "Bhavnagar,IN", "ભાવનગર": "Bhavnagar,IN",
    "jamnagar": "Jamnagar,IN", "જામનગર": "Jamnagar,IN",
    "kodinar": "Kodinar,IN", "કોડીનાર": "Kodinar,IN",
    "morbi": "Morbi,IN", "મોરબી": "Morbi,IN",
    "surendranagar": "Surendranagar,IN", "સુરેન્દ્રનગર": "Surendranagar,IN",
    "kutch": "Bhuj,IN", "કચ્છ": "Bhuj,IN",
    "mehsana": "Mehsana,IN", "મહેસાણા": "Mehsana,IN",
    "anand": "Anand,IN", "આણંદ": "Anand,IN",
    "vadodara": "Vadodara,IN", "વડોદરા": "Vadodara,IN",
    "surat": "Surat,IN", "સુરત": "Surat,IN",
    "patan": "Patan,IN", "પાટણ": "Patan,IN",
    "porbandar": "Porbandar,IN", "પોરબંદર": "Porbandar,IN",
    "veraval": "Veraval,IN", "વેરાવળ": "Veraval,IN",
    "gandhinagar": "Gandhinagar,IN", "ગાંધીનગર": "Gandhinagar,IN",
    "bharuch": "Bharuch,IN", "ભરૂચ": "Bharuch,IN",
}

WEATHER_KEYWORDS = [
    "weather", "rain", "varsad", "વરસાદ", "હવામાન", "મોસમ",
    "barish", "baarish", "बारिश", "मौसम", "tapa", "તાપમાન",
    "temperature", "humidity", "bhej", "ભેજ", "garmi", "ગરમી",
    "thand", "ઠંડી", "paani", "પાણી", "hava", "હવા", "pavan", "પવન",
    "toofan", "તોફાન", "vavazodu", "વાવાઝોડું", "cloudy", "sunny",
    "forecast", "aavti kal", "આવતીકાલ", "aaje", "આજે",
]


def is_weather_query(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in WEATHER_KEYWORDS)


def extract_city_from_text(text: str) -> str | None:
    text_lower = text.lower()
    for key in CITY_MAP:
        if key in text_lower:
            return key
    return None


WEATHER_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧",
    "Drizzle": "🌦", "Thunderstorm": "⛈", "Snow": "❄️",
    "Mist": "🌫", "Haze": "🌫", "Fog": "🌫",
    "Dust": "🌪", "Smoke": "🌫",
}


def resolve_city(text: str) -> str | None:
    text_lower = text.lower().strip()
    for key, value in CITY_MAP.items():
        if key in text_lower:
            return value
    return f"{text.strip()},IN"


async def get_weather(city_query: str, language: str = "gu") -> str:
    api_key = settings.weather_api_key
    if not api_key:
        if language == "gu":
            return "❌ હવામાન સેવા હાલમાં ઉપલબ્ધ નથી. કૃપા કરીને પછી પ્રયાસ કરો."
        return "❌ मौसम सेवा अभी उपलब्ध नहीं है। कृपया बाद में प्रयास करें।"

    city = resolve_city(city_query)

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        weather_main = data["weather"][0]["main"]
        weather_desc = data["weather"][0]["description"]
        city_name = data["name"]
        icon = WEATHER_ICONS.get(weather_main, "🌤")

        if language == "gu":
            farming_advice = _get_farming_advice_gu(temp, humidity, weather_main)
            return (
                f"{icon} *{city_name} — હવામાન*\n\n"
                f"🌡 તાપમાન: *{temp}°C* (અનુભવ: {feels_like}°C)\n"
                f"💧 ભેજ: {humidity}%\n"
                f"💨 પવન: {wind_speed} m/s\n"
                f"🌤 સ્થિતિ: {weather_desc}\n\n"
                f"🌾 *ખેતી સલાહ:*\n{farming_advice}"
            )
        else:
            farming_advice = _get_farming_advice_hi(temp, humidity, weather_main)
            return (
                f"{icon} *{city_name} — मौसम*\n\n"
                f"🌡 तापमान: *{temp}°C* (महसूस: {feels_like}°C)\n"
                f"💧 नमी: {humidity}%\n"
                f"💨 हवा: {wind_speed} m/s\n"
                f"🌤 स्थिति: {weather_desc}\n\n"
                f"🌾 *खेती सलाह:*\n{farming_advice}"
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            if language == "gu":
                return f"❌ '{city_query}' શહેર મળ્યું નથી. કૃપા કરીને સાચું નામ લખો."
            return f"❌ '{city_query}' शहर नहीं मिला। कृपया सही नाम लिखें।"
        raise
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        if language == "gu":
            return "❌ હવામાન માહિતી મેળવવામાં ભૂલ. કૃપા કરીને પછી પ્રયાસ કરો."
        return "❌ मौसम जानकारी लाने में त्रुटि। कृपया बाद में प्रयास करें।"


def _get_farming_advice_gu(temp: float, humidity: float, weather: str) -> str:
    advice = []
    if weather in ("Rain", "Thunderstorm", "Drizzle"):
        advice.append("• વરસાદ પછી દવા છાંટવાનું ટાળો — દવા ધોવાઈ જશે")
        advice.append("• ખેતરમાં પાણીનો ભરાવો ન થાય તેનું ધ્યાન રાખો")
        advice.append("• ફૂગનાશક છંટકાવ માટે વરસાદ અટક્યા પછી 24 કલાક રાહ જુઓ")
    if humidity > 80:
        advice.append("• ભેજ વધારે છે — ફૂગ રોગનું જોખમ, પાકનું નિરીક્ષણ કરો")
    if temp > 40:
        advice.append("• ગરમી વધારે છે — સવારે/સાંજે સિંચાઈ કરો, બપોરે ટાળો")
    if temp < 10:
        advice.append("• ઠંડી છે — પાકને હિમથી બચાવો, સિંચાઈ આપો")
    if weather == "Clear" and humidity < 50:
        advice.append("• ચોખ્ખું વાતાવરણ — દવા છાંટવા માટે યોગ્ય સમય")
    if not advice:
        advice.append("• સામાન્ય વાતાવરણ — નિયમિત ખેતી કાર્ય ચાલુ રાખો")
    return "\n".join(advice)


def _get_farming_advice_hi(temp: float, humidity: float, weather: str) -> str:
    advice = []
    if weather in ("Rain", "Thunderstorm", "Drizzle"):
        advice.append("• बारिश के बाद दवा छिड़काव न करें — दवा बह जाएगी")
        advice.append("• खेत में पानी का जमाव न होने दें")
        advice.append("• फफूंदनाशक छिड़काव के लिए बारिश रुकने के 24 घंटे बाद करें")
    if humidity > 80:
        advice.append("• नमी ज़्यादा है — फफूंद रोग का खतरा, फसल की जाँच करें")
    if temp > 40:
        advice.append("• गर्मी ज़्यादा है — सुबह/शाम सिंचाई करें, दोपहर में न करें")
    if temp < 10:
        advice.append("• ठंड है — फसल को पाले से बचाएं, सिंचाई दें")
    if weather == "Clear" and humidity < 50:
        advice.append("• साफ़ मौसम — दवा छिड़काव के लिए अच्छा समय")
    if not advice:
        advice.append("• सामान्य मौसम — नियमित खेती कार्य जारी रखें")
    return "\n".join(advice)


async def get_forecast(city_query: str) -> list[dict] | None:
    """Get 5-day / 3-hour forecast from OpenWeatherMap."""
    api_key = settings.weather_api_key
    if not api_key:
        return None

    city = resolve_city(city_query)

    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {"q": city, "appid": api_key, "units": "metric", "cnt": 16}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        forecasts = []
        for item in data.get("list", []):
            forecasts.append({
                "datetime": item.get("dt_txt", ""),
                "temp": item["main"]["temp"],
                "humidity": item["main"]["humidity"],
                "weather": item["weather"][0]["main"],
                "description": item["weather"][0]["description"],
                "wind_speed": item["wind"]["speed"],
                "rain_mm": item.get("rain", {}).get("3h", 0),
            })

        return forecasts
    except Exception as e:
        logger.error(f"Forecast API error: {e}")
        return None


async def smart_weather_answer(question: str, language: str = "gu") -> str:
    """Fetch real weather + forecast data and let Gemini answer the question."""
    from app.services.gemini import generate

    city_key = extract_city_from_text(question)
    if not city_key:
        city_key = "rajkot"

    city = resolve_city(city_key)
    api_key = settings.weather_api_key
    if not api_key:
        if language == "gu":
            return "❌ હવામાન સેવા હાલમાં ઉપલબ્ધ નથી."
        return "❌ मौसम सेवा अभी उपलब्ध नहीं है।"

    current_data = None
    forecast_data = None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric"},
            )
            if resp.status_code == 200:
                current_data = resp.json()
    except Exception:
        pass

    forecast_data = await get_forecast(city_key)

    weather_context = ""
    if current_data:
        weather_context += f"""Current weather in {current_data.get('name', city_key)}:
- Temperature: {current_data['main']['temp']}°C (feels like {current_data['main']['feels_like']}°C)
- Humidity: {current_data['main']['humidity']}%
- Wind: {current_data['wind']['speed']} m/s
- Condition: {current_data['weather'][0]['description']}
- Clouds: {current_data.get('clouds', {}).get('all', 0)}%
"""

    if forecast_data:
        weather_context += "\nUpcoming forecast (next 48 hours):\n"
        for f in forecast_data[:16]:
            rain_info = f" | Rain: {f['rain_mm']}mm" if f['rain_mm'] > 0 else ""
            weather_context += f"  {f['datetime']} — {f['temp']}°C, {f['description']}, humidity {f['humidity']}%, wind {f['wind_speed']}m/s{rain_info}\n"

    lang_name = "Gujarati" if language == "gu" else "Hindi"

    prompt = f"""You are KhedutSathi, an AI farming assistant for Gujarat farmers.

The farmer asked a weather-related question. Use the REAL weather data below to answer accurately.

**Real Weather Data:**
{weather_context}

**Farmer's question:** {question}

**Instructions:**
- Answer in {lang_name} language
- Use the actual data above — do NOT make up temperatures or predictions
- If farmer asks about rain, check the forecast data for rain probability
- Give farming-relevant advice based on the actual conditions
- Be specific with numbers from the data
- Keep response concise (150-250 words)"""

    return generate(prompt, temperature=0.3, max_tokens=2000)

