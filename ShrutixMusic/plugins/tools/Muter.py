# ================= Muter.py (FULL + FINAL) =================
from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, ChatAdminRequired
import asyncio
import re
import time

# -----------------------------------------------------------
#   CONFIG — अपनी Telegram numeric ID डालें
# -----------------------------------------------------------
BOT_OWNER_ID = 7081885854          #  ← अपनी ID डालें
# -----------------------------------------------------------

# Active mutes
active_mutes = {}   # {(chat_id, user_id): end_timestamp}


# ----------------------- PARSE DURATION ---------------------
def parse_duration(text):
    """
    Convert: 30s, 5m, 1h → seconds
    """
    match = re.match(r"^(\d+)([smh]?)$", text.strip(), re.I)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600

    return value  # default → seconds


# ----------------------- CHECK ADMIN ------------------------
async def is_admin(client, chat_id, user_id, message=None):
    """
    Admin / Owner / Anonymous Admin (sender_chat)
    """
    try:
        # Bot Owner always allowed
        if user_id == BOT_OWNER_ID:
            return True

        # Anonymous admin → has sender_chat
        if message and getattr(message, "sender_chat", None):
            return True

        # Check via membership
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]

    except:
        return False


# ----------------- BOT DELETE PERMISSION -------------------
async def bot_can_delete(client, chat_id):
    """
    Robust: bot is admin → allow delete
    Some Telegram versions do not show can_delete_messages explicitly.
    """
    try:
        me = await client.get_me()
        m = await client.get_chat_member(chat_id, me.id)

        # If bot is admin or creator → allow delete
        if m.status in ("administrator", "creator"):
            return True

        # fallback check
        for attr in ["can_delete_messages", "can_manage_messages", "can_delete"]:
            if getattr(m, attr, None) is True:
                return True

        return False

    except:
        return False


# -------------------- GET TARGET USER ---------------------
async def extract_target(client, message: Message):
    """
    1st priority → reply  
    2nd → @mention / text_mention
    """
    # Reply
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    # Mentions
    if message.entities:
        for ent in message.entities:

            # text_mention → contains full user object
            if ent.type == "text_mention" and ent.user:
                return ent.user.id

            # @username mention → resolve username
            if ent.type == "mention":
                start = ent.offset
                length = ent.length
                username = message.text[start:start+length].lstrip("@")

                try:
                    user = await client.get_users(username)
                    return user.id
                except:
                    pass

    return None



# ======================= /amute COMMAND ======================
@app.on_message(filters.command("amute") & filters.group)
async def amute(client, message: Message):

    # CHECK ADMIN
    user_id = getattr(message.from_user, "id", None)
    if not await is_admin(client, message.chat.id, user_id, message=message):
        return await message.reply("❌ यह कमांड सिर्फ Admin या Bot Owner चला सकता है।")

    # GET DURATION
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("❌ Use: `/amute 30s` (Reply या Tag करें)")

    duration = parse_duration(parts[1])
    if duration is None:
        return await message.reply("❌ गलत टाइम — Use: 30s / 5m / 1h")

    # GET TARGET USER
    target = await extract_target(client, message)
    if not target:
        return await message.reply("❌ यूज़र नहीं मिला — Reply या Tag करें।")

    # CHECK BOT DELETE PERMISSION
    if not await bot_can_delete(client, message.chat.id):
        return await message.reply("❌ बॉट के पास Delete Messages की परमिशन नहीं दिख रही।")

    # REGISTER MUTE
    key = (message.chat.id, target)
    active_mutes[key] = time.time() + duration

    await message.reply(f"✅ User `{target}` **{duration} सेकंड** के लिए mute किया गया।")


    # ---------------- DELETE LOOP ----------------
    while True:
        now = time.time()

        # mute expired OR removed via aunmute
        if key not in active_mutes or now >= active_mutes[key]:
            active_mutes.pop(key, None)
            try:
                await message.reply(f"🔊 User `{target}` का mute ख़त्म।")
            except:
                pass
            break

        # Delete all new messages of that user
        try:
            async for msg in client.search_messages(message.chat.id, from_user=target, limit=40):
                try:
                    await msg.delete()
                except:
                    pass
        except:
            pass

        await asyncio.sleep(0.3)



# ======================= /aunmute COMMAND ======================
@app.on_message(filters.command("aunmute") & filters.group)
async def aunmute(client, message: Message):

    # CHECK ADMIN
    user_id = getattr(message.from_user, "id", None)
    if not await is_admin(client, message.chat.id, user_id, message=message):
        return await message.reply("❌ केवल Admin या Owner ही Unmute कर सकता है।")

    # GET TARGET USER
    target = await extract_target(client, message)
    if not target:
        return await message.reply("❌ Reply या Tag करके `/aunmute` चलाएँ।")

    key = (message.chat.id, target)

    if key in active_mutes:
        active_mutes.pop(key, None)
        return await message.reply(f"🔊 User `{target}` अनम्यूट कर दिया गया।")

    return await message.reply("❌ यह यूज़र mute नहीं है।")

# ================== END FILE ================================
