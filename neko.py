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

# Configuración de video con valores más robustos para archivos grandes
video_settings = {
    'resolution': '854x480',
    'crf': '28',  # Valor más balanceado para calidad/tamaño
    'audio_bitrate': '128k',  # Mejor calidad de audio
    'fps': '24',  # FPS más estándar
    'preset': 'medium',  # Más balance entre velocidad y compresión
    'codec': 'libx264',
    'threads': '0',  # Usar todos los cores disponibles
    'max_muxing_queue_size': '1024'  # Para evitar errores en archivos grandes
}

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

async def get_video_info(video_path):
    """Obtiene información detallada del video usando ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration,size:stream=width,height,r_frame_rate',
            '-of', 'json',
            video_path
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
    # Determinar si el vídeo está en el mensaje actual o en el respondido
    if message.video:
        video_message = message
    elif message.reply_to_message and message.reply_to_message.video:
        video_message = message.reply_to_message
    else:
        await message.reply("Por favor, envía o responde a un video para comprimirlo.")
        return

    try:
        # Descargar el video original
        original_video_path = await app.download_media(
            video_message.video,
            file_name=f"original_{video_message.message_id}.mp4"
        )
        
        if not os.path.exists(original_video_path):
            await message.reply("Error al descargar el video.")
            return

        original_size = os.path.getsize(original_video_path)
        if original_size > 2 * 1024 * 1024 * 1024:  # 2GB límite
            os.remove(original_video_path)
            await message.reply("⚠️ El archivo es demasiado grande (máximo 2GB).")
            return

        await message.reply(
            f"📥 Video descargado correctamente.\n"
            f"📏 Tamaño original: {original_size / (1024 * 1024):.2f} MB\n"
            f"⚙️ Iniciando compresión con configuración:\n"
            f"Resolución: {video_settings['resolution']}\n"
            f"CRF: {video_settings['crf']}\n"
            f"FPS: {video_settings['fps']}"
        )

        # Nombre del archivo comprimido
        compressed_video_path = f"compressed_{video_message.message_id}.mkv"
        
        # Comando FFmpeg optimizado para archivos grandes
        ffmpeg_command = [
            'ffmpeg', '-y',
            '-i', original_video_path,
            '-s', video_settings['resolution'],
            '-crf', video_settings['crf'],
            '-b:a', video_settings['audio_bitrate'],
            '-r', video_settings['fps'],
            '-preset', video_settings['preset'],
            '-c:v', video_settings['codec'],
            '-threads', video_settings['threads'],
            '-max_muxing_queue_size', video_settings['max_muxing_queue_size'],
            '-progress', '-',  # Para monitorear el progreso
            '-nostats',  # Reducir output innecesario
            '-loglevel', 'error',  # Solo mostrar errores
            compressed_video_path
        ]

        start_time = datetime.datetime.now()
        
        # Ejecutar FFmpeg en segundo plano
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Enviar actualizaciones periódicas
        last_update = datetime.datetime.now()
        while True:
            await asyncio.sleep(5)  # Actualizar cada 5 segundos
            
            if process.returncode is not None:
                break
                
            if (datetime.datetime.now() - last_update).seconds >= 30:
                elapsed = (datetime.datetime.now() - start_time).seconds
                await message.reply(f"⏳ Comprimiendo... Tiempo transcurrido: {elapsed} segundos")
                last_update = datetime.datetime.now()

        # Verificar si la compresión fue exitosa
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg error: {stderr.decode()}")
            await message.reply(f"❌ Error al comprimir el video:\n{stderr.decode()[:400]}")
            return

        # Obtener información del video comprimido
        compressed_size = os.path.getsize(compressed_video_path)
        video_info = await get_video_info(compressed_video_path)
        
        processing_time = datetime.datetime.now() - start_time
        processing_time_str = str(processing_time).split('.')[0]

        # Crear descripción detallada
        description = (
            f"✅ Video comprimido exitosamente\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"┠• Tamaño original: {original_size / (1024 * 1024):.2f} MB\n"
            f"┠• Tamaño comprimido: {compressed_size / (1024 * 1024):.2f} MB\n"
            f"┠• Reducción: {100 - (compressed_size / original_size * 100):.1f}%\n"
            f"┖• Tiempo de procesamiento: {processing_time_str}\n"
            f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            f"⚙️ Configuración usada:\n"
            f"• Resolución: {video_settings['resolution']}\n"
            f"• CRF: {video_settings['crf']}\n"
            f"• FPS: {video_settings['fps']}\n"
            f"• Preset: {video_settings['preset']}\n"
            f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"
        )

        # Enviar el video comprimido
        await message.reply_chat_action("upload_document")
        await app.send_video(
            chat_id=message.chat.id,
            video=compressed_video_path,
            caption=description
        )

    except Exception as e:
        logger.error(f"Error in compress_video: {e}", exc_info=True)
        await message.reply(f"⚠️ Ocurrió un error inesperado: {str(e)}")
    
    finally:
        # Limpieza de archivos temporales
        for file_path in [original_video_path, compressed_video_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting {file_path}: {e}")

# Funciones básicas de manejo de usuarios y comandos
async def handle_start(client, message):
    await message.reply("¡Bot activo! Envíame un video para comprimirlo o usa /convert respondiendo a un video.")

async def add_user(client, message):
    try:
        new_user_id = int(message.text.split()[1])
        if new_user_id not in users:
            users.append(new_user_id)
            await message.reply(f"✅ Usuario {new_user_id} añadido.")
        else:
            await message.reply("ℹ️ El usuario ya está en la lista.")
    except (IndexError, ValueError):
        await message.reply("❌ Formato incorrecto. Usa: /adduser <user_id>")

async def remove_user(client, message):
    try:
        user_id_to_remove = int(message.text.split()[1])
        if user_id_to_remove in users:
            users.remove(user_id_to_remove)
            await message.reply(f"✅ Usuario {user_id_to_remove} eliminado.")
        else:
            await message.reply("ℹ️ El usuario no está en la lista.")
    except (IndexError, ValueError):
        await message.reply("❌ Formato incorrecto. Usa: /removeuser <user_id>")

# Manejador de mensajes de texto (comandos)
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
            if update_video_settings(text[len('/calidad '):]):
                await message.reply(f"✅ Configuración actualizada:\n{video_settings}")
            else:
                await message.reply("❌ Error al actualizar la configuración. Verifica el formato.")
        elif text.startswith(('/adduser', '.adduser')):
            if user_id in admin_users:
                await add_user(client, message)
        elif text.startswith(('/removeuser', '.removeuser')):
            if user_id in admin_users:
                await remove_user(client, message)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.reply("⚠️ Ocurrió un error al procesar tu solicitud.")

# Manejador para vídeos enviados directamente (sin comando)
@app.on_message(filters.video & ~filters.command)
async def handle_auto_compress(client, message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        return
    # Llamar a la función de compresión
    await compress_video(client, message)

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()