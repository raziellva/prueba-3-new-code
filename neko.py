import os
import asyncio
import datetime
import re
import time
import math
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import BadRequest

# — Configuración inicial — 
def parse_ids(envvar):
    return [int(x) for x in os.getenv(envvar, "").split(",") if x.isdigit()]

api_id     = int(os.getenv("API_ID", 0))
api_hash   = os.getenv("API_HASH", "")
bot_token  = os.getenv("TOKEN", "")
admin_users = parse_ids("ADMINS")
users       = parse_ids("USERS")
temp_users  = []
temp_chats  = []
ban_users   = []
allowed_users = admin_users + users + temp_users + temp_chats

app = Client("video_compressor", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# — Ajustes por usuario —
video_settings = {
    "resolution":    "854x480",
    "crf":           "32",
    "audio_bitrate": "60k",
    "fps":           "24",
    "preset":        "veryfast",
    "codec":         "libx264",
    "auto_compress": True  # Compresión automática activada por defecto
}

def update_video_settings(cmd: str):
    for setting in cmd.split():
        if '=' in setting:
            key, value = setting.split("=")
            if key in video_settings:
                if key == "auto_compress":
                    video_settings[key] = value.lower() == "true"
                else:
                    video_settings[key] = value

async def safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

# — Funciones de progreso —
def create_progress_bar(percentage, length=20):
    filled = "■" * round(percentage / 100 * length)
    empty = "□" * (length - len(filled))
    return f"{filled}{empty}"

def parse_duration(duration_str):
    """Convierte duración en formato 00:00:00.00 a segundos"""
    try:
        parts = duration_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    except:
        return 0

# — Lógica de compresión de video — 
async def compress_video(client: Client, message: Message, auto_mode=False):
    try:
        # Manejar mensaje de estado
        status_msg = await message.reply("📥 Descargando video...")
        
        # Descargar video
        input_path = await client.download_media(
            message.reply_to_message.video if auto_mode else message.reply_to_message,
            progress=download_progress,
            progress_args=(status_msg, "📥 Descargando...")
        )
        
        orig_size = os.path.getsize(input_path)
        orig_mb = orig_size // (1024 * 1024)
        
        # Actualizar estado
        await status_msg.edit(f"📥 Descargado: {orig_mb} MB\n🗜️ Iniciando compresión...")
        
        # Preparar ruta de salida
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_compressed.mkv"
        
        # Comando FFmpeg
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-s",  video_settings["resolution"],
            "-crf",video_settings["crf"],
            "-b:a",video_settings["audio_bitrate"],
            "-r",  video_settings["fps"],
            "-preset",video_settings["preset"],
            "-c:v", video_settings["codec"],
            output_path
        ]
        
        # Iniciar compresión
        start_time = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Variables para seguimiento de progreso
        duration = 0
        last_update = 0
        
        # Leer salida de FFmpeg en tiempo real
        while not proc.stderr.at_eof():
            line = await proc.stderr.readline()
            line = line.decode().strip()
            
            # Analizar duración total
            if "Duration:" in line:
                match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", line)
                if match:
                    duration = parse_duration(match.group(1))
            
            # Analizar progreso actual
            match = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
            if match and duration > 0:
                current_time = parse_duration(match.group(1))
                progress = (current_time / duration) * 100
                
                # Actualizar cada 5 segundos o si el progreso cambió significativamente
                if time.time() - last_update > 5 or progress == 100:
                    elapsed = time.time() - start_time
                    progress_bar = create_progress_bar(progress)
                    await status_msg.edit(
                        f"🗜️ Comprimiendo video...\n"
                        f"{progress_bar} {progress:.1f}%\n"
                        f"⏱ Tiempo transcurrido: {int(elapsed)}s\n"
                        f"📦 Tamaño original: {orig_mb} MB"
                    )
                    last_update = time.time()
        
        # Esperar finalización
        await proc.wait()
        
        # Verificar si se creó el archivo
        if not os.path.exists(output_path):
            raise Exception("La compresión falló, no se generó archivo de salida")
        
        # Obtener resultados
        comp_size = os.path.getsize(output_path)
        comp_mb = comp_size // (1024 * 1024)
        compression_ratio = 100 - (comp_size / orig_size * 100)
        elapsed = str(datetime.timedelta(seconds=int(time.time() - start_time)))
        
        # Crear caption
        caption = (
            f"✅ **Video Comprimido**\n\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"• **Original:** {orig_mb} MB\n"
            f"• **Comprimido:** {comp_mb} MB\n"
            f"• **Reducción:** {compression_ratio:.1f}%\n"
            f"• **Tiempo:** {elapsed}\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"⚙️ **Configuración**\n"
            f"  - Resolución: {video_settings['resolution']}\n"
            f"  - CRF: {video_settings['crf']}\n"
            f"  - FPS: {video_settings['fps']}"
        )
        
        # Enviar video con progreso de subida
        await status_msg.edit("📤 Subiendo video comprimido...")
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption=caption,
            progress=upload_progress,
            progress_args=(status_msg, "📤 Subiendo..."),
            reply_to_message_id=message.message_id if auto_mode else message.reply_to_message.message_id
        )
        
        # Limpiar mensajes temporales
        await status_msg.delete()
        
    except BadRequest as e:
        await message.reply(f"❌ Error al enviar video: {str(e)}")
    except Exception as e:
        await message.reply(f"❌ Error durante la compresión: {str(e)}")
    finally:
        # Limpieza
        await safe_remove(input_path)
        await safe_remove(output_path)

# — Callbacks de progreso —
async def download_progress(current, total, status_msg, text):
    percentage = (current / total) * 100
    progress_bar = create_progress_bar(percentage)
    mb_current = current // (1024 * 1024)
    mb_total = total // (1024 * 1024)
    
    try:
        await status_msg.edit(
            f"{text}\n"
            f"{progress_bar} {percentage:.1f}%\n"
            f"📥 {mb_current}/{mb_total} MB"
        )
    except:
        pass

async def upload_progress(current, total, status_msg, text):
    percentage = (current / total) * 100
    progress_bar = create_progress_bar(percentage)
    mb_current = current // (1024 * 1024)
    mb_total = total // (1024 * 1024)
    
    try:
        await status_msg.edit(
            f"{text}\n"
            f"{progress_bar} {percentage:.1f}%\n"
            f"📤 {mb_current}/{mb_total} MB"
        )
    except:
        pass

# — Compresión automática —
async def auto_compress(client: Client, message: Message):
    if (message.video and 
        video_settings["auto_compress"] and 
        message.from_user.id not in ban_users and
        message.video.file_size > 5 * 1024 * 1024):  # Solo videos >5MB
        
        # Notificar al usuario
        notice = await message.reply(
            "🎥 Video detectado. Comprimiendo automáticamente...\n"
            "ℹ️ Para desactivar: /auto false",
            reply_to_message_id=message.message_id
        )
        
        # Comprimir
        await compress_video(client, notice, auto_mode=True)
        
        # Eliminar notificación
        await notice.delete()

# — Manejo de comandos — 
@app.on_message(filters.text)
async def command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text    = message.text.strip().lower()
    
    if user_id in ban_users:
        return
    
    if text.startswith("/start"):
        await message.reply(
            "🤖 **Bot de Compresión de Videos**\n\n"
            "Envía un video o responde a uno con /convert\n\n"
            "⚙️ **Comandos disponibles:**\n"
            "- /convert: Comprime el video respondido\n"
            "- /calidad: Cambia ajustes de compresión\n"
            "- /auto: Activa/desactiva compresión automática\n"
            "- /settings: Muestra configuración actual"
        )
    
    elif text.startswith("/convert") and message.reply_to_message and message.reply_to_message.video:
        await compress_video(client, message)
    
    elif text.startswith("/calidad"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            try:
                update_video_settings(parts[1])
                await message.reply(
                    f"⚙️ **Ajustes actualizados:**\n"
                    f"Resolución: `{video_settings['resolution']}`\n"
                    f"CRF: `{video_settings['crf']}`\n"
                    f"FPS: `{video_settings['fps']}`\n"
                    f"Preset: `{video_settings['preset']}`\n"
                    f"Auto: `{'✅' if video_settings['auto_compress'] else '❌'}`"
                )
            except Exception:
                await message.reply("❌ Formato inválido. Usa: `/calidad key=value`")
        else:
            await message.reply("ℹ️ Uso: `/calidad key=value`\nEj: `/calidad resolution=1280x720 crf=28`")
    
    elif text.startswith("/auto"):
        parts = text.split()
        if len(parts) > 1:
            state = parts[1].lower()
            if state in ["true", "on", "si", "yes"]:
                video_settings["auto_compress"] = True
                await message.reply("✅ **Compresión automática ACTIVADA**")
            elif state in ["false", "off", "no"]:
                video_settings["auto_compress"] = False
                await message.reply("❌ **Compresión automática DESACTIVADA**")
            else:
                await message.reply("❌ Valor inválido. Usa: `/auto on` o `/auto off`")
        else:
            await message.reply(f"🔄 Compresión automática: `{'ACTIVA' if video_settings['auto_compress'] else 'INACTIVA'}`")
    
    elif text.startswith("/settings"):
        await message.reply(
            f"⚙️ **Configuración Actual:**\n"
            f"- Resolución: `{video_settings['resolution']}`\n"
            f"- CRF: `{video_settings['crf']}`\n"
            f"- FPS: `{video_settings['fps']}`\n"
            f"- Preset: `{video_settings['preset']}`\n"
            f"- Auto-compresión: `{'✅' if video_settings['auto_compress'] else '❌'}`"
        )

# — Manejo de videos —
@app.on_message(filters.video)
async def video_handler(client: Client, message: Message):
    await auto_compress(client, message)

# — Ejecución — 
if __name__ == "__main__":
    print("Bot de compresión de videos iniciado...")
    app.run()