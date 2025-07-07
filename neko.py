import os
import glob
from pyrogram import Client, filters
import zipfile
import shutil
import random
import string
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
import re
from moodleclient import upload_token
import datetime
import subprocess
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton  # Añadido InlineKeyboardMarkup y InlineKeyboardButton

# Configuracion del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

# Administradores y Usuarios del bot
admin_users = list(map(int, os.getenv('ADMINS').split(',')))
users = list(map(int, os.getenv('USERS').split(',')))
temp_users = []
temp_chats = []
ban_users = []
allowed_users = admin_users + users + temp_users + temp_chats
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

compression_size = 10  # Tamaño de compresión por defecto en MB
file_counter = 0
bot_in_use = False

user_emails = {}
image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

# Función para generar el teclado de calidades
def get_quality_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Animes/Series Animadas", callback_data="quality_anime")
        ],
        [
            InlineKeyboardButton("Reels/Videos Cortos", callback_data="quality_reel")
        ],
        [
            InlineKeyboardButton("Películas Buena Calidad", callback_data="quality_movie_hq")
        ],
        [
            InlineKeyboardButton("Shows/Reality", callback_data="quality_show")
        ],
        [
            InlineKeyboardButton("Películas/Series Media Calidad", callback_data="quality_movie_mq")
        ]
    ])

# Manejador de callback queries para los botones de calidad
@app.on_callback_query()
async def handle_callback_query(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if not is_bot_public() and user_id not in allowed_users:
        await callback_query.answer("No tienes acceso al bot", show_alert=True)
        return
    
    if data.startswith("quality_"):
        quality_type = data.split("_")[1]
        
        if quality_type == "anime":
            settings = "resolution=854x480 crf=32 audio_bitrate=60k fps=15 preset=veryfast codec=libx264"
            description = "Calidad para Animes y Series Animadas"
        elif quality_type == "reel":
            settings = "resolution=420x720 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264"
            description = "Calidad para Reels y Videos Cortos"
        elif quality_type == "movie_hq":
            settings = "resolution=854x480 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264"
            description = "Calidad para Películas en Buena Calidad"
        elif quality_type == "show":
            settings = "resolution=854x480 crf=35 audio_bitrate=60k fps=18 preset=veryfast codec=libx264"
            description = "Calidad para Shows/Reality"
        elif quality_type == "movie_mq":
            settings = "resolution=854x480 crf=32 audio_bitrate=60k fps=18 preset=veryfast codec=libx264"
            description = "Calidad para Películas y Series en Calidad Media"
        
        update_video_settings(settings)
        await callback_query.answer(f"Configuración actualizada: {description}")
        await callback_query.message.edit_text(
            f"⚙️ Configuración actualizada:\n\n{description}\n\n{settings}",
            reply_markup=get_quality_keyboard()
        )

# [Resto de tus funciones existentes...]
# (Todas tus funciones actuales como compressfile, handle_compress, etc. permanecen igual)
# ...

video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

def update_video_settings(command: str):
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        video_settings[key] = value

# [Todas tus otras funciones permanecen igual hasta handle_message...]

BOT_IS_PUBLIC = os.getenv("BOT_IS_PUBLIC")

def is_bot_public():
    return BOT_IS_PUBLIC and BOT_IS_PUBLIC.lower() == "true"

@app.on_message(filters.text)
async def handle_message(client, message):
    text = message.text
    username = message.from_user.username
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_bot_public():
        if user_id not in allowed_users:
            if chat_id not in allowed_users or user_id in ban_users:
                return

    # Comandos existentes...
    if text.startswith(('/start', '.start', '/start')):
        await handle_start(client, message)
    elif text.startswith(('/convert', '.convert')):
        await compress_video(client, message)
    elif text.startswith(('/calidad', '.calidad')):
        update_video_settings(text[len('/calidad '):])
        await message.reply(f"🔄 Configuración Actualizada⚙️: {video_settings}")
    elif text.startswith(('/calidades', '.calidades')):  # Nuevo comando para mostrar botones
        await message.reply(
            "🎬 Selecciona una calidad predefinida:",
            reply_markup=get_quality_keyboard()
        )
    # [Resto de tus comandos existentes...]
    elif text.startswith(('/adduser', '.adduser')):
        if user_id in admin_users:
            await add_user(client, message)
    # [Todos los demás elif permanecen igual...]

# [El resto de tu código permanece igual...]

app.run()