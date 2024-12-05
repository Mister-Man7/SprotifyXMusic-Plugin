from SafoneAPI import SafoneAPI
from TheApi import api
from SprotifyMusic import app
from config import LOG_GROUP_ID
from pyrogram import filters
from pyrogram.types import Message


@app.on_message(filters.command("advice"))
async def advice(_, message: Message):
    A = await message.reply_text("...")
    res = api.get_advice()
    await A.edit(res)


@app.on_message(filters.command("astronomical"))
async def advice(_, message: Message):
    a = await SafoneAPI().astronomy()
    if a["success"]:
        c = a["date"]
        url = a["imageUrl"]
        b = a["explanation"]
        caption = f"🌌 **Today's Astronomical Event [{c}]:**\n\n{b}"
        await message.reply_photo(url, caption=caption)
    else:
        await message.reply_photo("🚫 **Please try again in a little while.!**")
        await app.send_message(LOG_GROUP_ID, "⚠️ **/astronomical It's not working.**")


__MODULE__ = "📝 Advice"
__HELP__ = """
/advice - 💡 **Get random advice**
/astronomical - 🌌 **To get today's astronomical fact**
"""
