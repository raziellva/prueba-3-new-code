import os
import datetime
import subprocess
import asyncio
import re
import math
from pyrogram import Client, filters, types
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import BadRequest

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración predeterminada para compresión de video
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

# Almacenar procesos activos por chat
active_compressions = {}

def update_video_settings(command: str):
    """Actualiza la configuración de compresión de video"""
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        if key in video_settings:
            video_settings[key] = value

async def download_progress(current, total, status_message):
    """Actualiza el progreso de descarga"""
    percent = current / total * 100
    bar_length = 20
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + ' ' * (bar_length - filled_length)
    try:
        await status_message.edit_text(
            f"⬇️ **Descargando video...**\n"
            f"`[{bar}] {percent:.1f}%`\n"
            f"**Descargado:** `{human_readable_size(current)}` / `{human_readable_size(total)}`"
        )
    except BadRequest:
        # Ignorar si el mensaje no cambia
        pass

async def upload_progress(current, total, status_message):
    """Actualiza el progreso de subida"""
    percent = current / total * 100
    bar_length = 20
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + ' ' * (bar_length - filled_length)
    try:
        await status_message.edit_text(
            f"⬆️ **Subiendo video comprimido...**\n"
            f"`[{bar}] {percent:.1f}%`\n"
            f"**Subido:** `{human_readable_size(current)}` / `{human_readable_size(total)}`"
        )
    except BadRequest:
        pass

def human_readable_size(size):
    """Convierte bytes a tamaño legible"""
    if size == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_name[i]}"

def get_ffmpeg_progress(output, duration):
    """Extrae el progreso de la salida de FFmpeg"""
    # Buscar el tiempo procesado actual
    time_match = re.search(r"time=(\d+:\d+:\d+\.\d+)", output)
    if not time_match or not duration:
        return 0
    
    # Convertir tiempo a segundos
    time_str = time_match.group(1)
    h, m, s = time_str.split(':')
    current_time = int(h) * 3600 + int(m) * 60 + float(s)
    
    # Calcular porcentaje
    return min(100, (current_time / duration) * 100)

async def run_ffmpeg_with_progress(command, duration, status_message, chat_id):
    """Ejecuta FFmpeg mostrando progreso"""
    process = subprocess.Popen(
        command,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Registrar proceso
    active_compressions[chat_id]['process'] = process
    
    # Leer salida en tiempo real
    last_update = datetime.datetime.now()
    while True:
        if active_compressions[chat_id].get('cancelled'):
            process.terminate()
            return False, "Cancelado por el usuario"
            
        line = process.stderr.readline()
        if not line:
            break
            
        # Actualizar progreso cada 1 segundo
        if (datetime.datetime.now() - last_update).seconds >= 1:
            progress = get_ffmpeg_progress(line, duration)
            if progress > 0:
                bar_length = 20
                filled_length = int(bar_length * progress // 100)
                bar = '█' * filled_length + ' ' * (bar_length - filled_length)
                try:
                    await status_message.edit_text(
                        f"🔧 **Comprimiendo video...**\n"
                        f"`[{bar}] {progress:.1f}%`\n"
                        f"⚙️ Usando: `{video_settings['preset']}` | CRF `{video_settings['crf']}`"
                    )
                    last_update = datetime.datetime.now()
                except BadRequest:
                    pass
    
    # Esperar a que termine el proceso
    process.wait()
    return process.returncode == 0, process.stderr.read()

def get_video_duration(file_path):
    """Obtiene la duración del video usando FFprobe"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 
             'format=duration', '-of', 
             'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except:
        return 0

async def compress_video(client: Client, message: Message):
    """Comprime videos usando FFmpeg con seguimiento de progreso"""
    status_message = None
    if message.reply_to_message and message.reply_to_message.video:
        try:
            # Mensaje de inicio
            download_msg = await message.reply("⬇️ **Iniciando descarga...**")
            
            # Descargar el video original con seguimiento
            original_video_path = await client.download_media(
                message.reply_to_message.video,
                progress=download_progress,
                progress_args=(download_msg,)
            )
            original_size = os.path.getsize(original_video_path)
            
            # Preparar ruta para video comprimido
            compressed_video_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
            
            # Obtener duración para el progreso
            video_duration = get_video_duration(original_video_path)
            
            # Construir comando FFmpeg
            ffmpeg_command = [
                'ffmpeg', '-y', '-i', original_video_path,
                '-s', video_settings['resolution'],
                '-crf', video_settings['crf'],
                '-b:a', video_settings['audio_bitrate'],
                '-r', video_settings['fps'],
                '-preset', video_settings['preset'],
                '-c:v', video_settings['codec'],
                '-progress', '-',  # Habilitar salida de progreso
                '-nostats',        # Reducir salida innecesaria
                compressed_video_path
            ]
            
            # Crear teclado para cancelación
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancelar compresión ❌", callback_data=f"cancel_{message.chat.id}")]
            ])
            
            # Enviar mensaje de estado con botón de cancelación
            status_message = await message.reply(
                "🔧 **Preparando compresión...**\n"
                f"📏 Tamaño original: {human_readable_size(original_size)}\n"
                f"⚙️ Configuración: {video_settings['resolution']} @ {video_settings['fps']}fps",
                reply_markup=keyboard
            )
            
            # Registrar proceso en activo
            active_compressions[message.chat.id] = {
                'process': None,
                'status_message_id': status_message.id,
                'cancelled': False
            }
            
            # Ejecutar compresión con seguimiento
            start_time = datetime.datetime.now()
            success, error = await run_ffmpeg_with_progress(
                ffmpeg_command, 
                video_duration,
                status_message,
                message.chat.id
            )
            
            # Verificar si fue cancelado
            if active_compressions[message.chat.id].get('cancelled'):
                await status_message.edit("❌ **Compresión cancelada** ❌")
                return
            
            # Verificar resultado
            if not success:
                raise Exception(f"Error en FFmpeg:\n{error[:1000] if error else 'Error desconocido'}")
            
            # Calcular métricas
            compressed_size = os.path.getsize(compressed_video_path)
            processing_time = datetime.datetime.now() - start_time
            compression_ratio = (1 - compressed_size/original_size) * 100
            
            # Crear descripción con resultados
            caption = (
                f"🎬 **Video Comprimido Correctamente**\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"┠ 📦 **Tamaño original:** {human_readable_size(original_size)}\n"
                f"┠ 📥 **Tamaño comprimido:** {human_readable_size(compressed_size)}\n"
                f"┠ 💯 **Reducción:** {compression_ratio:.1f}%\n"
                f"┠ ⏱️ **Tiempo procesamiento:** {str(processing_time).split('.')[0]}\n\n"
                "⚙️ **Configuración usada**\n"
                f"┠ 🖼️ Resolución: {video_settings['resolution']}\n"
                f"┠ 🎚️ CRF: {video_settings['crf']}\n"
                f"┠ 📺 FPS: {video_settings['fps']}\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            )
            
            # Enviar video comprimido con seguimiento
            upload_msg = await message.reply("⬆️ **Preparando subida...**")
            await client.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=caption,
                progress=upload_progress,
                progress_args=(upload_msg,)
            )
            await upload_msg.delete()
            
            # Eliminar mensaje de estado
            await status_message.delete()
            
        except Exception as e:
            if status_message and not active_compressions.get(message.chat.id, {}).get('cancelled'):
                await status_message.delete()
            await message.reply(f"❌ **Error en compresión**:\n`{str(e)}`")
            
        finally:
            # Limpiar procesos activos
            if message.chat.id in active_compressions:
                del active_compressions[message.chat.id]
                
            # Limpiar archivos temporales
            for path in [original_video_path, compressed_video_path]:
                if path and os.path.exists(path):
                    os.remove(path)
                    
    else:
        await message.reply("⚠️ Responde a un video para comprimirlo")

# ... (El resto del código permanece igual: cancel_compression, convert_command, quality_command, start_command)

if __name__ == "__main__":
    print("✅ Bot de compresión de videos iniciado")
    app.run()