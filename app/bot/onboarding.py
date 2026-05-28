from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.database.queries import get_or_create_user, update_user_profile
from app.bot.keyboards import main_menu_keyboard

DISTRICTS = [
    ("કોડીનાર", "Kodinar"), ("રાજકોટ", "Rajkot"), ("જૂનાગઢ", "Junagadh"),
    ("ગોંડલ", "Gondal"), ("અમરેલી", "Amreli"), ("ભાવનગર", "Bhavnagar"),
    ("અમદાવાદ", "Ahmedabad"), ("જામનગર", "Jamnagar"), ("મોરબી", "Morbi"),
    ("સુરેન્દ્રનગર", "Surendranagar"), ("મહેસાણા", "Mehsana"),
    ("આણંદ", "Anand"), ("વડોદરા", "Vadodara"), ("સુરત", "Surat"),
    ("કચ્છ", "Kutch"), ("બનાસકાંઠા", "Banaskantha"),
]

CROPS = [
    ("મગફળી", "groundnut"), ("કપાસ", "cotton"), ("ઘઉં", "wheat"),
    ("જીરું", "cumin"), ("દિવેલા", "castor"), ("બાજરી", "bajra"),
    ("મગ", "mung"), ("તલ", "sesame"), ("ડાંગર", "rice"),
    ("ડુંગળી", "onion"), ("બટાટા", "potato"), ("ચણા", "chana"),
]

LAND_SIZES = [
    ("1-5 વીઘા", "1-5"), ("5-15 વીઘા", "5-15"),
    ("15-30 વીઘા", "15-30"), ("30+ વીઘા", "30+"),
]


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_or_create_user(telegram_id=user.id, first_name=user.first_name or "")

    if db_user.get("onboarding_complete"):
        name = db_user.get("first_name", "")
        village = db_user.get("village") or db_user.get("district") or ""
        crops = db_user.get("crops") or []

        crop_str = ", ".join(crops[:3]) if crops else "—"
        msg = (
            f"🌾 *આવો {name}ભાઈ!* ફરી મળીને આનંદ થયો.\n\n"
            f"📍 {village} | 🌱 {crop_str}\n\n"
            f"નીચેના બટન વાપરો અથવા સીધો સવાલ પૂછો!"
        )
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=main_menu_keyboard(db_user),
        )
        return

    context.user_data["onboarding_step"] = "name"

    msg = (
        "🌾 *ખેડૂતસાથીમાં આપનું સ્વાગત છે!*\n\n"
        "ચાલો 30 સેકન્ડમાં સેટઅપ કરીએ.\n\n"
        "👤 *તમારું નામ શું છે?*\n"
        "(ઉદા. રમેશભાઈ)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle onboarding steps. Returns True if onboarding handled the message."""
    step = context.user_data.get("onboarding_step")
    if not step:
        return False

    user = update.effective_user
    text = update.message.text if update.message else ""

    if step == "name":
        name = text.strip()
        update_user_profile(user.id, first_name=name)
        context.user_data["onboarding_step"] = "district"

        buttons = []
        row = []
        for label, value in DISTRICTS:
            row.append(InlineKeyboardButton(label, callback_data=f"ob_dist_{value}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("🔍 અન્ય (Other)", callback_data="ob_dist_other")])

        await update.message.reply_text(
            f"✅ *{name}*, આવકાર છે!\n\n📍 *તમારું ગામ/જિલ્લો પસંદ કરો:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return True

    if step == "district_other":
        district = text.strip()
        update_user_profile(user.id, district=district, village=district)
        context.user_data["onboarding_step"] = "crops"
        await _ask_crops(update.message)
        return True

    return False


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle onboarding inline button callbacks. Returns True if handled."""
    query = update.callback_query
    data = query.data

    if not data.startswith("ob_"):
        return False

    await query.answer()
    user = query.from_user

    if data.startswith("ob_dist_"):
        district = data.replace("ob_dist_", "")

        if district == "other":
            context.user_data["onboarding_step"] = "district_other"
            await query.edit_message_text("📍 *તમારા ગામ/શહેરનું નામ લખો:*", parse_mode="Markdown")
            return True

        update_user_profile(user.id, district=district, village=district)
        context.user_data["onboarding_step"] = "crops"
        await query.edit_message_text(f"✅ *{district}* સેટ થયું!")
        await _send_crop_selection(query.message)
        return True

    if data.startswith("ob_crop_"):
        crop = data.replace("ob_crop_", "")

        if crop == "done":
            selected = context.user_data.get("selected_crops", [])
            if not selected:
                await query.answer("ઓછામાં ઓછો 1 પાક પસંદ કરો!", show_alert=True)
                return True

            update_user_profile(user.id, crops=selected)
            context.user_data["onboarding_step"] = "land"
            await query.edit_message_text(f"✅ પાક: {', '.join(selected)}")
            await _ask_land_size(query.message)
            return True

        selected = context.user_data.get("selected_crops", [])
        if crop in selected:
            selected.remove(crop)
        else:
            selected.append(crop)
        context.user_data["selected_crops"] = selected

        await query.edit_message_reply_markup(
            reply_markup=_crop_keyboard(selected)
        )
        return True

    if data.startswith("ob_land_"):
        land = data.replace("ob_land_", "")
        update_user_profile(user.id, land_size=land, onboarding_complete=True)

        context.user_data.pop("onboarding_step", None)
        context.user_data.pop("selected_crops", None)

        db_user = get_or_create_user(telegram_id=user.id)
        name = db_user.get("first_name", "")
        district = db_user.get("district", "")
        crops = db_user.get("crops", [])
        crop_str = ", ".join(crops[:3])

        msg = (
            f"🎉 *{name}, સેટઅપ પૂર્ણ!*\n\n"
            f"📍 જિલ્લો: {district}\n"
            f"🌱 પાક: {crop_str}\n"
            f"📐 જમીન: {land} વીઘા\n\n"
            f"હવે ફક્ત ફોટો મોકલો, સવાલ પૂછો, \n"
            f"અથવા નીચેના બટન વાપરો! 👇"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
        await query.message.reply_text(
            "👇 તમારું મેનુ તૈયાર છે:",
            reply_markup=main_menu_keyboard(db_user),
        )
        return True

    return False


def _crop_keyboard(selected: list) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for label, value in CROPS:
        check = "✅" if value in selected else "⬜"
        row.append(InlineKeyboardButton(f"{check} {label}", callback_data=f"ob_crop_{value}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("➡️ આગળ વધો", callback_data="ob_crop_done")])
    return InlineKeyboardMarkup(buttons)


async def _send_crop_selection(message):
    await message.reply_text(
        "🌱 *તમારા પાક પસંદ કરો* (એક કરતા વધુ પસંદ થઈ શકે):",
        parse_mode="Markdown",
        reply_markup=_crop_keyboard([]),
    )


async def _ask_crops(message):
    await _send_crop_selection(message)


async def _ask_land_size(message):
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"ob_land_{value}")]
        for label, value in LAND_SIZES
    ]
    await message.reply_text(
        "📐 *તમારી જમીન કેટલી છે?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
