from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from config import ADMIN_ID
import database as db

user_states = {}

def get_main_keyboard():
    """Main Dashboard Keyboard with Bulk Sessions Import Option"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ADD ACC (OTP)", callback_data="btn_add_acc"),
            InlineKeyboardButton("📂 SESSIONS (.txt/Text)", callback_data="btn_import_sessions")
        ],
        [
            InlineKeyboardButton("⚡ BULK OTP LOGIN", callback_data="btn_bulk_login"),
            InlineKeyboardButton("🎯 USER ID", callback_data="btn_user_id")
        ],
        [
            InlineKeyboardButton("📝 SET REVIEWS", callback_data="btn_set_reviews"),
            InlineKeyboardButton("📊 STATS", callback_data="btn_stats")
        ],
        [
            InlineKeyboardButton("🚀 SEND REVIEWS", callback_data="btn_send_reviews")
        ]
    ])

def register_admin_handlers(app: Client):

    # ================= /start COMMAND (ADMIN ONLY) =================
    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            await message.reply_text("⛔ **Unauthorized Access!** Sirf authorized admin is bot ko use kar sakta hai.")
            return

        user_states.pop(message.from_user.id, None)
        greeting_text = (
            "👋 **Namaste Boss! Welcome to Review Automation Bot.**\n\n"
            "☁️ **Database:** `Supabase Cloud Connected`\n\n"
            "Neeche diye gaye buttons ka use karke apne accounts, sessions, target ID aur reviews manage karein:"
        )
        await message.reply_text(greeting_text, reply_markup=get_main_keyboard())

    # ================= STATS BUTTON =================
    @app.on_callback_query(filters.regex("^btn_stats$"))
    async def stats_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        acc_count = await db.get_accounts_count()
        target_id = await db.get_target_id()
        text_cnt, photo_cnt = await db.get_reviews_count()

        target_display = f"`{target_id}`" if target_id else "❌ _Not Set Yet_"

        stats_text = (
            "📊 **CURRENT SYSTEM STATS (SUPABASE CLOUD)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Connected Cloud Accounts:** `{acc_count}`\n"
            f"🎯 **Target Recipient ID:** {target_display}\n"
            f"💬 **Text Reviews Loaded:** `{text_cnt}`\n"
            f"📸 **Photo Proof Reviews:** `{photo_cnt}`\n"
            f"📦 **Total Reviews in Queue:** `{text_cnt + photo_cnt}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "☁️ *Saare sessions permanently Supabase me stored hain.*"
        )

        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
        ])
        try:
            await callback.message.edit_text(stats_text, reply_markup=back_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= SET TARGET USER ID BUTTON =================
    @app.on_callback_query(filters.regex("^btn_user_id$"))
    async def user_id_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        user_states[callback.from_user.id] = "AWAITING_TARGET_ID"
        prompt_text = (
            "🎯 **Set Target User ID / Username**\n\n"
            "Jis user ya account ko reviews send karne hain, uska **Telegram Username** yahan reply me bhejein:\n\n"
            "_(Example: `@my_telegram_username` ya `my_username`)_"
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_main_menu")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= TARGET ID INPUT RECEIVER =================
    @app.on_message(filters.private & filters.text, group=1)
    async def handle_target_id_input(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return

        state = user_states.get(message.from_user.id)
        if state == "AWAITING_TARGET_ID":
            target_input = message.text.strip()
            if not target_input.startswith("@") and not target_input.isdigit():
                target_input = f"@{target_input}"

            await db.set_target_id(target_input)
            user_states.pop(message.from_user.id, None)

            success_text = f"✅ **Target Successfully Set:** `{target_input}`\n\nAb reviews isi username par send honge."
            await message.reply_text(success_text, reply_markup=get_main_keyboard())
        else:
            message.continue_propagation()

    # ================= BACK TO MAIN MENU =================
    @app.on_callback_query(filters.regex("^btn_main_menu$"))
    async def back_to_menu(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        user_states.pop(callback.from_user.id, None)
        try:
            await callback.message.edit_text(
                "👋 **Main Dashboard Menu:**",
                reply_markup=get_main_keyboard()
            )
        except MessageNotModified:
            pass
        await callback.answer()