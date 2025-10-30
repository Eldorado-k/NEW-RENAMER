import random
import asyncio
import os
import time
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from pyrogram.errors import FloodWait
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db
from helper.database import Database
from helper.ffmpeg import fix_thumb, take_screen_shot
from get.preferences import get_rename_preference
from config import Config
from typing import Dict, Optional

app = Client("combined", api_id=Config.STRING_API_ID,
             api_hash=Config.STRING_API_HASH, session_string=Config.STRING_SESSION)

db = Database(Config.DB_URL, Config.DB_NAME)

renaming_operations = {}

# Système de stockage pour le tri
user_series_data: Dict[int, Dict] = {}

# Regex optimisées pour l'extraction des métadonnées
SEASON_PATTERN = re.compile(r'(S(?:aison)?|Season)[\s\._-]*(\d+)', re.IGNORECASE)
EPISODE_PATTERN = re.compile(r'(E(?:p(?:isode)?)?|Épisode|EP|Ep)[\s\._-]*(\d+)', re.IGNORECASE)
EPISODE_ONLY_PATTERN = re.compile(r'(?:E|Ep|Episode|EP|Épisode)[\s\._-]*(\d+)', re.IGNORECASE)
NUMBER_PATTERN = re.compile(r'(\d+)(?:\.\w+)?$')

# Define regex patterns for extracting information
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)

def extract_quality(filename):
    match5 = re.search(pattern5, filename)
    if match5:
        return match5.group(1) or match5.group(2)
    match6 = re.search(pattern6, filename)
    if match6:
        return "4k"
    match7 = re.search(pattern7, filename)
    if match7:
        return "2k"
    match8 = re.search(pattern8, filename)
    if match8:
        return "HdRip"
    match9 = re.search(pattern9, filename)
    if match9:
        return "4kX264"
    match10 = re.search(pattern10, filename)
    if match10:
        return "4kx265"
    return "Unknown"

def extract_episode_number(caption):
    match = re.search(pattern1, caption)
    if match:
        return match.group(2)
    match = re.search(pattern2, caption)
    if match:
        return match.group(2)
    match = re.search(pattern3, caption)
    if match:
        return match.group(1)
    match = re.search(pattern3_2, caption)
    if match:
        return match.group(1)
    match = re.search(pattern4, caption)
    if match:
        return match.group(2)
    match = re.search(patternX, caption)
    if match:
        return match.group(1)
    return None

def extract_metadata(text: str):
    """Extrait les métadonnées avec détection intelligente"""
    # Essai d'extraire saison et épisode format standard
    season_match = SEASON_PATTERN.search(text)
    episode_match = EPISODE_PATTERN.search(text)
    
    if season_match and episode_match:
        return (
            text[:season_match.start()].strip(),
            int(season_match.group(2)),
            int(episode_match.group(2))
        )
    
    # Recherche d'épisode seul avec lettre
    episode_only_match = EPISODE_ONLY_PATTERN.search(text)
    if episode_only_match:
        return (
            text[:episode_only_match.start()].strip(),
            None,
            int(episode_only_match.group(1))
        )
    
    # Détection intelligente des numéros d'épisode sans 'E'
    patterns = [
        r'[\.\s_-](\d{2,3})[\.\s_-]',
        r'[\.\s_-](\d{1,2})[\.\s]',
        r'\[(\d{2,3})\]',
        r'\((\d{2,3})\)',
    ]
    
    # Éviter les numéros de résolution
    resolution_keywords = ['720', '1080', '480', '2160', '4k', 'hd', 'fullhd']
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            episode_num = match.group(1)
            if episode_num not in resolution_keywords and 1 <= int(episode_num) <= 999:
                series_name = text[:match.start()].strip()
                series_name = re.sub(r'[\d\[\]\(\)]+$', '', series_name).strip()
                return series_name, None, int(episode_num)
    
    # Dernier recours: chercher le dernier nombre dans le nom de fichier
    numbers = re.findall(r'\d+', text)
    if numbers:
        for num in reversed(numbers):
            episode_num = int(num)
            if 1 <= episode_num <= 999:
                series_name = re.sub(r'\d+.*$', '', text).strip()
                series_name = re.sub(r'[\.\s_-]+$', '', series_name)
                return series_name, None, episode_num
    
    raise ValueError("Format de fichier non reconnu")

async def check_user_subscription(user_id):
    subscription = await db.get_user_subscription(user_id)
    if subscription:
        return True
    return False

async def prompt_verification(client, message):
    await message.reply_text(
        "⚠️ You need to verify your account before using this bot. Please complete the verification process.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Verify", callback_data="verify")]
        ])
    )

async def send_to_channel_sorted(client, file_path, caption, thumb_path, media_type, file_size, user_id, original_message, series_name, season, episode):
    """Envoyer le fichier vers le canal avec système de tri"""
    
    if user_id not in Config.CHANNEL_ADMINS:
        await client.send_message(user_id, "⚠️ Vous n'êtes pas autorisé à envoyer des fichiers dans le canal.")
        return None
    
    try:
        # Stocker les informations pour le tri
        if user_id not in user_series_data:
            user_series_data[user_id] = {}
        
        if series_name not in user_series_data[user_id]:
            user_series_data[user_id][series_name] = {}
        
        season_key = season if season is not None else 1  # Default season 1 if None
        
        if season_key not in user_series_data[user_id][series_name]:
            user_series_data[user_id][series_name][season_key] = {}
        
        # Stocker les données du fichier
        user_series_data[user_id][series_name][season_key][episode] = {
            'file_path': file_path,
            'caption': caption,
            'thumb_path': thumb_path,
            'media_type': media_type,
            'file_size': file_size,
            'original_message': original_message
        }
        
        await original_message.edit(f"✅ Fichier ajouté à la file d'attente: {series_name} - S{season_key:02d}E{episode:02d}")
        return True
        
    except Exception as e:
        await client.send_message(user_id, f"❌ Erreur lors de l'ajout à la file: {e}")
        return None

async def send_sorted_files_to_channel(client, user_id):
    """Envoyer tous les fichiers triés vers le canal"""
    if user_id not in user_series_data or not user_series_data[user_id]:
        return 0
    
    total_sent = 0
    
    try:
        # Parcourir toutes les séries triées
        for series_name in sorted(user_series_data[user_id].keys()):
            series_data = user_series_data[user_id][series_name]
            
            # Parcourir toutes les saisons triées
            for season in sorted(series_data.keys()):
                season_data = series_data[season]
                
                # Parcourir tous les épisodes triés
                for episode in sorted(season_data.keys()):
                    file_data = season_data[episode]
                    
                    # Formater la caption finale
                    if season is not None:
                        final_caption = f"<b>{series_name} - S{season:02d}E{episode:02d}</b>"
                    else:
                        final_caption = f"<b>{series_name} - Episode {episode:02d}</b>"
                    
                    # Envoyer le fichier au canal
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            if file_data['media_type'] == "video":
                                if file_data['file_size'] > 50 * 1024 * 1024:
                                    await client.send_document(
                                        chat_id=Config.DESTINATION_CHANNEL,
                                        document=file_data['file_path'],
                                        caption=final_caption,
                                        thumb=file_data['thumb_path']
                                    )
                                else:
                                    await client.send_video(
                                        chat_id=Config.DESTINATION_CHANNEL,
                                        video=file_data['file_path'],
                                        caption=final_caption,
                                        thumb=file_data['thumb_path']
                                    )
                            elif file_data['media_type'] == "audio":
                                await client.send_audio(
                                    chat_id=Config.DESTINATION_CHANNEL,
                                    audio=file_data['file_path'],
                                    caption=final_caption,
                                    thumb=file_data['thumb_path']
                                )
                            else:
                                await client.send_document(
                                    chat_id=Config.DESTINATION_CHANNEL,
                                    document=file_data['file_path'],
                                    caption=final_caption,
                                    thumb=file_data['thumb_path']
                                )
                            
                            total_sent += 1
                            break
                            
                        except FloodWait as e:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(e.value)
                            else:
                                raise e
                        except Exception as e:
                            if attempt == max_retries - 1:
                                raise e
                            await asyncio.sleep(2)
                    
                    # Pause anti-flood
                    await asyncio.sleep(1)
        
        return total_sent
        
    except Exception as e:
        print(f"Erreur lors de l'envoi trié: {e}")
        return total_sent

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_files(client, message):
    user_id = message.from_user.id

    try:
        is_premium = await check_user_subscription(user_id)
        if not is_premium:
            await prompt_verification(client, message)
            return

        preference = await get_rename_preference(user_id)
        if preference == "manual":
            await message.reply_text("✏️ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇ Nᴀᴍᴇ...",
                                     reply_to_message_id=message.id,
                                     reply_markup=ForceReply(True))
            return

        if preference == "auto":
            await auto_rename_files(client, message)
            return

    except Exception as e:
        await message.reply_text(f"⚠️ Error Occurred ☹️\n\n{e}")

@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    try:
        preference = await get_rename_preference(message.from_user.id)
        if preference != "manual":
            await message.reply_text("⚠️ Auto-renaming is enabled. This command is not applicable.")
            return

        reply_message = message.reply_to_message

        if isinstance(reply_message.reply_markup, ForceReply):
            new_name = message.text
            await message.delete()

            msg = await client.get_messages(message.chat.id, reply_message.id)
            file = msg.reply_to_message

            if not file:
                await message.reply_text("⚠️ This message doesn't contain any downloadable media.")
                return

            media = getattr(file, file.media.value, None)
            if not media:
                await message.reply_text("⚠️ This message doesn't contain any media.")
                return

            if not "." in new_name:
                if "." in media.file_name:
                    extn = media.file_name.rsplit('.', 1)[-1]
                else:
                    extn = "mkv"
                new_name = new_name + "." + extn

            await reply_message.delete()

            user_id = message.from_user.id
            media_type = await get_media_type(user_id)
            if not media_type:
                media_type = 'video'

            media_type = media_type.lower()
            await process_file(client, message, media, new_name, media_type)

    except Exception as e:
        await message.reply_text(f"⚠️ Error Occurred ☹️\n\n{e}")

async def process_file(client, message, media, new_name, media_type):
    """Process the file after getting the new name and media type."""

    file_path = f"downloads/{new_name}"
    metadata_path = None
    ph_path = None

    try:
        ms = await message.reply_text("⚙️ Tʀyɪɴɢ Tᴏ Dᴏᴡɴʟᴏᴀᴅɪɴɢ")
        path = await client.download_media(message=media, file_name=file_path, progress=progress_for_pyrogram, progress_args=("⚠️ __**Please wait...**__\n\n❄️ **Dᴏᴡɴʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ....**", ms, time.time()))
    except Exception as e:
        if ms:
            await ms.edit(f"⚠️ Error Occurred ☹️\n\n{e}")
        return

    _bool_metadata = await db.get_metadata(message.chat.id)

    if _bool_metadata:
        metadata_path = f"Metadata/{new_name}"
        metadata = await db.get_metadata_code(message.chat.id)
        if metadata:
            try:
                await ms.edit("I Fᴏᴜɴᴅ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ\n\n__**Aᴅᴅɪɴɢ Mᴇᴛᴀᴅᴀᴛᴀ Tᴏ Fɪʟᴇ....**")
                cmd = f"""ffmpeg -i "{path}" {metadata} "{metadata_path}" """
                process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                er = stderr.decode()
                if er:
                    return await ms.edit(f"{er}\n\n**Error**")
            except Exception as e:
                return await ms.edit(f"⚠️ Error Occurred ☹️\n\n{e}")
        await ms.edit("**Metadata added to the file successfully ✅**\n\n⚠️ __**Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....**")
    else:
        await ms.edit("⚠️ __**Please wait...**__\n\n\n**Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....**")

    duration = 0
    try:
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        if metadata.has("duration"):
            duration = metadata.get('duration').seconds
        parser.close()
    except Exception as e:
        pass

    c_caption = await db.get_caption(message.chat.id)
    c_thumb = await db.get_thumbnail(message.chat.id)

    if c_caption:
        try:
            caption = c_caption.format(filename=new_name, filesize=humanbytes(media.file_size), duration=convert(duration))
        except Exception as e:
            return await ms.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇʏᴡᴏʀᴅ Aʀɢᴜᴇɴᴛ ●> ({e})")
    else:
        caption = f"**{new_name}**"

    if media.thumbs or c_thumb:
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
            width, height, ph_path = await fix_thumb(ph_path)
        else:
            try:
                ph_path_ = await take_screen_shot(file_path, os.path.dirname(os.path.abspath(file_path)), random.randint(0, duration - 1))
                width, height, ph_path = await fix_thumb(ph_path_)
            except Exception as e:
                ph_path = None

    # Extraire les métadonnées pour le tri
    try:
        series_name, season, episode = extract_metadata(new_name)
    except ValueError:
        # Si impossible d'extraire, utiliser des valeurs par défaut
        series_name = "Série"
        season = 1
        episode = 1

    user_id = message.from_user.id
    if user_id in Config.CHANNEL_ADMINS:
        # Ajouter à la file d'attente pour envoi trié
        added = await send_to_channel_sorted(
            client, 
            file_path, 
            caption, 
            ph_path, 
            media_type, 
            media.file_size, 
            user_id,
            ms,
            series_name,
            season,
            episode
        )
        
        if added:
            # Nettoyer les fichiers temporaires
            if os.path.exists(path):
                os.remove(path)
            if metadata_path and os.path.exists(metadata_path):
                os.remove(metadata_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            return
        else:
            await ms.edit("❌ Échec de l'ajout à la file, envoi en PV...")
    
    # Si pas autorisé ou échec, envoyer en PV
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if media.file_size > 4000 * 1024 * 1024:
                filw = await client.send_document(message.chat.id, file_path, caption=caption, thumb=ph_path, force_document=True)
            elif media_type == "document":
                filw = await client.send_document(message.chat.id, file_path, caption=caption, thumb=ph_path)
            elif media_type == "video":
                filw = await client.send_video(message.chat.id, file_path, caption=caption, thumb=ph_path)
            elif media_type == "audio":
                filw = await client.send_audio(message.chat.id, file_path, caption=caption, thumb=ph_path)
            else:
                filw = await client.send_document(message.chat.id, file_path, caption=caption, thumb=ph_path)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                await ms.edit(f"⚠️ Error Occurred ☹️ Retrying... ({attempt + 1}/{max_retries})\n\n{e}")
                await asyncio.sleep(5)
            else:
                await ms.edit(f"⚠️ Error Occurred ☹️\n\n{e}")

    # Nettoyer les fichiers temporaires
    if os.path.exists(path):
        os.remove(path)
    if os.path.exists(file_path):
        os.remove(file_path)
    if metadata_path and os.path.exists(metadata_path):
        os.remove(metadata_path)
    if ph_path and os.path.exists(ph_path):
        os.remove(ph_path)

    try:
        await ms.delete()
    except Exception as e:
        pass

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id

    try:
        preference = await get_rename_preference(message.from_user.id)
        if preference == "manual":
            return
        format = await db.get_auto_rename_format(user_id)
        media_type = await db.get_media_type(user_id)
        
        # Extract media details
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
            file_size = message.document.file_size
            media_type = media_type or "document"
            caption = message.caption or ""
        elif message.video:
            file_id = message.video.file_id
            file_name = f"{message.video.file_name or 'video'}.mp4"
            file_size = message.video.file_size
            media_type = media_type or "video"
            caption = message.caption or ""
        elif message.audio:
            file_id = message.audio.file_id
            file_name = f"{message.audio.file_name or 'audio'}.mp3"
            file_size = message.audio.file_size
            media_type = media_type or "audio"
            caption = message.caption or ""
        else:
            return await message.reply_text("Unsupported File Type")

        if not caption:
            return await message.reply_text("No caption found for the media. Cannot rename.")

        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                return

        renaming_operations[file_id] = datetime.now()

        episode_number = extract_episode_number(caption)
        
        if episode_number:
            placeholders = ["episode", "Episode", "EPISODE", "{episode}"]
            for placeholder in placeholders:
                format = format.replace(placeholder, str(episode_number), 1)
            
            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in format:
                    extracted_qualities = extract_quality(caption)
                    if extracted_qualities == "Unknown":
                        await message.reply_text("I Was Not Able To Extract The Quality Properly. Renaming As 'Unknown'...")
                        return

                    format = format.replace(quality_placeholder, extracted_qualities)

            _, file_extension = os.path.splitext(file_name)
            new_file_name = f"{format}{file_extension}"
            file_path = f"downloads/{new_file_name}"
            file = message

            download_msg = await message.reply_text(text="Trying To Download.....")
            try:
                path = await client.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=("Download Started....", download_msg, time.time()))
            except Exception as e:
                return await download_msg.edit(f"Error: {e}")

            duration = 0
            try:
                metadata = extractMetadata(createParser(file_path))
                if metadata.has("duration"):
                    duration = metadata.get('duration').seconds
            except Exception:
                pass

            upload_msg = await download_msg.edit("Trying To Uploading.....")
            ph_path = None
            c_caption = await db.get_caption(message.chat.id)
            c_thumb = await db.get_thumbnail(message.chat.id)

            caption = c_caption.format(filename=new_file_name, filesize=humanbytes(file_size), duration=convert(duration)) if c_caption else f"**{new_file_name}**"

            if c_thumb:
                ph_path = await client.download_media(c_thumb)
            elif media_type == "video" and message.video.thumbs:
                ph_path = await client.download_media(message.video.thumbs[0].file_id)

            if ph_path:
                try:
                    Image.open(ph_path).convert("RGB").save(ph_path)
                    img = Image.open(ph_path)
                    img.resize((320, 240)).save(ph_path, "JPEG")
                except Exception:
                    ph_path = None

            # Extraire les métadonnées pour le tri
            try:
                series_name, season, episode = extract_metadata(new_file_name)
            except ValueError:
                series_name = "Série"
                season = 1
                episode = 1

            if user_id in Config.CHANNEL_ADMINS:
                added = await send_to_channel_sorted(
                    client, 
                    path, 
                    caption, 
                    ph_path, 
                    media_type, 
                    file_size, 
                    user_id,
                    upload_msg,
                    series_name,
                    season,
                    episode
                )
                
                if added:
                    if os.path.exists(path):
                        os.remove(path)
                    if ph_path and os.path.exists(ph_path):
                        os.remove(ph_path)
                    
                    try:
                        await download_msg.delete()
                    except:
                        pass
                    return
                else:
                    await upload_msg.edit("❌ Échec de l'ajout à la file, envoi en PV...")

            try:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Uploading Started....", upload_msg, time.time())
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
            except Exception as e:
                print(f"Error while uploading document: {e}")
            finally:
                if os.path.exists(path):
                    os.remove(path)
                if ph_path and os.path.exists(ph_path):
                    os.remove(ph_path)
                if download_msg:
                    try:
                        await download_msg.delete()
                    except Exception as e:
                        print(f"Error while deleting download_msg: {e}")
                if upload_msg:
                    try:
                        await upload_msg.delete()
                    except Exception as e:
                        print(f"Error while deleting upload_msg: {e}")

    except Exception as e:
        print(f"Error in auto_rename_files: {e}")
    finally:
        if file_id in renaming_operations:
            del renaming_operations[file_id]

# Commandes pour gérer l'envoi trié
@Client.on_message(filters.private & filters.command("send_sorted"))
async def send_sorted_command(client, message):
    """Commande pour envoyer tous les fichiers triés vers le canal"""
    user_id = message.from_user.id
    
    if user_id not in Config.CHANNEL_ADMINS:
        await message.reply_text("❌ Vous n'êtes pas autorisé à utiliser cette commande.")
        return
    
    if user_id not in user_series_data or not user_series_data[user_id]:
        await message.reply_text("❌ Aucun fichier dans la file d'attente.")
        return
    
    progress_msg = await message.reply_text("🔄 Envoi des fichiers triés vers le canal...")
    
    try:
        total_sent = await send_sorted_files_to_channel(client, user_id)
        
        if total_sent > 0:
            await progress_msg.edit(f"✅ {total_sent} fichiers envoyés avec succès vers le canal !")
            # Vider la file d'attente après envoi réussi
            user_series_data.pop(user_id, None)
        else:
            await progress_msg.edit("❌ Aucun fichier n'a pu être envoyé.")
            
    except Exception as e:
        await progress_msg.edit(f"❌ Erreur lors de l'envoi: {e}")

@Client.on_message(filters.private & filters.command("clear_queue"))
async def clear_queue_command(client, message):
    """Commande pour vider la file d'attente"""
    user_id = message.from_user.id
    
    if user_id in user_series_data:
        user_series_data.pop(user_id)
        await message.reply_text("✅ File d'attente vidée.")
    else:
        await message.reply_text("ℹ️ Aucune file d'attente active.")

@Client.on_message(filters.private & filters.command("queue_status"))
async def queue_status_command(client, message):
    """Commande pour voir le statut de la file d'attente"""
    user_id = message.from_user.id
    
    if user_id not in user_series_data or not user_series_data[user_id]:
        await message.reply_text("ℹ️ Aucun fichier dans la file d'attente.")
        return
    
    queue_info = "📋 **File d'attente actuelle:**\n\n"
    total_files = 0
    
    for series_name, series_data in user_series_data[user_id].items():
        queue_info += f"**{series_name}**\n"
        for season, season_data in series_data.items():
            episodes = sorted(season_data.keys())
            queue_info += f"  Saison {season}: Episodes {min(episodes)}-{max(episodes)} ({len(episodes)} fichiers)\n"
            total_files += len(episodes)
    
    queue_info += f"\n**Total: {total_files} fichiers**"
    queue_info += "\n\nUtilisez /send_sorted pour envoyer vers le canal"
    queue_info += "\nUtilisez /clear_queue pour vider la file"
    
    await message.reply_text(queue_info)

# New methods to set and get media type
async def set_media_type(user_id, media_type):
    """Set the media type preference for a user."""
    await db.col.update_one(
        {"_id": user_id},
        {"$set": {"media_type": media_type}},
        upsert=True
    )

async def get_media_type(user_id):
    """Retrieve the media type preference for a user."""
    user_data = await db.col.find_one({"_id": user_id})
    media_type = user_data.get("media_type") if user_data else None
    return media_type