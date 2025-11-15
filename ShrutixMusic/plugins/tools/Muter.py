from ShrutixMusic import app
from pyrogram import filters
from pyrogram.types import Message
import asyncio
import re

# अपना बॉट ओनर आईडी यहाँ डालें
BOT_OWNER_ID = 7081885854

def parse_duration(duration_str):
    match = re.match(r"(\\d+)([smh]?)", duration_str)
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

@app.on_message(filters.command("amute", prefixes="/") & filters.group)
async def amute(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("यह कमांड सिर्फ ग्रुप के एडमिन या बॉट के ओनर ही इस्तेमाल कर सकते हैं।")
        return

    if not message.reply_to_message and not message.entities:
        await message.reply("कृपया किसी यूज़र को टैग या रिप्लाई करके और टाइम देकर कमांड चलाएँ, जैसे `/amute 30s` या `/amute 5m`.")
        return

    # ड्यूरेशन पार्स करें
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("आपको म्यूट का समय देना होगा। जैसे `/amute 30s` या `/amute 5m`.")
        return

    duration = parse_duration(parts[1])
    if duration is None:
        await message.reply("अमान्य समय दिया गया है। कृपया सही फॉर्मैट में समय दें, जैसे 30s, 5m, 1h.")
        return

    # जिस यूज़र को म्यूट करना है उसे पहचानें (रिप्लाई या टैग से)
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        target_user_id = None
        for entity in message.entities:
            if entity.type == "text_mention":
                target_user_id = entity.user.id
                break
            elif entity.type == "mention":
                user = entity
                try:
                    user_data = await client.get_users(user.text)
                    target_user_id = user_data.id
                    break
                except Exception as e:
                    await message.reply("इस यूज़र को पहचानने में दिक्कत हुई। कृपया सही यूज़र टैग करें।")
                    return
        
        if not target_user_id:
            await message.reply("यूज़र को पहचान नहीं पाया। कृपया सही से टैग करें।")
            return

    await message.reply(f"यूज़र {target_user_id} को {duration} सेकंड के लिए म्यूट किया जा रहा है।")

    end_time = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end_time:
        async for msg in client.search_messages(message.chat.id, from_user=target_user_id):
            await msg.delete()
        await asyncio.sleep(1)

@app.on_message(filters.command("aunmute", prefixes="/") & filters.group)
async def aunmute(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("यह कमांड सिर्फ ग्रुप के एडमिन या बॉट के ओनर ही इस्तेमाल कर सकते हैं।")
        return

    if not message.reply_to_message and not message.entities:
        await message.reply("कृपया अनम्यूट करने के लिए किसी यूज़र के मैसेज पर रिप्लाई करें या उसे टैग करें।")
        return

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.
