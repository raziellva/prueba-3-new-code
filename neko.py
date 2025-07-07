import os
import glob
from pyrogram import Client, filters
import zipfile
import shutil
import random
import string
import smtplib
import requests
from bs4 import BeautifulSoup
import re
import datetime
import subprocess
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

# Administradores y Usuarios del bot
admin_users = [5644237743] 
users = [5644237743, 6237974157] 

# Configuración de video por defecto
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '164k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264',

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

def update_video_settings(command: str):
    try:
        settings = command.split()
        for setting in settings:
            if '=' in setting:
                key, value = setting.split('=')
                if key in video_settings:
                    video_settings[key] = value
        return True
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return False

# Teclado inline con presets de calidad
def quality_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧩REELS", callback_data="reels")],
        [InlineKeyboardButton("🎌 ANIME", callback_data="anime")],
        [InlineKeyboardButton("🎭 SHOWS", callback_data="shows")],
        [InlineKeyboardButton("🎬 PELÍCULAS Pro", callback_data="PelículasPro")],
        [InlineKeyboardButton("🎬 PELÍCULAS Medium", callback_data="peliculasmedium")]
    ])

async def handle_start(client, message):
    await message.reply(
        "𝗦𝗘𝗟𝗘𝗖𝗖𝗜𝗢𝗡𝗔𝗥 𝗖𝗔𝗟𝗜𝗗𝗔𝗗:",
        reply_markup=quality_keyboard()
    )

@app.on_callback_query()
async def quality_callback(client, callback_query: CallbackQuery):
    quality_map = {
        "reels":    "resolution=420x720 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264",
        "anime":    "resolution=854x480 crf=32 audio_bitrate=60k fps=15 preset=veryfast codec=libx264",
        "show":    "resolution=854x480 crf=35 audio_bitrate=60k fps=18 preset=veryfast codec=libx264",
        "peliculaspro":   "resolution=854x480 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264",
        "peliculasmedium":  "resolution=854x480 crf=32 audio_bitrate=60k fps=18 preset=veryfast codec=libx264"
    }
    config = quality_map.get(callback_query.data)
    if config and update_video_settings(config):
        await callback_query.answer("🛠️ Calidad aplicada🛠️.")
        await callback_query.message.edit_text(
            f"⚙️ Configuración actual⚙️:\n{video_settings}"
        )
    else:
        await callback_query.answer("❌ Error al aplicar calidad.")

async def get_video_info(video_path):
    """Obtiene información detallada del video usando ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration,size:stream=width,height,r_frame_rate',
            '-of', 'json', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFprobe error: {result.stderr}")
            return None
        return result.stdout
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

async def compress_video(client, message: Message):
    if not (message.reply_to_message and message.reply_to_message.video):
        await message.reply("Por favor, responde a un video para comprimirlo.")
        return

    try:
        original_video_path = await app.download_media(
            message.reply_to_message.video,
            file_name=f"original_{message.message_id}.mp4"
        )
        if not os.path.exists(original_video_path):
            await message.reply("Error al descargar el video.")
            return

        original_size = os.path.getsize(original_video_path)
        if original_size > 2 * 1024**3:  # 2 GB
            os.remove(original_video_path)
            await message.reply("⚠️ El archivo es demasiado grande (máximo 2 GB).")
            return

        await message.reply(
            f"📥 Video descargado.\n"
            f"Tamaño original: {original_size/1024**2:.2f} MB\n"
            f"⚙️ Compresión: {video_settings}"
        )

        compressed_video_path = f"compressed_{message.message_id}.mkv"
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', original_video_path,
            '-s', video_settings['resolution'],
            '-crf', video_settings['crf'],
            '-b:a', video_settings['audio_bitrate'],
            '-r', video_settings['fps'],
            '-preset', video_settings['preset'],
            '-c:v', video_settings['codec'],
            '-threads', video_settings['threads'],
            '-max_muxing_queue_size', video_settings['max_muxing_queue_size'],
            '-progress', '-', '-nostats', '-loglevel', 'error',
            compressed_video_path
        ]

        start = datetime.datetime.now()
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        last_update = start
        while True:
            await asyncio.sleep(5)
            if process.returncode is not None:
                break
            if (datetime.datetime.now() - last_update).seconds >= 30:
                elapsed = (datetime.datetime.now() - start).seconds
                await message.reply(f"⏳ Comprimiendo… {elapsed}s transcurridos")
                last_update = datetime.datetime.now()

        if process.returncode != 0:
            err = (await process.stderr.read()).decode()
            logger.error(f"FFmpeg error: {err}")
            await message.reply(f"❌ Error al comprimir:\n{err[:400]}")
            return

        compressed_size = os.path.getsize(compressed_video_path)
        duration = str(datetime.datetime.now() - start).split('.')[0]

        description = (
            f"✅ Completado\n"
            f"Original: {original_size/1024**2:.2f} MB\n"
            f"Comprimido: {compressed_size/1024**2:.2f} MB\n"
            f"Reducción: {100 - (compressed_size/original_size*100):.1f}%\n"
            f"Tiempo: {duration}\n"
            f"Configuración: {video_settings}"
        )

        await message.reply_chat_action("upload_document")
        await app.send_video(
            chat_id=message.chat.id,
            video=compressed_video_path,
            caption=description,
            progress=progress_callback
        )

    except Exception as e:
        logger.error(f"Error in compress_video: {e}", exc_info=True)
        await message.reply(f"⚠️ Error inesperado: {e}")

    finally:
        for path in [original_video_path, compressed_video_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Error deleting {path}: {e}")

async def progress_callback(current, total):
    pass

@app.on_message(filters.text)
async def handle_message(client, message):
    global users
    text = message.text
    user_id = message.from_user.id
    if user_id not in users:
        return

    try:
        if text.startswith(('/start', '.start')):
            await handle_start(client, message)
        elif text.startswith(('/convert', '.convert')):
            await compress_video(client, message)
        elif text.startswith(('/calidad', '.calidad')):
            if update_video_settings(text.split(maxsplit=1)[1]):
                await message.reply(f"✅ Configuración actualizada:\n{video_settings}")
            else:
                await message.reply("❌ Error al actualizar configuración.")
        elif text.startswith(('/adduser', '.adduser')) and user_id in admin_users:
            await add_user(client, message)
        elif text.startswith(('/banuser', '.banuser')) and user_id in admin_users:
            await remove_user(client, message)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.reply("⚠️ Ocurrió un error procesando tu solicitud.")

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()
