import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.database.queries import get_or_create_user, log_analytics
from app.services.disease_detection import diagnose_disease
from app.services.ai_chat import farming_chat
from app.services.voice import transcribe_voice
from app.services.weather import is_weather_query, smart_weather_answer
from app.services.mandi import resolve_crop, resolve_district, fetch_mandi_prices_api, format_price_response
from app.utils.image import compress_image

PRICE_KEYWORDS = [
    "bhav", "ભાવ", "भाव", "price", "rate", "rates", "bazaar", "bazar",
    "mandi", "મંડી", "मंडी", "apmc", "market", "kimat", "કિંમત", "कीमत",
    "mol", "મોલ", "दाम", "daam", "dam",
]

DISEASE_KEYWORDS = [
    "rog", "રોગ", "रोग", "disease", "bimari", "બીમારી", "बीमारी",
    "kido", "કીડો", "कीड़ा", "pest", "insect", "jivat", "જીવાત",
    "paan", "પાન", "patti", "पत्ती", "leaf", "spot", "yellow",
    "sukay", "સુકાય", "sukhay", "wilt", "rot", "fungus",
    "dawaa", "દવા", "दवा", "spray", "medicine",
]


def is_price_query(text: str) -> bool:
    text_lower = text.lower()
    has_price_kw = any(kw in text_lower for kw in PRICE_KEYWORDS)
    has_crop = resolve_crop(text) is not None
    return has_price_kw and has_crop


def is_disease_query(text: str) -> bool:
    text_lower = text.lower()
    has_disease_kw = any(kw in text_lower for kw in DISEASE_KEYWORDS)
    has_crop = resolve_crop(text) is not None
    return has_disease_kw and has_crop

logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4096


async def safe_reply(message, text: str):
    """Send a reply, handling Markdown errors and long messages."""
    chunks = [text[i:i + MAX_TELEGRAM_MSG] for i in range(0, len(text), MAX_TELEGRAM_MSG)]
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle crop disease photo — full RAG pipeline."""
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    if lang == "gu":
        wait_msg = await update.message.reply_text("📸 ફોટો મળ્યો! રોગ ઓળખી રહ્યા છીએ... ⏳")
    else:
        wait_msg = await update.message.reply_text("📸 फोटो मिला! रोग पहचान रहे हैं... ⏳")

    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_bytes = await file.download_as_bytearray()

        compressed = compress_image(bytes(image_bytes))

        crop_hint = context.user_data.get("selected_crop")

        diagnosis = await diagnose_disease(
            image_bytes=compressed,
            crop_hint=crop_hint,
            language=lang,
        )

        log_analytics(db_user["id"], "image_upload", {
            "crop_hint": crop_hint,
            "has_diagnosis": True,
        })

        context.user_data.pop("selected_crop", None)

        await wait_msg.delete()
        await safe_reply(update.message, diagnosis)

    except Exception as e:
        logger.error(f"Disease detection error: {e}", exc_info=True)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        if lang == "gu":
            msg = "❌ રોગ ઓળખવામાં ભૂલ થઈ. કૃપા કરીને ફરી પ્રયાસ કરો અથવા સ્પષ્ટ ફોટો મોકલો."
        else:
            msg = "❌ रोग पहचानने में त्रुटि हुई। कृपया फिर से प्रयास करें या स्पष्ट फोटो भेजें।"
        await update.message.reply_text(msg)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice message — transcribe with Whisper, then process as text."""
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    if lang == "gu":
        wait_msg = await update.message.reply_text("🎤 અવાજ સાંભળી રહ્યા છીએ... ⏳")
    else:
        wait_msg = await update.message.reply_text("🎤 आवाज सुन रहे हैं... ⏳")

    try:
        voice = update.message.voice or update.message.audio
        file = await voice.get_file()
        audio_bytes = await file.download_as_bytearray()

        transcription = await transcribe_voice(bytes(audio_bytes))

        if not transcription:
            await wait_msg.delete()
            if lang == "gu":
                msg = "❌ અવાજ સમજાયો નથી. કૃપા કરીને ફરી બોલો અથવા ટાઈપ કરો."
            else:
                msg = "❌ आवाज समझ नहीं आई। कृपया फिर बोलें या टाइप करें।"
            await update.message.reply_text(msg)
            return

        log_analytics(db_user["id"], "voice_message", {"transcription": transcription[:200]})

        if lang == "gu":
            await wait_msg.edit_text(f"🎤 તમે બોલ્યા: _{transcription}_\n\n🤖 જવાબ તૈયાર કરી રહ્યા છીએ...", parse_mode=ParseMode.MARKDOWN)
        else:
            await wait_msg.edit_text(f"🎤 आपने बोला: _{transcription}_\n\n🤖 जवाब तैयार कर रहे हैं...", parse_mode=ParseMode.MARKDOWN)

        response = await farming_chat(question=transcription, language=lang)

        await wait_msg.delete()
        await safe_reply(update.message, f"🎤 _{transcription}_\n\n{response}")

    except Exception as e:
        logger.error(f"Voice handling error: {e}", exc_info=True)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        if lang == "gu":
            msg = "❌ અવાજ પ્રક્રિયામાં ભૂલ. કૃપા કરીને ફરી પ્રયાસ કરો."
        else:
            msg = "❌ आवाज प्रक्रिया में त्रुटि। कृपया फिर से प्रयास करें।"
        await update.message.reply_text(msg)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-form text — route menu buttons or AI farming chat."""
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    text = update.message.text

    if text == "📸 રોગ ઓળખો":
        from app.bot.commands import disease_command
        await disease_command(update, context)
        return

    if text == "💰 ભાવ જુઓ":
        if lang == "gu":
            msg = "💰 ભાવ જોવા:\n`/price કપાસ રાજકોટ`\n\nઅથવા ફક્ત પાક લખો:\n`/price જીરું`"
        else:
            msg = "💰 भाव देखने के लिए:\n`/price कपास राजकोट`\n\nया सिर्फ फसल लिखें:\n`/price जीरा`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "🌤 હવામાન":
        if lang == "gu":
            msg = "🌤 હવામાન જોવા:\n`/weather રાજકોટ`"
        else:
            msg = "🌤 मौसम देखने के लिए:\n`/weather राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "❓ મદદ":
        from app.bot.commands import help_command
        await help_command(update, context)
        return

    # Detect price queries: "mugfali bhav kodinar", "કપાસ ભાવ રાજકોટ", "cotton rate"
    if is_price_query(text):
        crop = resolve_crop(text)
        district = resolve_district(text)

        if lang == "gu":
            wait_msg = await update.message.reply_text("💰 ભાવ શોધી રહ્યા છીએ... ⏳")
        else:
            wait_msg = await update.message.reply_text("💰 भाव खोज रहे हैं... ⏳")

        try:
            prices = await fetch_mandi_prices_api(crop)
            response = format_price_response(prices, crop, district, lang)
            log_analytics(db_user["id"], "price_query", {"crop": crop, "district": district, "query": text[:200]})
            await wait_msg.delete()
            try:
                await update.message.reply_text(response, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Price query error: {e}", exc_info=True)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            if lang == "gu":
                await update.message.reply_text("❌ ભાવ મેળવવામાં ભૂલ. કૃપા કરીને પછી પ્રયાસ કરો.")
            else:
                await update.message.reply_text("❌ भाव लाने में त्रुटि। कृपया बाद में प्रयास करें।")
        return

    # Detect disease queries: "kapas ma rog aavyo", "કપાસમાં કીડો"
    if is_disease_query(text):
        crop = resolve_crop(text)
        context.user_data["selected_crop"] = crop

        from app.bot.commands import disease_command
        if lang == "gu":
            msg = f"🌱 *{crop}* માં રોગ/જીવાત વિશે જાણવા પાકનો ફોટો મોકલો — હું ઓળખી આપીશ!"
        else:
            msg = f"🌱 *{crop}* में रोग/कीट के बारे में जानने के लिए फसल का फोटो भेजें — मैं पहचान दूंगा!"

        try:
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(msg)
        return

    # Detect weather questions and use real data
    if is_weather_query(text):
        if lang == "gu":
            wait_msg = await update.message.reply_text("🌤 હવામાન તપાસી રહ્યા છીએ... ⏳")
        else:
            wait_msg = await update.message.reply_text("🌤 मौसम जाँच रहे हैं... ⏳")
        try:
            response = await smart_weather_answer(question=text, language=lang)
            log_analytics(db_user["id"], "weather_query", {"question": text[:200]})
            await wait_msg.delete()
            await safe_reply(update.message, response)
        except Exception as e:
            logger.error(f"Weather chat error: {e}", exc_info=True)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            if lang == "gu":
                await update.message.reply_text("❌ હવામાન માહિતી મેળવવામાં ભૂલ.")
            else:
                await update.message.reply_text("❌ मौसम जानकारी लाने में त्रुटि।")
        return

    if lang == "gu":
        wait_msg = await update.message.reply_text("🤖 જવાબ તૈયાર કરી રહ્યા છીએ... ⏳")
    else:
        wait_msg = await update.message.reply_text("🤖 जवाब तैयार कर रहे हैं... ⏳")

    try:
        response = await farming_chat(question=text, language=lang)
        log_analytics(db_user["id"], "text_chat", {"question": text[:200]})
        await wait_msg.delete()
        await safe_reply(update.message, response)

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        if lang == "gu":
            msg = "❌ જવાબ આપવામાં ભૂલ થઈ. કૃપા કરીને ફરી પ્રયાસ કરો."
        else:
            msg = "❌ जवाब देने में त्रुटि हुई। कृपया फिर से प्रयास करें।"
        await update.message.reply_text(msg)


async def crop_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle crop selection from inline keyboard."""
    query = update.callback_query
    await query.answer()

    crop = query.data.replace("crop_", "")
    context.user_data["selected_crop"] = crop

    db_user = get_or_create_user(telegram_id=query.from_user.id)
    lang = db_user.get("language", "gu")

    crop_names_gu = {
        "cotton": "કપાસ", "groundnut": "મગફળી", "wheat": "ઘઉં",
        "cumin": "જીરું", "castor": "દિવેલા", "bajra": "બાજરી",
        "mung": "મગ", "sesame": "તલ", "rice": "ડાંગર",
    }
    crop_names_hi = {
        "cotton": "कपास", "groundnut": "मूंगफली", "wheat": "गेहूं",
        "cumin": "जीरा", "castor": "अरंडी", "bajra": "बाजरा",
        "mung": "मूंग", "sesame": "तिल", "rice": "धान",
    }

    crop_name = crop_names_gu.get(crop, crop) if lang == "gu" else crop_names_hi.get(crop, crop)

    if lang == "gu":
        msg = f"✅ *{crop_name}* પસંદ થયું.\n\n📸 હવે પાકનો ફોટો મોકલો — હું રોગ ઓળખીશ!"
    else:
        msg = f"✅ *{crop_name}* चुना गया.\n\n📸 अब फसल का फोटो भेजें — मैं रोग पहचानूंगा!"

    await query.edit_message_text(msg, parse_mode="Markdown")
