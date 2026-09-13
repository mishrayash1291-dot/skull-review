import os
import re
import random
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied
from pyrogram.raw.functions.messages import DeleteHistory
from config import API_ID, API_HASH, ADMIN_ID
from utils.pfp_generator import download_random_pfp, cleanup_pfp
import database as db

logger = logging.getLogger(__name__)

bulk_engine_state = {
    "target_id": None,
    "photo_index": 0,
    "accounts_data": {}  # clean_phone -> { "sent_msg_ids": list, "chat_id": int }
}

def register_rotation_handlers(app: Client):

    # ================= 1. START BULK SENDING =================
    @app.on_callback_query(filters.regex("^btn_send_reviews$"))
    async def send_reviews_start(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        target_id = await db.get_target_id()
        if not target_id:
            await callback.answer("❌ Pehle [USER ID] button se target set karein!", show_alert=True)
            return

        accounts = await db.get_all_accounts()
        if not accounts:
            await callback.answer("❌ Pehle [ADD ACC] ya [SESSIONS] se accounts add karein!", show_alert=True)
            return

        text_reviews = await db.get_text_reviews()
        if not text_reviews:
            await callback.answer("❌ Pehle [SET REVIEWS] se Text reviews add karein!", show_alert=True)
            return

        photo_reviews = await db.get_photo_reviews()
        if not photo_reviews:
            await callback.answer("❌ Pehle [SET REVIEWS] -> [Load Photos (.zip)] se photos load karein!", show_alert=True)
            return

        formatted_target = target_id.strip()
        if not formatted_target.startswith("@") and not formatted_target.isdigit():
            formatted_target = f"@{formatted_target}"

        bulk_engine_state["target_id"] = formatted_target
        bulk_engine_state["photo_index"] = 0

        status_msg = await callback.message.edit_text(
            f"🚀 **Bulk Sending Started!**\n\n"
            f"🎯 Target: `{formatted_target}`\n"
            f"👥 Total Accounts: `{len(accounts)}`\n"
            f"📸 Loaded ZIP Proofs: `{len(photo_reviews)}`\n\n"
            "⏳ *Dispatching reviews...*"
        )
        await callback.answer()

        await process_bulk_send(client, status_msg)

    # ================= 2. REVIEW DISPATCHER =================
    async def process_bulk_send(bot_client: Client, status_msg: Message):
        target_id = bulk_engine_state["target_id"]
        photo_reviews = await db.get_photo_reviews()
        accounts = await db.get_all_accounts()

        if not accounts:
            return

        success_count = 0

        for acc in accounts:
            phone = acc["phone"]
            clean_phone = phone.replace("+", "").replace(" ", "")
            session_str = acc["session_string"]

            user_client = Client(
                name=f"blk_{clean_phone}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_str,
                in_memory=True
            )

            try:
                await user_client.start()

                target_peer = int(target_id) if str(target_id).isdigit() else str(target_id)
                chat_obj = await user_client.get_chat(target_peer)
                chat_id = chat_obj.id

                sent_msg_ids = []

                msg_count = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5], k=1)[0]

                def get_next_photo():
                    if not photo_reviews:
                        return None
                    idx = bulk_engine_state["photo_index"] % len(photo_reviews)
                    bulk_engine_state["photo_index"] += 1
                    path = photo_reviews[idx]["media_path"]
                    if path:
                        abs_p = os.path.abspath(path)
                        if os.path.exists(abs_p):
                            return abs_p
                    return None

                # 1 MESSAGE (Photo Proof + Caption)
                if msg_count == 1:
                    photo_path = get_next_photo()
                    caption_text = await db.get_unique_text_review()
                    if photo_path:
                        m = await user_client.send_photo(chat_id, photo_path, caption=caption_text)
                    else:
                        m = await user_client.send_message(chat_id, caption_text)
                    if m:
                        sent_msg_ids.append(m.id)

                # 2 MESSAGES (Text + Photo Proof)
                elif msg_count == 2:
                    t1 = await db.get_unique_text_review()
                    m1 = await user_client.send_message(chat_id, t1)
                    if m1:
                        sent_msg_ids.append(m1.id)
                    await asyncio.sleep(random.uniform(1.2, 2.0))

                    photo_path = get_next_photo()
                    t2 = await db.get_unique_text_review()
                    if photo_path:
                        m2 = await user_client.send_photo(chat_id, photo_path, caption=t2)
                    else:
                        m2 = await user_client.send_message(chat_id, t2)
                    if m2:
                        sent_msg_ids.append(m2.id)

                # 3 MESSAGES (Text + Photo Proof + Text)
                elif msg_count == 3:
                    t1 = await db.get_unique_text_review()
                    m1 = await user_client.send_message(chat_id, t1)
                    if m1:
                        sent_msg_ids.append(m1.id)
                    await asyncio.sleep(random.uniform(1.2, 2.0))

                    photo_path = get_next_photo()
                    t2 = await db.get_unique_text_review()
                    if photo_path:
                        m2 = await user_client.send_photo(chat_id, photo_path, caption=t2)
                    else:
                        m2 = await user_client.send_message(chat_id, t2)
                    if m2:
                        sent_msg_ids.append(m2.id)
                    await asyncio.sleep(random.uniform(1.2, 2.0))

                    t3 = await db.get_unique_text_review()
                    m3 = await user_client.send_message(chat_id, t3)
                    if m3:
                        sent_msg_ids.append(m3.id)

                # 4 MESSAGES
                elif msg_count == 4:
                    t1 = await db.get_unique_text_review()
                    m1 = await user_client.send_message(chat_id, t1)
                    if m1:
                        sent_msg_ids.append(m1.id)
                    await asyncio.sleep(random.uniform(1.0, 1.8))

                    photo_path = get_next_photo()
                    t2 = await db.get_unique_text_review()
                    if photo_path:
                        m2 = await user_client.send_photo(chat_id, photo_path, caption=t2)
                    else:
                        m2 = await user_client.send_message(chat_id, t2)
                    if m2:
                        sent_msg_ids.append(m2.id)
                    await asyncio.sleep(random.uniform(1.0, 1.8))

                    t3 = await db.get_unique_text_review()
                    m3 = await user_client.send_message(chat_id, t3)
                    if m3:
                        sent_msg_ids.append(m3.id)
                    await asyncio.sleep(random.uniform(1.0, 1.8))

                    t4 = await db.get_unique_text_review()
                    m4 = await user_client.send_message(chat_id, t4)
                    if m4:
                        sent_msg_ids.append(m4.id)

                if sent_msg_ids:
                    bulk_engine_state["accounts_data"][clean_phone] = {
                        "sent_msg_ids": sent_msg_ids,
                        "chat_id": chat_id
                    }
                    success_count += 1

                await user_client.stop()

            except Exception as e:
                logger.error(f"Bulk Send Error for {phone}: {e}")

            await asyncio.sleep(random.uniform(1.5, 3.0))

        action_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete Chat & Send Review Again 🔄", callback_data="btn_bulk_delete_and_resend")],
            [InlineKeyboardButton("🗑️ Delete Chats Only 🛑", callback_data="btn_bulk_delete_only")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")]
        ])

        summary_text = (
            f"✅ **Realistic Batch Completed!**\n\n"
            f"📩 **Reviews Sent:** `{success_count} / {len(accounts)}` Accounts sent reviews to `{target_id}`\n\n"
            "📸 *Aap target chat ka screenshot le lijiye, fir neeche options chunein:*"
        )

        try:
            await status_msg.edit_text(summary_text, reply_markup=action_kb)
        except Exception:
            await bot_client.send_message(ADMIN_ID, summary_text, reply_markup=action_kb)

    # ================= 3. BULK DELETE & RE-SEND (PURANI DP FORCE DELETE FIX) =================
    @app.on_callback_query(filters.regex("^btn_bulk_delete_and_resend$"))
    async def bulk_delete_and_resend_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        target_id = bulk_engine_state["target_id"]
        accounts = await db.get_all_accounts()

        status_msg = await callback.message.edit_text(
            f"⏳ *Deleting chats & wiping old DPs for {len(accounts)} accounts...*\n\n"
            "Kripya thoda wait karein..."
        )
        await callback.answer()

        for acc in accounts:
            phone = acc["phone"]
            clean_phone = phone.replace("+", "").replace(" ", "")
            session_str = acc["session_string"]

            user_client = Client(
                name=f"del_blk_{clean_phone}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_str,
                in_memory=True
            )

            try:
                await user_client.start()

                target_peer = int(target_id) if str(target_id).isdigit() else str(target_id)
                chat_obj = await user_client.get_chat(target_peer)
                chat_id = chat_obj.id

                # 1. Delete all individual sent messages
                acc_data = bulk_engine_state["accounts_data"].get(clean_phone, {})
                sent_msg_ids = acc_data.get("sent_msg_ids", [])
                if sent_msg_ids:
                    try:
                        await user_client.delete_messages(chat_id, sent_msg_ids, revoke=True)
                    except Exception:
                        pass

                # 2. Complete Chat History Wipe for both sides
                try:
                    raw_peer = await user_client.resolve_peer(chat_id)
                    await user_client.invoke(DeleteHistory(peer=raw_peer, max_id=0, revoke=True))
                except Exception as e:
                    logger.warning(f"DeleteHistory error: {e}")

                # 3. Update Name from names.txt
                new_name = await db.get_next_name()
                parts = new_name.split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""
                try:
                    await user_client.update_profile(first_name=first_name, last_name=last_name)
                except Exception as e:
                    logger.warning(f"Update profile name error: {e}")

                # 4. FORCE PURGE OLD PROFILE PHOTOS FIRST
                try:
                    old_photos = [p async for p in user_client.get_chat_photos("me")]
                    if old_photos:
                        await user_client.delete_profile_photos([p.file_id for p in old_photos])
                except Exception:
                    pass

                # 5. Apply Local PFP (Only if available from local pfp/ folder)
                pfp_path = await download_random_pfp(phone)
                if pfp_path and os.path.exists(pfp_path):
                    try:
                        await user_client.set_profile_photo(photo=pfp_path)
                    except Exception as e:
                        logger.warning(f"Set photo error: {e}")
                    cleanup_pfp(pfp_path)

                await user_client.stop()

            except Exception as e:
                logger.error(f"Bulk Morph Error for {phone}: {e}")

            await asyncio.sleep(1)

        await status_msg.edit_text(
            f"✨ *All chats deleted & accounts refreshed with clean identities!*\n\n"
            f"🚀 *Sending next batch of reviews to `{target_id}`...*"
        )

        await process_bulk_send(client, status_msg)

    # ================= 4. BULK DELETE ONLY =================
    @app.on_callback_query(filters.regex("^btn_bulk_delete_only$"))
    async def bulk_delete_only_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        target_id = bulk_engine_state["target_id"]
        accounts = await db.get_all_accounts()

        status_msg = await callback.message.edit_text(
            f"⏳ *Deleting all chats across {len(accounts)} accounts...*"
        )
        await callback.answer()

        for acc in accounts:
            phone = acc["phone"]
            clean_phone = phone.replace("+", "").replace(" ", "")
            session_str = acc["session_string"]

            user_client = Client(
                name=f"del_only_{clean_phone}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_str,
                in_memory=True
            )

            try:
                await user_client.start()

                target_peer = int(target_id) if str(target_id).isdigit() else str(target_id)
                chat_obj = await user_client.get_chat(target_peer)
                chat_id = chat_obj.id

                acc_data = bulk_engine_state["accounts_data"].get(clean_phone, {})
                sent_msg_ids = acc_data.get("sent_msg_ids", [])
                if sent_msg_ids:
                    try:
                        await user_client.delete_messages(chat_id, sent_msg_ids, revoke=True)
                    except Exception:
                        pass

                try:
                    raw_peer = await user_client.resolve_peer(chat_id)
                    await user_client.invoke(DeleteHistory(peer=raw_peer, max_id=0, revoke=True))
                except Exception as e:
                    pass

                await user_client.stop()

            except Exception as e:
                logger.error(f"Delete only error for {phone}: {e}")

            await asyncio.sleep(0.5)

        from handlers.admin_menu import get_main_keyboard
        await status_msg.edit_text(
            "✅ **All Chats Successfully Deleted!**\n\nSaare accounts se messages permanently remove ho gaye hain.",
            reply_markup=get_main_keyboard()
        )