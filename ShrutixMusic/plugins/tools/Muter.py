# ShrutixMusic/plugins/tools/Muter.py
from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import ChatAdminRequired, RPCError
import asyncio
import re
import time

# अपने Telegram user id यहाँ डालें (owner)
BOT_OWNER_ID = 7081885854

# active_mutes: {(chat_id, user_id): end_timestamp}
active_mutes = {}

def parse_duration(duration_str):
    match = re.match(r"^(\d+)([smh]?)$", duration_str.strip(), re.I)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    return value  # default seconds

async def is_admin(client, chat_id, user_id):
    if user_id == BOT_OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except RPCError:
        return False

async def bot_has_delete_permission(client, chat_id):
    try:
        me = await client.get_chat_member(chat_id, (await client.get_me()).id)
        # can_delete_messages attribute available for admins
        return getattr(me, "can_delete_messages", False) or me.status == "creator"
    except RPCError:
        return False

# /amute command: supports reply OR mention in message.entities
@app.on_message(filters.command("amute", prefixes="/") & filters.group)
async def amute_cmd(client, message: Message):
    # permission of invoking user
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("सिर्फ ग्रुप के एडमिन या बॉट ओनर ही यह कमांड चला सकते हैं।")

    # parse duration and find target
    parts = message.text.split(maxsplit=1)
    if not parts or len(parts) < 2:
        return await message.reply("टाइम दें: जैसे `/amute 30s` और रिप्लाई करें या किसी को टैग करें।")

    duration = parse_duration(parts[1])
    if duration is None:
        return await message.reply("अमान्य समय। फॉर्मेट: 30s, 5m, 1h")

    # determine target user: prefer reply, else mention/text_mention
    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
    else:
        # check entities for text_mention or mention
        if message.entities:
            for ent in message.entities:
                if ent.type == "text_mention" and ent.user:
                    target_user_id = ent.user.id
                    break
                elif ent.type == "mention":
                    # extract username text from message and resolve it
                    start = ent.offset
                    length = ent.length
                    username = message.text[start:start+length]
                    # username like @name -> strip @
                    username = username.lstrip("@")
                    try:
                        user_obj = await client.get_users(username)
                        target_user_id = user_obj.id
                        break
                    except RPCError:
                        continue

    if not target_user_id:
        return await message.reply("यूज़र नहीं मिला। रिप्लाई करें या सही से टैग/मेंशन करें।")

    # bot permission check
    if not await bot_has_delete_permission(client, message.chat.id):
        return await message.reply("बॉट के पास 'Delete messages' परमिशन नहीं है। पहले बॉट को admin बनाकर अनुमति दें।")

    key = (message.chat.id, target_user_id)
    end_ts = time.time() + duration
    active_mutes[key] = end_ts

    await message.reply(f"यूज़र `{target_user_id}` को {duration} सेकंड के लिए म्यूट किया गया — अब उसके नए मैसेज तुरंत हटाए जाएंगे।")

    # loop to immediately delete messages until mute expires or removed
    try:
        while True:
            now = time.time()
            current_end = active_mutes.get(key)
            if not current_end or current_end <= now:
                # expired or manually removed
                active_mutes.pop(key, None)
                try:
                    await message.reply(f"यूज़र `{target_user_id}` का म्यूट समाप्त हो गया।")
                except Exception:
                    pass
                break

            # attempt to delete recent messages from target immediately
            # iterate recent messages in the chat (most recent first)
            try:
                async for msg in client.search_messages(message.chat.id, from_user=target_user_id, limit=50):
                    # try immediate delete
                    try:
                        await msg.delete()
                    except ChatAdminRequired:
                        await message.reply("बॉट के पास मैसेज डिलीट करने की अनुमति नहीं है।")
                        active_mutes.pop(key, None)
                        return
                    except Exception:
                        # ignore if message already deleted or can't delete that specific message
                        pass
            except Exception:
                # search_messages can raise for some chats — ignore and continue
                pass

            # very short sleep to try to keep deletions near-instant
            await asyncio.sleep(0.5)
    finally:
        active_mutes.pop(key, None)

# /aunmute command
@app.on_message(filters.command("aunmute", prefixes="/") & filters.group)
async def aunmute_cmd(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("सिर्फ ग्रुप के एडमिन या बॉट ओनर ही यह कमांड चला सकते हैं।")

    # target via reply or mention
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
        return await message.reply("कृपया रिप्लाई करें या किसी को टैग करके अनम्यूट करें।")

    key = (message.chat.id, target_user_id)
    if key in active_mutes:
        active_mutes.pop(key, None)
        return await message.reply(f"यूज़र `{target_user_id}` को अनम्यूट कर दिया गया है। अब उसके नए मैसेज नहीं हटेंगे।")
    else:
        return await message.reply("यह यूज़र वर्तमान में म्यूट नहीं है।")
