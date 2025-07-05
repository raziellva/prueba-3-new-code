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
from pyrogram.types import Message

# Configuración del bot (existente)
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')
admin_users = [5644237743] 
users = [5644237743, 6237974157] 

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración de compresión (existente)
video_settings = {
    'resolution': '854x480',
    'crf': '35',
    'audio_bitrate': '60k',
    'fps': '15',
    'preset': 'veryfast',
    'codec': 'libx264',
    'auto_compress': False  # Nuevo parámetro para controlar la compresión automática
}

def update_video_settings(command: str):
    settings = command.split()
    for setting in settings:
        if '=' in setting:  # Verificación adicional para evitar errores
            key, value = setting.split('=')
            video_settings[key] = value

# Función para comprimir video (existente, con pequeñas mejoras)
async def compress_video(client, message: Message, auto_mode=False):
    if message.reply_to_message and message.reply_to_message.video:
        original_video_path = await app.download_media(message.reply_to_message.video)
        original_size = os.path.getsize(original_video_path)
        
        # Solo enviar mensaje si no es modo automático
        if not auto_mode:
            await app.send_message(chat_id=message.chat.id, 
                                  text=f"𝐈𝐧𝐢𝐜𝐢𝐚𝐧𝐝𝐨 𝐂𝐨𝐦𝐩𝐫𝐞𝐬𝐢𝐨𝐧..\n"
                                      f"📚Tamaño original: {original_size // (1024 * 1024)} MB")
        
        compressed_video_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
        ffmpeg_command = [
            'ffmpeg', '-y', '-i', original_video_path,
            '-s', video_settings['resolution'], '-crf', video_settings['crf'],
            '-b:a', video_settings['audio_bitrate'], '-r', video_settings['fps'],
            '-preset', video_settings['preset'], '-c:v', video_settings['codec'],
            compressed_video_path
        ]
        
        try:
            start_time = datetime.datetime.now()
            
            if not auto_mode:
                await app.send_message(chat_id=message.chat.id, text="🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...")
            
            process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            
            compressed_size = os.path.getsize(compressed_video_path)
            duration = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                                             compressed_video_path])
            duration = float(duration.strip())
            duration_str = str(datetime.timedelta(seconds=duration))
            processing_time = datetime.datetime.now() - start_time
            processing_time_str = str(processing_time).split('.')[0]
            
            description = (
                f"🗜️𝐕𝐢𝐝𝐞𝐨 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐝𝐨 𝐂𝐨𝐫𝐫𝐞𝐜𝐭𝐚𝐦𝐞𝐧𝐭𝐞📥\n"
                "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗼𝗿𝗶𝗴𝗶𝗻𝗮𝗹: {original_size // (1024 * 1024)} MB\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗰𝗼𝗺𝗽𝗿𝗶𝗺𝗶𝗱𝗱𝗼: {compressed_size // (1024 * 1024)} MB\n"
                f" ┖• 𝗧𝗶𝗲𝗺𝗽𝗼 𝗱𝗲 𝗽𝗿𝗼𝗰𝗲𝘀𝗮𝗺𝗶𝗲𝗻𝘁𝗼: {processing_time_str}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
                f"⚙️𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗰𝗶𝗼𝗻 𝘂𝘀𝗮𝗱𝗮⚙️\n"
                f"•𝑹𝒆𝒔𝒐𝒍𝒖𝒄𝒊𝒐‌𝒏:  {video_settings['resolution']}\n" 
                f"•𝑪𝑹𝑭: {video_settings['crf']}\n"
                f"•𝑭𝑷𝑺: {video_settings['fps']}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            )
            
            await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description)
            
        except Exception as e:
            await app.send_message(chat_id=message.chat.id, text=f"Ocurrió un error al comprimir el video: {e}")
        finally:
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            if os.path.exists(compressed_video_path):
                os.remove(compressed_video_path)
    elif not auto_mode:
        await app.send_message(chat_id=message.chat.id, text="Por favor, responde a un video para comprimirlo.")

# Nueva función para manejar la compresión automática
async def handle_auto_compress(client, message: Message):
    if message.from_user.id not in admin_users:
        await message.reply("❌ Solo los administradores pueden cambiar esta configuración.")
        return
    
    new_state = not video_settings['auto_compress']
    video_settings['auto_compress'] = new_state
    state = "activada" if new_state else "desactivada"
    await message.reply(f"✅ Compresión automática {state}.")


# FORMA DEFINITIVA QUE FUNCIONARÁ
@app.on_message(filters.video & ~filters.command(commands=None))
async def handle_video_upload(client, message: Message):
    if video_settings['auto_compress'] and message.from_user.id in users:
        await compress_video(client, message, auto_mode=True)

# Resto de handlers existentes
async def handle_start(client, message):
    await message.reply("𝗕𝗼𝘁 𝗙𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗻𝗱𝗼✅...")

async def add_user(client, message):
    user_name = message.from_user.username
    try:
        user_id = int(message.text.split("/adduser")[1])
        if user_id in users:
            await message.reply_text(f"El ID:  \n`{user_id}`\nya esta en la lista de usuarios permitidos.") 
            return
            
        users.append(user_id)
        await message.reply_text(f"✅Usuario con ID:\n`{user_id}`\nHa sido añadido.")
    except (IndexError, ValueError):
        await message.reply_text(f"💢 Formato del comando incorrecto\n /adduser + ID.")

async def remove_user(client, message):
    user_name = message.from_user.username
    try:
        user_id = int(message.text.split("/banuser")[1]) 
        if user_id in users:
            users.remove(user_id)
            await message.reply_text(f"❌Usuario con ID:\n`{user_id}`\nHa sido eliminado de la lista ")
        else:
            await message.reply_text(f"❌El usuario:  \n`{user_id}`\nno se encuentra en la lista.")
    except (IndexError, ValueError):
        await message.reply_text("💢 Formato de comando incorrecto \n /banuser + ID.")

@app.on_message(filters.text)
async def handle_message(client, message):
    global users
    text = message.text
    user_id = message.from_user.id
    
    if user_id not in users:
        return
    
    if text.startswith(('/start', '.start')):
        await handle_start(client, message)
    elif text.startswith(('/convert', '.convert')):
        await compress_video(client, message)
    elif text.startswith(('/calidad', '.calidad')):
        update_video_settings(text[len('/calidad '):])
        await message.reply(f"🔄 Configuración Actualizada⚙️: \n `{video_settings}`")
    elif text.startswith(('/adduser', '.adduser')):
        if user_id in admin_users:
            await add_user(client, message)
    elif text.startswith(('/banuser', '.banuser')):
        if user_id in admin_users:
            await remove_user(client, message)
    elif text.startswith(('/autocompress', '.autocompress')):
        await handle_auto_compress(client, message)

print("Bot en ejecución, con función de compresión automática añadida")
app.run()