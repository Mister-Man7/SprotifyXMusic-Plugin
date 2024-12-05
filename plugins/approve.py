from SprotifyMusic import app
from SprotifyMusic.core.mongo import mongodb
from SprotifyMusic.misc import SUDOERS
from SprotifyMusic.utils.keyboard import ikb
from pyrogram import filters, Client
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors.exceptions.bad_request_400 import UserAlreadyParticipant
from pyrogram.types import ChatJoinRequest, Message, CallbackQuery

from utils.permissions import admins_only, member_permissions

approvaldb = mongodb.autoapprove


def smallcap(text):
    trans_table = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ0𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
    )
    return text.translate(trans_table)


@app.on_message(filters.command("autoapprove") & filters.group)
@admins_only("can_change_info")
async def approval_command(_client: Client, message: Message):
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    if chat:
        mode = chat.get("mode", "")
        if not mode:
            mode = "manual"
            await approvaldb.update_one(
                {"chat_id": chat_id},
                {"$set": {"mode": mode}},
                upsert=True,
            )
        if mode == "automatic":
            switch = "manual"
            mdbutton = "🔄 **Automatic**"
        else:
            switch = "automatic"
            mdbutton = "🔄 **Manual**"
        buttons = {
            "❌ **Disable**": "approval_off",
            f"{mdbutton}": f"approval_{switch}",
        }
        keyboard = ikb(buttons, 1)
        await message.reply(
            "✅ **Auto-Approval enabled for this group.**", reply_markup=keyboard
        )
    else:
        buttons = {"✅ **Enable**": "approval_on"}
        keyboard = ikb(buttons, 1)
        await message.reply(
            "❌ **Auto-approval disabled for this group.**", reply_markup=keyboard
        )


@app.on_callback_query(filters.regex("approval(.*)"))
async def approval_cb(_client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    from_user = callback_query.from_user
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        if from_user.id not in SUDOERS:
            return await callback_query.answer(
                f"❌ **You do not have the required permission.**\n**Permission:** {permission}",
                show_alert=True,
            )
    command_parts = callback_query.data.split("_", 1)
    option = command_parts[1]
    if option == "off":
        if await approvaldb.count_documents({"chat_id": chat_id}) > 0:
            approvaldb.delete_one({"chat_id": chat_id})
            buttons = {"✅ **Enable**": "approval_on"}
            keyboard = ikb(buttons, 1)
            return await callback_query.edit_message_text(
                "❌ **Auto-approval disabled in this group.**",
                reply_markup=keyboard,
            )
    if option == "on":
        switch = "manual"
        mode = "automatic"
    if option == "automatic":
        switch = "manual"
        mode = option
    if option == "manual":
        switch = "automatic"
        mode = option
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True,
    )
    chat = await approvaldb.find_one({"chat_id": chat_id})
    mode = "🔄 **Automatic**" if chat["mode"] == "automatic" else "🔄 **Manual**"
    buttons = {"❌ **Disable**": "approval_off", f"{mode}": f"approval_{switch}"}
    keyboard = ikb(buttons, 1)
    await callback_query.edit_message_text(
        "✅ **Auto-approval enabled in this group.**", reply_markup=keyboard
    )


@app.on_message(filters.command("approveall") & filters.group)
@admins_only("can_restrict_members")
async def clear_pending_command(_client: Client, message: Message):
    a = await message.reply_text("⏳ **Please wait...**", quote=True)
    chat_id = message.chat.id
    await app.approve_all_chat_join_requests(chat_id)
    await a.edit(
        "✅ **If there is a user waiting for approval, I have already approved them.**")
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"pending_users": []}},
    )


@app.on_message(filters.command("clearpending") & filters.group)
@admins_only("can_restrict_members")
async def clear_pending_command(_client: Client, message: Message):
    chat_id = message.chat.id
    result = await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"pending_users": []}},
    )
    if result.modified_count > 0:
        await message.reply_text("✅ **Pending users have been cleaned up.**", quote=True)
    else:
        await message.reply_text("⚠️ **No pending users clear.**", quote=True)


@app.on_chat_join_request(filters.group)
async def accept(_client: Client, message: ChatJoinRequest):
    chat = message.chat
    user = message.from_user
    chat_id = await approvaldb.find_one({"chat_id": chat.id})
    if chat_id:
        mode = chat_id["mode"]
        if mode == "automatic":
            await app.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
            return
        if mode == "manual":
            is_user_in_pending = await approvaldb.count_documents(
                {"chat_id": chat.id, "pending_users": int(user.id)}
            )
            if is_user_in_pending == 0:
                await approvaldb.update_one(
                    {"chat_id": chat.id},
                    {"$addToSet": {"pending_users": int(user.id)}},
                    upsert=True,
                )
                buttons = {
                    "✅ **Accept**": f"manual_approve_{user.id}",
                    "❌ **Refuse**": f"manual_decline_{user.id}",
                }
                keyboard = ikb(buttons, int(2))
                text = f"**User: {user.mention} sent a request to join our group. Any admin can accept or decline.**"
                admin_data = [
                    i
                    async for i in app.get_chat_members(
                        chat_id=message.chat.id,
                        filter=ChatMembersFilter.ADMINISTRATORS,
                    )
                ]
                for admin in admin_data:
                    if admin.user.is_bot or admin.user.is_deleted:
                        continue
                    text += f"[\u2063](tg://user?id={admin.user.id})"
                return await app.send_message(chat.id, text, reply_markup=keyboard)


@app.on_callback_query(filters.regex("manual_(.*)"))
async def manual(app: Client, callback_query: CallbackQuery):
    chat = callback_query.message.chat
    from_user = callback_query.from_user
    permissions = await member_permissions(chat.id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        if from_user.id not in SUDOERS:
            return await callback_query.answer(
                f"❌ **You do not have the necessary permission.**\n**Permission:** {permission}",
                show_alert=True,
            )
    datas = callback_query.data.split("_", 2)
    dis = datas[1]
    id = datas[2]
    if dis == "approve":
        try:
            await app.approve_chat_join_request(chat_id=chat.id, user_id=id)
        except UserAlreadyParticipant:
            await callback_query.answer(
                "✅ **User already approved in the group by another administrator.**",
                show_alert=True,
            )
            return await callback_query.message.delete()

    if dis == "decline":
        try:
            await app.decline_chat_join_request(chat_id=chat.id, user_id=id)
        except Exception as e:
            if "messages.HideChatJoinRequest" in str(e):
                await callback_query.answer(
                    "✅ **User already approved in the group by another administrator.**",
                    show_alert=True,
                )

    await approvaldb.update_one(
        {"chat_id": chat.id},
        {"$pull": {"pending_users": int(id)}},
    )
    return await callback_query.message.delete()


__MODULE__ = "🛡️ Approve"
__HELP__ = """
**Comando:** /autoapprove

🛠️ **About:** 
This module allows the automatic approval of entry requests to your group through a unbeaten link 


**⚙️ Modes:**
When you send /autoapprove in your group, you will see a button **“Activate** if automatic approval is not activated for your group.  
𝗦𝗲 𝗷𝗮́ 𝗲𝘀𝘁𝗶𝘃𝗲𝗿 𝗮𝘁𝗶𝘃𝗮𝗱𝗮, 𝘃𝗼𝗰𝗲̂ 𝘃𝗲𝗿𝗮́ 𝗱𝗼𝗶𝘀 𝗺𝗼𝗱𝗼𝘀:

- **🔄 Automatic** - accept input requests automatically.

- **📝 Manual** - sends a message to the group, marking the admits, who can accept or refuse requests.

**🧹 Use:**  
/clearpending to clean all user pending input data, allowing them to reset the requests.
"""
