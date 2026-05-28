from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import main_menu_keyboard, language_keyboard, crop_selection_keyboard
from app.bot.onboarding import start_onboarding
from app.database.queries import get_or_create_user, update_user_language, log_analytics
from app.services.mandi import (
    fetch_mandi_prices_api, resolve_crop, resolve_district, format_price_response,
)
from app.services.weather import get_weather

HELP_GU = """📋 *ખેડૂતસાથી — મદદ*

🔹 *રોગ ઓળખવા* — પાકનો ફોટો મોકલો
🔹 *ભાવ જોવા* — "mugfali bhav kodinar" ટાઈપ કરો
🔹 *હવામાન* — "kodinar ma varsad?" ટાઈપ કરો
🔹 `/language` — ભાષા બદલો
🔹 `/feedback` — અભિપ્રાય

🎤 ગુજરાતીમાં વોઈસ મેસેજ મોકલો!
💬 કોઈ પણ ખેતી વિષે સવાલ ટાઈપ કરો!

💰 *"મારા ભાવ"* — એક ટેપમાં તમારા પાકના ભાવ
🌤 *"મારું હવામાન"* — એક ટેપમાં તમારા ગામનું હવામાન"""

HELP_HI = """📋 *खेडूतसाथी — मदद*

🔹 *रोग पहचानो* — फसल का फोटो भेजो
🔹 *भाव देखो* — "mugfali bhav kodinar" टाइप करो
🔹 *मौसम* — "kodinar ma varsad?" टाइप करो
🔹 `/language` — भाषा बदलो
🔹 `/feedback` — राय

🎤 हिंदी में वॉइस मेसेज भेजो!
💬 कोई भी खेती का सवाल टाइप करो!

💰 *"मेरे भाव"* — एक टैप में आपकी फसल के भाव
🌤 *"मेरा मौसम"* — एक टैप में आपके गाँव का मौसम"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_onboarding(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_user = get_or_create_user(telegram_id=update.effective_user.id)
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
    db_user = get_or_create_user(telegram_id=update.effective_user.id)
    lang = db_user.get("language", "gu")
    if lang == "gu":
        msg = "🌱 પાક પસંદ કરો અથવા સીધો ફોટો મોકલો:"
    else:
        msg = "🌱 फसल चुनें या सीधा फोटो भेजें:"
    await update.message.reply_text(msg, reply_markup=crop_selection_keyboard())


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_user = get_or_create_user(telegram_id=update.effective_user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    if not args:
        if lang == "gu":
            msg = "💰 ભાવ જોવા:\n`/price કપાસ રાજકોટ`\n\nઅથવા ટાઈપ કરો:\n`mugfali bhav kodinar`"
        else:
            msg = "💰 भाव देखने के लिए:\n`/price कपास राजकोट`\n\nया टाइप करें:\n`mugfali bhav kodinar`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    query_text = " ".join(args)
    crop = resolve_crop(query_text)
    district = resolve_district(query_text) or db_user.get("district")

    if not crop:
        if lang == "gu":
            msg = "❌ પાક ઓળખાયો નથી. ઉદાહરણ: `mugfali bhav rajkot`"
        else:
            msg = "❌ फसल पहचानी नहीं गई। उदाहरण: `mugfali bhav rajkot`"
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
    except Exception:
        await wait_msg.delete()
        await update.message.reply_text("❌ ભાવ મેળવવામાં ભૂલ.")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_user = get_or_create_user(telegram_id=update.effective_user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    city = " ".join(args) if args else db_user.get("district")

    if not city:
        if lang == "gu":
            msg = "🌤 હવામાન જોવા:\n`/weather રાજકોટ`"
        else:
            msg = "🌤 मौसम देखने के लिए:\n`/weather राजकोट`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

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
    except Exception:
        await wait_msg.delete()
        await update.message.reply_text("❌ હવામાન માહિતી મેળવવામાં ભૂલ.")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_user = get_or_create_user(telegram_id=update.effective_user.id)
    lang = db_user.get("language", "gu")

    args = context.args
    if not args:
        if lang == "gu":
            msg = "📝 કૃપા કરીને તમારો અભિપ્રાય લખો:\n`/feedback તમારો મેસેજ`"
        else:
            msg = "📝 कृपया अपनी राय लिखें:\n`/feedback आपका मेसेज`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    log_analytics(db_user["id"], "feedback", {"text": " ".join(args)})

    if lang == "gu":
        await update.message.reply_text("🙏 તમારો અભિપ્રાય માટે આભાર!")
    else:
        await update.message.reply_text("🙏 आपकी राय के लिए धन्यवाद!")
