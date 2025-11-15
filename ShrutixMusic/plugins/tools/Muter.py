# ShrutixMusic/plugins/tools/Muter.py
from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError, ChatAdminRequired
import asyncio
import re
import time
import logging

LOG = logging.getLogger(__name__)

# ====== CONFIG (अपना ID डालें) ======
BOT_OWNER_ID = 123456789   # ← अपनी numeric Telegram ID यहाँ डालें
# ======================================

# active_mutes store: {(chat_id, user_id): end_timestamp}
active_mutes = {}

def parse_duration(duration_str):
    """Parse 30s, 5m, 1h -> seconds. Return None if invalid."""
    if not duration_str:
        return None
    match = re.match(r"^(\d+)([smh]?)$", duration_str.strip(), re.I)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    return value  # seconds default

async def is_admin(client, chat_id, user_id):
    """Return True if user is bot owner or chat admin/creator."""
    if user_id == BOT_OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return getattr(member, "status", "") in ["administrator", "creator"]
    except RPCError as e:
        LOG.warning("is_admin: get_chat_member failed: %s", e)
        return False

async def bot_has_delete_permission(client, chat_id):
    """Robust check whether bot can delete messages in chat."""
    try:
        me = await client.get_me()
        m = await client.get_chat_member(chat_id, me.id)
    except RPCError as e:
        LOG.warning("bot_has_delete_permission: RPCError: %s", e)
        return False
    status = getattr(m, "status", "")
    # creator always can
    if status == "creator":
        return True
    # explicit attribute (pyrogram admin object)
    if getattr(m, "can_delete_messages", None) is True:
        return True
    # fallback: if administrator but attribute missing, assume yes (less strict)
    if status == "administrator":
        return True
    return False

# --- /start (group only) -> show basic buttons/help ---
@app.on_message(filters.command("start") & filters.group)
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("How to Mute", callback_data="amute_help")],
        [InlineKeyboardButton("How to Unmute", callback_data="aunmute_help")]
    ])
    await message.reply("Use buttons below for quick help (group only).", reply_markup=keyboard)

@app.on_callback_query()
async def cb_handler(client, cq):
    try:
        if not await is_admin(client, cq.message.chat.id, cq.from_user.id):
            await cq.answer("यह सिर्फ एडमिन/ओनर के लिए है।", show_alert=True)
            return
        if cq.data == "amute_help":
            await cq.answer("म्यूट करने के लिए: रिप्लाई या मेंशन करके `/amute 30s` (30s/5m/1h)", show_alert=True)
        elif cq.data == "aunmute_help":
            await cq.answer("अनम्यूट करने के लिए: रिप्लाई या मेंशन करके `/aunmute`", show_alert=True)
    except Exception as e:
        LOG.exception("callback error: %s", e)

# --- Debug: whoami ---
@app.on_message(filters.command("whoami") & (filters.user(BOT_OWNER_ID) | filters.me))
async def whoami_cmd(client, message):
    me = await client.get_me()
    await message.reply_text(f"Running client: {me.first_name} ({me.id})\nusername: @{me.username}")

# --- Debug: check permissions of bot in this chat ---
@app.on_message(filters.command("checkperm") & filters.group)
async def checkperm_cmd(client, message):
    try:
        me = await client.get_me()
        m = await client.get_chat_member(message.chat.id, me.id)
    except RPCError as e:
        return await message.reply(f"get_chat_member failed: {e}")

    info = f"me.id = {me.id}\nstatus = {getattr(m, 'status', 'unknown')}\n"
    attrs = []
    for attr in ("can_delete_messages", "can_restrict_members", "can_promote_members", "can_change_info"):
        if hasattr(m, attr):
            attrs.append(f"{attr}={getattr(m, attr)}")
    if attrs:
        info += "\n" + "\n".join(attrs)
    await message.reply(info)

# --- /amute: reply or mention supported ---
@app.on_message(filters.command("amute", prefixes="/") & filters.group)
async def amute_cmd(client, message: Message):
    try:
        # only admin or owner can invoke
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("सिर्फ ग्रुप के एडमिन या बॉट ओनर ही यह कमांड चला सकते हैं।")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("उदाहरण: `/amute 30s` — रिप्लाई या मेंशन करके चलाएँ।")

        duration = parse_duration(parts[1])
        if duration is None:
            return await message.reply("अमान्य समय। फॉर्मेट: 30s, 5m, 1h")

        # find target: prefer reply
        target_user_id = None
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user_id = message.reply_to_message.from_user.id
        else:
            # look for text_mention or mention in entities
            if message.entities:
                for ent in message.entities:
                    if ent.type == "text_mention" and ent.user:
                        target_user_id = ent.user.id
                        break
                    elif ent.type == "mention":
                        start = ent.offset
                        length = ent.length
                        username = message.text[start:start+length].lstrip("@")
                        try:
                            user_obj = await client.get_users(username)
                            target_user_id = user_obj.id
                            break
                        except RPCError:
                            continue

        if not target_user_id:
            return await message.reply("यूज़र नहीं मिला — कृपया रिप्लाई करें या सही से टैग करें।")

        # check bot permission
        if not await bot_has_delete_permission(client, message.chat.id):
            # give more diagnostic hint
            await message.reply("बॉट के पास 'Delete messages' परमिशन नहीं दिख रही। /checkperm चलाकर पुष्टि करें।")
            return

        key = (message.chat.id, target_user_id)
        end_ts = time.time() + duration
        active_mutes[key] = end_ts

        await message.reply(f"यूज़र `{target_user_id}` को {duration} सेकंड के लिए म्यूट किया गया — नए मैसेज तुरंत हटेंगे।")

        # loop to delete messages quickly until mute expires or removed
        while True:
            now = time.time()
            current_end = active_mutes.get(key)
            if (not current_end) or (current_end <= now):
                active_mutes.pop(key, None)
                try:
                    await message.reply(f"यूज़र `{target_user_id}` का म्यूट समाप्त हो गया।")
                except Exception:
                    pass
                break

            # delete recent messages by target (most recent first)
            try:
                async for msg in client.search_messages(message.chat.id, from_user=target_user_id, limit=50):
                    try:
                        await msg.delete()
                    except ChatAdminRequired:
                        await message.reply("बॉट के पास मैसेज डिलीट करने की अनुमति नहीं है (ChatAdminRequired)।")
                        active_mutes.pop(key, None)
                        return
                    except Exception:
                        # ignore per-message errors
                        pass
            except Exception as e:
                LOG.debug("search_messages error: %s", e)

            # very short sleep to keep deletions near-instant
            await asyncio.sleep(0.5)

    except Exception as e:
        LOG.exception("amute_cmd error: %s", e)
        try:
            await message.reply("कुछ त्रुटि हुई — लॉग देखें।")
        except:
            pass

# --- /aunmute: stop deleting for target ---
@app.on_message(filters.command("aunmute", prefixes="/") & filters.group)
async def aunmute_cmd(client, message: Message):
    try:
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("सिर्फ ग्रुप के एडमिन या बॉट ओनर ही यह कमांड चला सकते हैं।")

        target_user_id = None
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user_id = message.reply_to_message.from_user.id
        else:
            if message.entities:
                for ent in message.entities:
                    if ent.type == "text_mention" and ent.user:
                        target_user_id = ent.user.id
                        break
                    elif ent.type == "mention":
                        start = ent.offset
                        length = ent.length
                        username = message.text[start:start+length].lstrip("@")
                        try:
                            user_obj = await client.get_users(username)
                            target_user_id = user_obj.id
                            break
                        except RPCError:
                            continue

        if not target_user_id:
            return await message.reply("कृपया रिप्लाई करके या मेंशन करके अनम्यूट करें।")

        key = (message.chat.id, target_user_id)
        if key in active_mutes:
            active_mutes.pop(key, None)
            return await message.reply(f"यूज़र `{target_user_id}` को अनम्यूट कर दिया गया है। अब उसके नए मैसेज नहीं हटेंगे।")
        else:
            return await message.reply("यह यूज़र वर्तमान में म्यूट नहीं है।")

    except Exception as e:
        LOG.exception("aunmute_cmd error: %s", e)
        try:
            await message.reply("कुछ त्रुटि हुई — लॉग देखें।")
        except:
            pass
