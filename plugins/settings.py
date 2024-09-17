from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ForceReply
from helper.database import db  # Use the db instance from database.py
import importlib.util
import sys

# Dynamically import the module with special characters
module_name = "thumb_and_cap"  # Use an appropriate module name without special characters
module_path = "./plugins/thumb_&_cap.py"

try:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    thumb_and_cap = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = thumb_and_cap
    spec.loader.exec_module(thumb_and_cap)

    # Import functions from the dynamically loaded module
    handle_set_caption = thumb_and_cap.handle_set_caption
    handle_delete_caption = thumb_and_cap.handle_delete_caption
    handle_see_caption = thumb_and_cap.handle_see_caption
    handle_view_thumbnail = thumb_and_cap.handle_view_thumbnail
    handle_delete_thumbnail = thumb_and_cap.handle_delete_thumbnail
except Exception as e:
    print(f"Error importing module '{module_name}': {e}")

@Client.on_message(filters.private & filters.command("settings"))
async def settings_command(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        
        user_media_type = await db.get_media_type(user_id) or "Video"
        auto_rename_status = await db.get_auto_rename_status(user_id) or "❌"
        screenshot_status = await db.get_screenshot_response(user_id) or "❌"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("sᴇᴛ ᴍᴇᴅɪᴀ", callback_data="set_media")],
            [
                InlineKeyboardButton("sᴇᴛ ᴄᴀᴩᴛɪᴏɴ", callback_data="set_caption"),
                InlineKeyboardButton("ᴠɪᴇᴡ ᴄᴀᴩᴛɪᴏɴ", callback_data="see_caption"),
                InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴄᴀᴩᴛɪᴏɴ", callback_data="delete_caption")
            ],
            [
                InlineKeyboardButton("sᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="set_thumbnail"),
                InlineKeyboardButton("ᴠɪᴇᴡ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="view_thumbnail"),
                InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="delete_thumbnail")
            ],
            [
                InlineKeyboardButton("sᴇᴛ ᴘʀᴇғɪx", callback_data="set_prefix"),
                InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴘʀᴇғɪx", callback_data="del_prefix"),
                InlineKeyboardButton("sᴇᴇ ᴘʀᴇғɪx", callback_data="see_prefix")
            ],
            [
                InlineKeyboardButton("sᴇᴛ sᴜғғɪx", callback_data="set_suffix"),
                InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ sᴜғғɪx", callback_data="del_suffix"),
                InlineKeyboardButton("sᴇᴇ sᴜғғɪx", callback_data="see_suffix")
            ],
            [
                InlineKeyboardButton(f"ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ {auto_rename_status}", callback_data="auto_rename"),
                InlineKeyboardButton("ᴀᴅᴅᴏɴs", callback_data="addons")
            ]
        ])
        
        await message.reply_photo(
            photo="https://graph.org/file/0a1de3013521eb6e7ee02.jpg",  # Your image link
            caption="**⚙️ Sᴇᴛᴛɪɴɢs Mᴇɴᴜ**\n\nSᴇʟᴇᴄᴛ ᴀɴ Oᴘᴛɪᴏɴ:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error in /settings command: {e}")

@Client.on_message(filters.private & filters.command("autorename"))
async def auto_rename_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Extract the format from the command
    format = message.text.split("/autorename", 1)[1].strip()

    # Save the format template to the database
    await db.set_auto_rename_format(user_id, format)

    await message.reply_text("**Auto Rename Format Updated Successfully! ✅**")

@Client.on_callback_query()
async def callback_handler(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "auto_rename":
        auto_rename_status = await db.get_auto_rename_status(user_id) or "❌"
        new_status = "✅" if auto_rename_status == "❌" else "❌"
        await db.set_auto_rename_status(user_id, new_status)
        await callback_query.message.edit_text(
            "**THIS IS A AUTO RENAME FROM CAPTION**\n\n"
            "**PLEASE SETUP AUTO RENAME FORMAT**\n\n"
            "Usᴇ Tʜᴇsᴇ Kᴇʏᴡᴏʀᴅs Tᴏ Sᴇᴛᴜᴘ Cᴜsᴛᴏᴍ Fɪʟᴇ Nᴀᴍᴇ\n\n"
            "✓ ᴇᴘɪsᴏᴅᴇ :- Tᴏ Rᴇᴘʟᴀᴄᴇ Eᴘɪsᴏᴅᴇ Nᴜᴍʙᴇʀ\n"
            "✓ ᴏ̨ᴜᴀʟɪᴛʏ :- Tᴏ Rᴇᴘʟᴀᴄᴇ Tʜᴇ Qᴜᴀʟɪᴛʏ\n"
            "✓ ᴛɪᴛʟᴇ :- Tᴏ Rᴇᴘʟᴀᴄᴇ Tʜᴇ Tɪᴛʟᴇ Oғ Tʜᴇ Fɪʟᴇ\n\n"
            f"**Current Auto-Rename Format:** {await db.get_auto_rename_format(user_id)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"↻ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")],
                [InlineKeyboardButton(f"ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ {'✅' if new_status == '✅' else '❌'}", callback_data="auto_rename")],
                [InlineKeyboardButton("🖊️ Sᴇᴛ Fᴏʀᴍᴀᴛ", callback_data="set_formattt")]
            ])
        )
    elif data == "set_formattt":
        await callback_query.message.reply_text(
            "Pʟᴇᴀsᴇ Sᴇɴᴅ Tʜᴇ Nᴇw Fᴏʀᴍᴀᴛ:**\n\nUse the format like `/autorename Episode - Quality`"
        )
    elif data == "addons":
        # Show the Addons menu with three buttons
        await callback_query.message.edit_text(
            "Select an option:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴄʀᴇᴇɴsʜᴏᴛs {'✅' if await db.get_screenshot_response(user_id) == '✅' else '❌'}", callback_data="generate_screenshots")],
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴀᴍᴘʟᴇ Vɪᴅᴇᴏ {'✅' if await db.get_sample_video_response(user_id) == '✅' else '❌'}", callback_data="generate_sample_video")],
                [InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data="main_menu")]
            ])
        )
    elif data == "generate_screenshots":
        # Get current status of screenshots
        screenshot_status = await db.get_screenshot_response(user_id) or "❌"
        # Toggle status
        new_status = "✅" if screenshot_status == "❌" else "❌"
        # Update status in the database
        await db.set_screenshot_response(user_id, new_status)
        # Update the message
        await callback_query.message.edit_text(
            "Sᴄʀᴇᴇɴsʜᴏᴛs ᴜᴘᴅᴀᴛᴇ ᴄᴏᴍᴘʟᴇᴛᴇ\n\n"
            "Sᴛᴀᴛᴜs: " + ("✅ Enabled" if new_status == "✅" else "❌ Disabled"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴄʀᴇᴇɴsʜᴏᴛs {'✅' if await db.get_screenshot_response(user_id) == '✅' else '❌'}", callback_data="generate_screenshots")],
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴀᴍᴘʟᴇ Vɪᴅᴇᴏ {'✅' if await db.get_sample_video_response(user_id) == '✅' else '❌'}", callback_data="generate_sample_video")],
                [InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data="main_menu")]
            ])
        )
    elif data == "generate_sample_video":
        # Get current status of sample video
        sample_video_status = await db.get_sample_video_response(user_id) or "❌"
        # Toggle status
        new_status = "✅" if sample_video_status == "❌" else "❌"
        # Update status in the database
        await db.set_sample_video_response(user_id, new_status)
        # Update the message
        await callback_query.message.edit_text(
            "Sᴀᴍᴘʟᴇ Vɪᴅᴇᴏ ᴜᴘᴅᴀᴛᴇ ᴄᴏᴍᴘʟᴇᴛᴇ\n\n"
            "Sᴛᴀᴛᴜs: " + ("✅ Enabled" if new_status == "✅" else "❌ Disabled"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴄʀᴇᴇɴsʜᴏᴛs {'✅' if await db.get_screenshot_response(user_id) == '✅' else '❌'}", callback_data="generate_screenshots")],
                [InlineKeyboardButton(f"Gᴇɴᴇʀᴀᴛᴇ Sᴀᴍᴘʟᴇ Vɪᴅᴇᴏ {'✅' if await db.get_sample_video_response(user_id) == '✅' else '❌'}", callback_data="generate_sample_video")],
                [InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data="main_menu")]
            ])
        )

    if data == "set_media":
        user_media_type = await db.get_media_type(user_id) or "Video"  # Fetch using db instance
        media_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Vɪᴅᴇᴏ ✅" if user_media_type == "Video" else "Video", callback_data="media_video"),
                InlineKeyboardButton("Dᴏᴄᴜᴍᴇɴᴛ ✅" if user_media_type == "Document" else "Document", callback_data="media_document")
            ],
            [InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data="main_menu")]
        ])
        await callback_query.message.edit_text("Sᴇʟᴇᴄᴛ Mᴇᴅɪᴀ Tʏᴘᴇ:", reply_markup=media_keyboard)

    elif data.startswith("media_"):
        media_type = data.split("_")[1].capitalize()
        await db.set_media_type(user_id, media_type)  # Set using db instance
        
        # Update the keyboard to show the new selection with a tick
        user_media_type = media_type  # Update to the new selection
        media_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Video ✅" if user_media_type == "Video" else "Video", callback_data="media_video"),
                InlineKeyboardButton("Document ✅" if user_media_type == "Document" else "Document", callback_data="media_document")
            ],
            [InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data="main_menu")]
        ])
        await callback_query.message.edit_text("Sᴇʟᴇᴄᴛ Mᴇᴅɪᴀ Tʏᴘᴇ:", reply_markup=media_keyboard)

    elif data == "main_menu":
        auto_rename_status = await db.get_auto_rename_status(user_id) or "❌"
        screenshot_status = await db.get_screenshot_response(user_id) or "❌"
        await callback_query.message.edit_text(
            "**⚙️ Sᴇᴛᴛɪɴɢs Mᴇɴᴜ**\n\nSᴇʟᴇᴄᴛ ᴀɴ Oᴘᴛɪᴏɴ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴇᴛ ᴍᴇᴅɪᴀ", callback_data="set_media")],
                [
                    InlineKeyboardButton("sᴇᴛ ᴄᴀᴩᴛɪᴏɴ", callback_data="set_caption"),
                    InlineKeyboardButton("ᴠɪᴇᴡ ᴄᴀᴩᴛɪᴏɴ", callback_data="see_caption"),
                    InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴄᴀᴩᴛɪᴏɴ", callback_data="delete_caption")
                ],
                [
                    InlineKeyboardButton("sᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="set_thumbnail"),
                    InlineKeyboardButton("ᴠɪᴇᴡ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="view_thumbnail"),
                    InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="delete_thumbnail")
                ],
                [
                    InlineKeyboardButton("sᴇᴛ ᴘʀᴇғɪx", callback_data="set_prefix"),
                    InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴘʀᴇғɪx", callback_data="del_prefix"),
                    InlineKeyboardButton("sᴇᴇ ᴘʀᴇғɪx", callback_data="see_prefix")
                ],
                [
                    InlineKeyboardButton("sᴇᴛ sᴜғғɪx", callback_data="set_suffix"),
                    InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ sᴜғғɪx", callback_data="del_suffix"),
                    InlineKeyboardButton("sᴇᴇ sᴜғғɪx", callback_data="see_suffix")
                ],
                [
                    InlineKeyboardButton(f"ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ {auto_rename_status}", callback_data="auto_rename"),
                InlineKeyboardButton("ᴀᴅᴅᴏɴs", callback_data="addons")
                ]
            ])
        )

    elif data == "set_caption":
        await callback_query.message.reply_text(
            "Gɪᴠᴇ Tʜᴇ Cᴀᴩᴛɪᴏɴ\n\n"
            "Exᴀᴍᴩʟᴇ:- /set_caption {filename}\n\n"
            "💾 Sɪᴢᴇ: {filesize}\n\n"
            "⏰ Dᴜʀᴀᴛɪᴏɴ: {duration}"
        )

    elif data == "see_caption":
       caption = await db.get_caption(user_id)
       caption_text = caption if caption else "No caption set."
       await callback_query.message.edit_text(
        f"Current caption:\n\n{caption_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↻ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
        ])
    )

    elif data == "delete_caption":
        await db.set_caption(user_id, None)
        await callback_query.message.edit_text(
        "Caption deleted.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↻ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
        ])
    )


    elif data == "set_thumbnail":
        await callback_query.message.reply_text("Send me the new thumbnail (as a photo):")

    elif data == "view_thumbnail":
        thumbnail = await db.get_thumbnail(user_id)
        if thumbnail:
            await callback_query.message.reply_photo(thumbnail)
        else:
            await callback_query.message.reply_text("No thumbnail set.")

    elif data == "delete_thumbnail":
        await db.set_thumbnail(user_id, None)
        await callback_query.message.reply_text("Thumbnail deleted.")

    elif data == "set_prefix":
        await callback_query.message.reply_text(
            "Give the prefix:\n\nExample: /set_prefix @Aniflix_Official"
        )

    elif data == "set_suffix":
        await callback_query.message.reply_text(
            "Give the suffix:\n\nExample: /set_suffix @Aniflix_Official"
        )

    elif data == "del_prefix":
        await db.set_prefix(user_id, None)
        await callback_query.message.reply_text("Prefix deleted.")

    elif data == "see_prefix":
        prefix = await db.get_prefix(user_id)
        prefix_text = prefix if prefix else "No prefix set."
        await callback_query.message.edit_text(
        f"Current prefix:\n{prefix_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↻ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
        ])
    )

    elif data == "see_suffix":
        suffix = await db.get_suffix(user_id)
        suffix_text = suffix if suffix else "No suffix set."
        await callback_query.message.edit_text(
        f"Current suffix:\n{suffix_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↻ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
        ])
    )


    elif data == "del_suffix":
        await db.set_suffix(user_id, None)
        await callback_query.message.reply_text("Suffix deleted.")


