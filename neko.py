import os
import datetime
import subprocess
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# Configuración del bot
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

async def get_duration(file_path):
    """Obtiene la duración del video en segundos"""
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    try:
        duration = float(stdout.decode().strip())
    except (ValueError, TypeError):
        return 0.0
    return duration

def time_to_seconds(time_str):
    """Convierte tiempo en formato HH:MM:SS a segundos"""
    parts = time_str.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        return 0.0

def create_progress_bar(percent, bar_length=20):
    """Crea una barra de progreso visual"""
    completed = int(bar_length * percent / 100)
    remaining = bar_length - completed
    return '▰' * completed + '▱' * remaining

async def compress_video(client, message: Message):
    if message.reply_to_message and message.reply_to_message.video:
        original_video_path = await app.download_media(message.reply_to_message.video)
        original_size = os.path.getsize(original_video_path)
        await app.send_message(chat_id=message.chat.id, text=f"𝐈𝐧𝐢𝐜𝐢𝐚𝐧𝐝𝐨 𝐂𝐨𝐦𝐩𝐫𝐞𝐬𝐢𝐨𝐧..\n"
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
            
            # Obtener duración total del video
            total_duration = await get_duration(original_video_path)
            if total_duration <= 0:
                await app.send_message(chat_id=message.chat.id, text="Error: No se pudo obtener la duración del video.")
                return

            # Crear proceso FFmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Enviar mensaje de progreso inicial
            progress_message = await app.send_message(
                chat_id=message.chat.id,
                text="🗜️ Compresión iniciada...\n0% [▱▱▱▱▱▱▱▱▱▱]"
            )
            
            # Expresión regular para buscar el tiempo en la salida de FFmpeg
            time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
            last_percent = 0
            last_update = datetime.datetime.now()

            # Leer la salida de FFmpeg para obtener el progreso
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line = line.decode().strip()
                
                # Buscar la línea que contiene el tiempo actual
                time_match = time_pattern.search(line)
                if time_match:
                    current_time_str = time_match.group(1)
                    current_seconds = time_to_seconds(current_time_str)
                    percent = min(100, (current_seconds / total_duration) * 100)
                    
                    # Actualizar progreso cada 5% o cada 10 segundos
                    if percent - last_percent >= 5 or (datetime.datetime.now() - last_update).seconds >= 10:
                        last_percent = percent
                        last_update = datetime.datetime.now()
                        progress_bar = create_progress_bar(percent)
                        await progress_message.edit_text(
                            f"🗜️ Compresión en progreso...\n"
                            f"{percent:.1f}% [{progress_bar}]"
                        )
            
            # Esperar a que termine el proceso
            await process.wait()
            
            # Verificar si hubo error
            if process.returncode != 0:
                await progress_message.edit_text("❌ Error durante la compresión.")
                return
            
            # Proceso completado
            await progress_message.edit_text("✅ Compresión completada. Subiendo video...")
            
            # Obtener tamaño del video comprimido
            compressed_size = os.path.getsize(compressed_video_path)
            processing_time = datetime.datetime.now() - start_time
            processing_time_str = str(processing_time).split('.')[0]  # Sin microsegundos

            # Crear descripción del video
            description = (
                f"🗜️𝐕𝐢𝐝𝐞𝐨 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐝𝐨 𝐂𝐨𝐫𝐫𝐞𝐜𝐭𝐚𝐦𝐞𝐧𝐭𝐞📥\n"
                "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗼𝗿𝗶𝗴𝗶𝗻𝗮𝗹: {original_size // (1024 * 1024)} MB\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗰𝗼𝗺𝗽𝗿𝗶𝗺𝗶𝗱𝗼: {compressed_size // (1024 * 1024)} MB\n"
                f" ┖• 𝗧𝗶𝗲𝗺𝗽𝗼 𝗱𝗲 𝗽𝗿𝗼𝗰𝗲𝘀𝗮𝗺𝗶𝗲𝗻𝘁𝗼: {processing_time_str}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
                f"⚙️𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗰𝗶𝗼𝗻 𝘂𝘀𝗮𝗱𝗮⚙️\n"
                f"•𝑹𝒆𝒔𝒐𝒍𝒖𝒄𝒊𝒐‌𝒏:  {video_settings['resolution']}\n" 
                f"•𝑪𝑹𝑭: {video_settings['crf']}\n"
                f"•𝑭𝑷𝑺: {video_settings['fps']}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            )

            # Enviar el video comprimido
            await app.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=description
            )
            
            # Eliminar mensaje de progreso
            await progress_message.delete()

        except Exception as e:
            await app.send_message(chat_id=message.chat.id, text=f"Ocurrió un error al comprimir el video: {e}")
        finally:
            # Eliminar archivos temporales
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            if os.path.exists(compressed_video_path):
                os.remove(compressed_video_path)
    else:
        await app.send_message(chat_id=message.chat.id, text="Por favor, responde a un video para comprimirlo.")

BOT_IS_PUBLIC = os.getenv("BOT_IS_PUBLIC")

def is_bot_public():
    return BOT_IS_PUBLIC and BOT_IS_PUBLIC.lower() == "true"

@app.on_message(filters.text)
async def handle_message(client, message):
    text = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_bot_public():
        if user_id not in allowed_users:
            if chat_id not in allowed_users or user_id in ban_users:
                return

    if text.startswith(('/convert', '.convert')):
        await compress_video(client, message)
    elif text.startswith(('/calidad', '.calidad')):
        update_video_settings(text[len('/calidad '):])
        await message.reply(f"🔄 Configuración Actualizada⚙️: {video_settings}")

app.run()