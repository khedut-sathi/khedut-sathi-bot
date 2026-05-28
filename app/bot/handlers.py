import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.database.queries import get_or_create_user, is_onboarding_complete, log_analytics
from app.services.disease_detection import diagnose_disease
from app.services.ai_chat import farming_chat
from app.services.voice import transcribe_voice
from app.services.weather import is_weather_query, smart_weather_answer, get_weather
from app.services.mandi import resolve_crop, resolve_district, fetch_mandi_prices_api, format_price_response
from app.bot.onboarding import handle_onboarding
from app.bot.context import get_crop, set_crop, set_topic, set_last_disease, get_context_summary
from app.bot.keyboards import main_menu_keyboard
from app.utils.image import compress_image

logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4096

PRICE_KEYWORDS = [
    "bhav", "ભાવ", "भाव", "price", "rate", "rates", "bazaar", "bazar",
    "mandi", "મંડી", "मंडी", "apmc", "market", "kimat", "કિંમત", "कीमत",
    "mol", "મોલ", "दाम", "daam", "dam",
]

DISEASE_KEYWORDS = [
    "rog", "રોગ", "रोग", "disease", "bimari", "બીમારી", "बीमारी",
    "kido", "કીડો", "कीड़ा", "pest", "insect", "jivat", "જીવાત",
    "spot", "yellow", "sukay", "સુકાય", "wilt", "rot", "fungus",
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


async def safe_reply(message, text: str):
    chunks = [text[i:i + MAX_TELEGRAM_MSG] for i in range(0, len(text), MAX_TELEGRAM_MSG)]
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        crop_hint = context.user_data.get("selected_crop") or get_crop(context, db_user)

        diagnosis = await diagnose_disease(
            image_bytes=compressed, crop_hint=crop_hint, language=lang,
        )

        log_analytics(db_user["id"], "image_upload", {"crop_hint": crop_hint})
        set_topic(context, "disease")
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
            await update.message.reply_text("❌ રોગ ઓળખવામાં ભૂલ થઈ. કૃપા કરીને સ્પષ્ટ ફોટો મોકલો.")
        else:
            await update.message.reply_text("❌ रोग पहचानने में त्रुटि। कृपया स्पष्ट फोटो भेजें।")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                await update.message.reply_text("❌ અવાજ સમજાયો નથી. કૃપા કરીને ફરી બોલો.")
            else:
                await update.message.reply_text("❌ आवाज समझ नहीं आई। कृपया फिर बोलें।")
            return

        log_analytics(db_user["id"], "voice_message", {"transcription": transcription[:200]})

        farmer_context = get_context_summary(context, db_user)
        response = await farming_chat(
            question=transcription, language=lang, farmer_context=farmer_context,
        )

        await wait_msg.delete()
        await safe_reply(update.message, f"🎤 _{transcription}_\n\n{response}")

    except Exception as e:
        logger.error(f"Voice error: {e}", exc_info=True)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        if lang == "gu":
            await update.message.reply_text("❌ અવાજ પ્રક્રિયામાં ભૂલ.")
        else:
            await update.message.reply_text("❌ आवाज प्रक्रिया में त्रुटि।")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")
    text = update.message.text

    # Handle onboarding steps
    if await handle_onboarding(update, context):
        return

    # === PERSONALIZED MENU BUTTONS ===

    # "મારા ભાવ" — one tap, shows farmer's crop prices in their location
    if text == "💰 મારા ભાવ":
        crops = db_user.get("crops", [])
        district = db_user.get("district")

        if not crops:
            await update.message.reply_text("🌱 પહેલા `/start` થી પાક સેટ કરો.", parse_mode="Markdown")
            return

        if lang == "gu":
            wait_msg = await update.message.reply_text("💰 તમારા ભાવ શોધી રહ્યા છીએ... ⏳")
        else:
            wait_msg = await update.message.reply_text("💰 आपके भाव खोज रहे हैं... ⏳")

        try:
            all_responses = []
            for crop_name in crops[:3]:
                api_crop = resolve_crop(crop_name)
                if api_crop:
                    prices = await fetch_mandi_prices_api(api_crop)
                    resp = format_price_response(prices, api_crop, district, lang)
                    all_responses.append(resp)

            log_analytics(db_user["id"], "my_prices", {"crops": crops, "district": district})
            await wait_msg.delete()
            await safe_reply(update.message, "\n\n".join(all_responses) if all_responses else "❌ ભાવ મળ્યા નથી.")
        except Exception as e:
            logger.error(f"My prices error: {e}", exc_info=True)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("❌ ભાવ મેળવવામાં ભૂલ.")
        return

    # "મારું હવામાન" — one tap weather for farmer's location
    if text == "🌤 મારું હવામાન":
        district = db_user.get("district") or db_user.get("village")
        if not district:
            await update.message.reply_text("📍 પહેલા `/start` થી લોકેશન સેટ કરો.", parse_mode="Markdown")
            return

        if lang == "gu":
            wait_msg = await update.message.reply_text("🌤 હવામાન તપાસી રહ્યા છીએ... ⏳")
        else:
            wait_msg = await update.message.reply_text("🌤 मौसम जाँच रहे हैं... ⏳")

        try:
            response = await get_weather(district, lang)
            log_analytics(db_user["id"], "my_weather", {"district": district})
            await wait_msg.delete()
            try:
                await update.message.reply_text(response, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(response)
        except Exception:
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("❌ હવામાન માહિતી મેળવવામાં ભૂલ.")
        return

    # "મારો પાક" — show farmer's crop info
    if text == "🌱 મારો પાક":
        crops = db_user.get("crops", [])
        district = db_user.get("district", "")
        name = db_user.get("first_name", "")

        if crops:
            crop_str = ", ".join(crops)
            msg = (
                f"🌱 *{name}ના પાક:* {crop_str}\n"
                f"📍 *જિલ્લો:* {district}\n\n"
                f"પાક બદલવા `/start` મોકલો.\n"
                f"પાકનો ફોટો મોકલીને રોગ ઓળખો!"
            )
        else:
            msg = "🌱 પાક સેટ નથી. `/start` મોકલો."

        try:
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(msg)
        return

    # "મિત્રને જોડો" — share/invite
    if text == "📞 મિત્રને જોડો":
        name = db_user.get("first_name", "")
        village = db_user.get("district", "")

        invite_msg = (
            f"🌾 *ખેડૂતસાથી — AI ખેતી સહાયક*\n\n"
            f"📸 પાકનો ફોટો મોકલો, રોગ ઓળખો\n"
            f"💰 મંડી ભાવ જુઓ — એક ટેપમાં\n"
            f"🌤 હવામાન જાણો\n"
            f"🎤 ગુજરાતીમાં બોલીને પૂછો\n\n"
            f"👉 *t.me/KhedutSathiBot*\n\n"
            f"_{name} ({village}) એ તમને જોડ્યા_"
        )
        log_analytics(db_user["id"], "invite_shared")
        try:
            await update.message.reply_text(invite_msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(invite_msg)
        if lang == "gu":
            await update.message.reply_text("👆 આ મેસેજ WhatsApp ગ્રુપમાં ફોરવર્ડ કરો!")
        else:
            await update.message.reply_text("👆 यह मेसेज WhatsApp ग्रुप में फॉरवर्ड करें!")
        return

    # Old menu buttons (for users who haven't onboarded)
    if text == "📸 રોગ ઓળખો":
        from app.bot.commands import disease_command
        await disease_command(update, context)
        return

    if text in ("💰 ભાવ જુઓ",):
        if lang == "gu":
            msg = "💰 ભાવ જોવા:\nઉદા. `mugfali bhav kodinar`\nઅથવા `/price કપાસ રાજકોટ`"
        else:
            msg = "💰 भाव देखने के लिए:\nउदा. `mugfali bhav kodinar`\nया `/price कपास राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "🌤 હવામાન":
        if lang == "gu":
            msg = "🌤 હવામાન:\n`/weather રાજકોટ`"
        else:
            msg = "🌤 मौसम:\n`/weather राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "❓ મદદ":
        from app.bot.commands import help_command
        await help_command(update, context)
        return

    # === NATURAL LANGUAGE DETECTION ===

    # Detect price queries
    if is_price_query(text):
        crop = resolve_crop(text)
        district = resolve_district(text) or db_user.get("district")

        set_crop(context, crop)
        set_topic(context, "price")

        if lang == "gu":
            wait_msg = await update.message.reply_text("💰 ભાવ શોધી રહ્યા છીએ... ⏳")
        else:
            wait_msg = await update.message.reply_text("💰 भाव खोज रहे हैं... ⏳")

        try:
            prices = await fetch_mandi_prices_api(crop)
            response = format_price_response(prices, crop, district, lang)
            log_analytics(db_user["id"], "price_query", {"crop": crop, "district": district})
            await wait_msg.delete()
            try:
                await update.message.reply_text(response, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Price error: {e}", exc_info=True)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("❌ ભાવ મેળવવામાં ભૂલ.")
        return

    # Detect disease text queries
    if is_disease_query(text):
        crop = resolve_crop(text)
        set_crop(context, crop)
        context.user_data["selected_crop"] = crop

        if lang == "gu":
            msg = f"🌱 *{crop}* માં રોગ/જીવાત? પાકનો ફોટો મોકલો — હું ઓળખી આપીશ!"
        else:
            msg = f"🌱 *{crop}* में रोग/कीट? फसल का फोटो भेजें — मैं पहचान दूंगा!"
        try:
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(msg)
        return

    # Detect weather questions
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
            logger.error(f"Weather error: {e}", exc_info=True)
            try:
                await wait_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("❌ હવામાન માહિતી મેળવવામાં ભૂલ.")
        return

    # === AI CHAT (with context) ===
    if lang == "gu":
        wait_msg = await update.message.reply_text("🤖 જવાબ તૈયાર કરી રહ્યા છીએ... ⏳")
    else:
        wait_msg = await update.message.reply_text("🤖 जवाब तैयार कर रहे हैं... ⏳")

    try:
        # Update session crop if farmer mentions one
        detected_crop = resolve_crop(text)
        if detected_crop:
            set_crop(context, detected_crop)

        farmer_context = get_context_summary(context, db_user)
        response = await farming_chat(
            question=text, language=lang, farmer_context=farmer_context,
        )
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
            await update.message.reply_text("❌ જવાબ આપવામાં ભૂલ થઈ.")
        else:
            await update.message.reply_text("❌ जवाब देने में त्रुटि हुई।")


async def crop_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    crop = query.data.replace("crop_", "")
    context.user_data["selected_crop"] = crop
    set_crop(context, crop)

    db_user = get_or_create_user(telegram_id=query.from_user.id)
    lang = db_user.get("language", "gu")

    crop_names = {
        "cotton": "કપાસ", "groundnut": "મગફળી", "wheat": "ઘઉં",
        "cumin": "જીરું", "castor": "દિવેલા", "bajra": "બાજરી",
        "mung": "મગ", "sesame": "તલ", "rice": "ડાંગર",
    }

    crop_name = crop_names.get(crop, crop)

    if lang == "gu":
        msg = f"✅ *{crop_name}* પસંદ થયું.\n\n📸 હવે પાકનો ફોટો મોકલો!"
    else:
        msg = f"✅ *{crop_name}* चुना गया.\n\n📸 अब फसल का फोटो भेजें!"

    await query.edit_message_text(msg, parse_mode="Markdown")
