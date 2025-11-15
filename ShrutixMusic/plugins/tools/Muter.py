from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import re

BOT_OWNER_ID = 7081885854   # ← यहाँ अपनी Telegram ID डालना

def parse_duration(duration_str):
    match = re.match(r"(\d+)([smh]?)", duration_str)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2).lower()
    if unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    else:
        return value

async def is_admin(client, chat_id, user_id):
    if user_id == BOT_OWNER_ID:
        return True
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]


# /start — बटन दिखेगा (सिर्फ ग्रुप में)
@app.on_message(filters.command("start") & filters.group)
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Mute", callback_data="amute_help")],
        [InlineKeyboardButton("Unmute", callback_data="aunmute_help")]
    ])
    await message.reply(
        "👇 नीचे दिए गए बटन से म्यूट/अनम्यूट कमांड का उपयोग सीखे",
        reply_markup=keyboard
    )


# बटन क्लिक
@app.on_callback_query()
async def cb_handler(client, cq):
    if not await is_admin(client, cq.message.chat.id, cq.from_user.id):
        await cq.answer("यह सिर्फ एडमिन / ओनर के लिए है।", show_alert=True)
        return

    if cq.data == "amute_help":
        await cq.answer("म्यूट के लिए:\n/amute 30s (या 5m, 1h)\nरिप्लाई में यूज़र चुनें।", show_alert=True)

    if cq.data == "aunmute_help":
        await cq.answer("अनम्यूट के लिए:\n/aunmute\nरिप्लाई में यूज़र चुनें।", show_alert=True)


# /amute
@app.on_message(filters.command("amute", prefixes="/") & filters.group)
async def amute(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("सिर्फ एडमिन / ओनर यूज़ कर सकते हैं।")

    if not message.reply_to_message:
        return await message.reply("किसी यूज़र के मैसेज पर रिप्लाई करके टाइम दें: /amute 30s")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("टाइम देना ज़रूरी है! जैसे: /amute 30s")

    duration = parse_duration(parts[1])
    target = message.reply_to_message.from_user.id

    await message.reply(f"User `{target}` को {duration} सेकंड के लिए म्यूट किया जा रहा है।")

    end = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end:
        async for msg in client.search_messages(message.chat.id, from_user=target):
            await msg.delete()
        await asyncio.sleep(2)


# /aunmute
@app.on_message(filters.command("aunmute") & filters.group)
async def aunmute(client, message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("सिर्फ एडमिन / ओनर यूज़ कर सकते हैं।")

    if not message.reply_to_message:
        return await message.reply("अनम्यूट करने के लिए किसी यूज़र के मैसेज पर रिप्लाई करें।")

    await message.reply("अब इस यूज़र के मैसेज डिलीट नहीं होंगे।")
