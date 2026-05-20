from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import main_menu_keyboard, language_keyboard, crop_selection_keyboard
from app.database.queries import get_or_create_user, update_user_language, log_analytics
from app.services.mandi import (
    fetch_mandi_prices_api, resolve_crop, resolve_district, format_price_response,
)
from app.services.weather import get_weather

WELCOME_GU = """🌾 *ખેડૂતસાથી માં આપનું સ્વાગત છે!*

હું તમારો AI ખેતી સહાયક છું. હું તમને આ બાબતોમાં મદદ કરી શકું:

📸 *રોગ ઓળખો* — પાકનો ફોટો મોકલો, રોગ જાણો
💰 *ભાવ જુઓ* — મંડીના ભાવ ચેક કરો
🎤 *અવાજ* — ગુજરાતીમાં બોલીને પૂછો
🌤 *હવામાન* — તમારા વિસ્તારનું હવામાન

નીચેના બટન વાપરો અથવા સીધો ફોટો/અવાજ મોકલો!"""

WELCOME_HI = """🌾 *खेडूतसाथी में आपका स्वागत है!*

मैं आपका AI खेती सहायक हूं। मैं इन बातों में मदद कर सकता हूं:

📸 *रोग पहचानो* — फसल का फोटो भेजो, रोग जानो
💰 *भाव देखो* — मंडी के भाव चेक करो
🎤 *आवाज* — हिंदी में बोलकर पूछो
🌤 *मौसम* — अपने इलाके का मौसम

नीचे के बटन इस्तेमाल करो या सीधा फोटो/आवाज भेजो!"""

HELP_GU = """📋 *ખેડૂતસાથી — મદદ*

🔹 *રોગ ઓળખવા* — પાકનો ફોટો મોકલો
🔹 `/price કપાસ રાજકોટ` — મંડી ભાવ
🔹 `/weather રાજકોટ` — હવામાન
🔹 `/language` — ભાષા બદલો (ગુજરાતી/હિંદી)
🔹 `/feedback તમારો મેસેજ` — તમારો અભિપ્રાય

🎤 *અવાજ* — ગુજરાતીમાં વોઈસ મેસેજ મોકલો
💬 *ચેટ* — કોઈ પણ ખેતી વિષે સવાલ ટાઈપ કરો!"""

HELP_HI = """📋 *खेडूतसाथी — मदद*

🔹 *रोग पहचानो* — फसल का फोटो भेजो
🔹 `/price कपास राजकोट` — मंडी भाव
🔹 `/weather राजकोट` — मौसम
🔹 `/language` — भाषा बदलो (गुजराती/हिंदी)
🔹 `/feedback आपका मेसेज` — आपकी राय

🎤 *आवाज* — हिंदी में वॉइस मेसेज भेजो
💬 *चैट* — कोई भी खेती का सवाल टाइप करो!"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(
        telegram_id=user.id,
        first_name=user.first_name or "",
    )
    lang = db_user.get("language", "gu")
    welcome = WELCOME_GU if lang == "gu" else WELCOME_HI
    await update.message.reply_text(
        welcome, parse_mode="Markdown", reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")
    await update.message.reply_text(
        HELP_GU if lang == "gu" else HELP_HI, parse_mode="Markdown",
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ભાષા પસંદ કરો / भाषा चुनें:", reply_markup=language_keyboard(),
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("lang_", "")
    update_user_language(query.from_user.id, lang)
    msg = "✅ ભાષા ગુજરાતી સેટ થઈ!" if lang == "gu" else "✅ भाषा हिंदी सेट हो गई!"
    await query.edit_message_text(msg)


async def disease_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")
    if lang == "gu":
        msg = "🌱 પાક પસંદ કરો અથવા સીધો ફોટો મોકલો:"
    else:
        msg = "🌱 फसल चुनें या सीधा फोटो भेजें:"
    await update.message.reply_text(msg, reply_markup=crop_selection_keyboard())


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    if not args:
        if lang == "gu":
            msg = "💰 ભાવ જોવા માટે:\n`/price કપાસ રાજકોટ`\n\nઉદાહરણ:\n`/price groundnut junagadh`\n`/price જીરું`"
        else:
            msg = "💰 भाव देखने के लिए:\n`/price कपास राजकोट`\n\nउदाहरण:\n`/price groundnut junagadh`\n`/price जीरा`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    query_text = " ".join(args)
    crop = resolve_crop(query_text)
    district = resolve_district(query_text)

    if not crop:
        if lang == "gu":
            msg = "❌ પાક ઓળખાયો નથી. ઉદાહરણ: `/price કપાસ રાજકોટ`"
        else:
            msg = "❌ फसल पहचानी नहीं गई। उदाहरण: `/price कपास राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

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
        await wait_msg.delete()
        if lang == "gu":
            await update.message.reply_text("❌ ભાવ મેળવવામાં ભૂલ. કૃપા કરીને પછી પ્રયાસ કરો.")
        else:
            await update.message.reply_text("❌ भाव लाने में त्रुटि। कृपया बाद में प्रयास करें।")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    if not args:
        if lang == "gu":
            msg = "🌤 હવામાન જોવા:\n`/weather રાજકોટ`"
        else:
            msg = "🌤 मौसम देखने के लिए:\n`/weather राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    city = " ".join(args)

    if lang == "gu":
        wait_msg = await update.message.reply_text("🌤 હવામાન તપાસી રહ્યા છીએ... ⏳")
    else:
        wait_msg = await update.message.reply_text("🌤 मौसम जाँच रहे हैं... ⏳")

    try:
        response = await get_weather(city, lang)
        log_analytics(db_user["id"], "weather_query", {"city": city})
        await wait_msg.delete()
        try:
            await update.message.reply_text(response, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(response)
    except Exception as e:
        await wait_msg.delete()
        if lang == "gu":
            await update.message.reply_text("❌ હવામાન માહિતી મેળવવામાં ભૂલ.")
        else:
            await update.message.reply_text("❌ मौसम जानकारी लाने में त्रुटि।")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    if not args:
        if lang == "gu":
            msg = "📝 કૃપા કરીને તમારો અભિપ્રાય લખો:\n`/feedback તમારો મેસેજ`"
        else:
            msg = "📝 कृपया अपनी राय लिखें:\n`/feedback आपका मेसेज`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    feedback_text = " ".join(args)
    log_analytics(db_user["id"], "feedback", {"text": feedback_text})

    if lang == "gu":
        await update.message.reply_text("🙏 તમારો અભિપ્રાય માટે આભાર!")
    else:
        await update.message.reply_text("🙏 आपकी राय के लिए धन्यवाद!")
