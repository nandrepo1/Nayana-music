# ShrutixMusic/plugins/tools/Muter.py
from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, ChatAdminRequired
import asyncio
import re
import time

# ===========================
#   CONFIG — CHANGE THIS!!
# ===========================
BOT_OWNER_ID = 7081885854   # ← अपनी Telegram Numeric ID डालें
# ===========================


active_mutes = {}  # {(chat_id, user_id): end_timestamp}


# ===========================
# DURATION PARSER
# ===========================
def parse_duration(text):
    match = re.match(r"^(\d+)([smh]?)$", text.strip(), re.I)
    if not match:
        return None
    v = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return v * 60
    if unit == "h":
        return v * 3600
    return v  # seconds


# ===========================
# ADMIN CHECK (ROBUST)
# ===========================
async def is_admin(client, chat_id, user_id, message=None):
    try:
        if user_id == BOT_OWNER_ID:
            return True

        # Anonymous admin
        if message and getattr(message, "sender_chat", None):
            return True

        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ["administrator", "creator"]

    except:
        return False


# ===========================
# BOT DELETE PERMISSION CHECK
# ===========================
async def bot_can_delete(client, chat_id):
    try:
        me = await client.get_me()
        m = await client.get_chat_member(chat_id, me.id)

        # creator always ok
        if m.status == "creator":
            return True

        # check multiple possible attributes used in pyrogram versions
        for attr in ["can_delete_messages", "can_manage_messages", "can_delete"]:
            if getattr(m, attr, None) is True:
                return True

        # fallback: admin → allow delete
        if m.status == "administrator":
            return True

        return False

    except:
        return False


# ===========================
# GET TARGET USER
# ===========================
async def extract_target(client, message: Message):
    # Prefer reply
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    # Check mentions
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                return ent.user.id

            if ent.type == "mention":
                start = ent.offset
                length = ent.length
                username = message.text[start:start+length].lstrip("@")
                try:
                    user = await client.get_users(username)
                    return user.id
                except:
                    continue

    return None


# ===========================
# /amute — MAIN COMMAND
# ===========================
@app.on_message(filters.command("amute") & filters.group)
async def amute(client, message: Message):

    user_id = getattr(message.from_user, "id", None)

    if not await is_admin(client, message.chat.id, user_id, message=message):
        return await message.reply("यह कमांड सिर्फ ग्रुप एडमिन या बॉट ओनर ही चला सकता है।")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("उदाहरण: `/amute 30s`\nरिप्लाई या टैग करके चलाएँ।")

    duration = parse_duration(parts[1])
    if duration is None:
        return await message.reply("गलत टाइम फॉर्मेट। उदाहरण: 30s, 5m, 1h")

    target = await extract_target(client, message)
    if not target:
        return await message.reply("यूज़र नहीं मिला। कृपया रिप्लाई या टैग करें।")

    if not await bot_can_delete(client, message.chat.id):
        return await message.reply("बॉट के पास Delete Messages permission नहीं दिख रही।")

    key = (message.chat.id, target)
    active_mutes[key] = time.time() + duration

    await message.reply(f"यूज़र `{target}` को {duration} सेकंड के लिए म्यूट किया गया।")

    # DELETE LOOP
    while True:
        now = time.time()

        if key not in active_mutes:
            break

        if now >= active_mutes[key]:
            active_mutes.pop(key, None)
            try:
                await message.reply(f"यूज़र `{target}` का म्यूट समाप्त हुआ।")
            except:
                pass
            break

        # delete user's messages
        try:
            async for msg in client.search_messages(message.chat.id, from_user=target, limit=50):
                try:
                    await msg.delete()
                except:
                    pass
        except:
            pass

        await asyncio.sleep(0.3)


# ===========================
# /aunmute — STOP MUTING
# ===========================
@app.on_message(filters.command("aunmute") & filters.group)
async def aunmute(client, message: Message):

    user_id = getattr(message.from_user, "id", None)

    if not await is_admin(client, message.chat.id, user_id, message=message):
        return await message.reply("यह कमांड सिर्फ एडमिन या ओनर चला सकते हैं।")

    target = await extract_target(client, message)
    if not target:
        return await message.reply("रिप्लाई या टैग करके /aunmute चलाएँ।")

    key = (message.chat.id, target)

    if key in active_mutes:
        active_mutes.pop(key, None)
        return await message.reply(f"यूज़र `{target}` अब अनम्यूट है।")

    return await message.reply("यह यूज़र अभी म्यूट नहीं है।")
