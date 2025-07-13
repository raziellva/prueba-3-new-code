import os
import json
import datetime
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# --- Configuración del bot ---
api_id = os.getenv('API_ID') or 123456
api_hash = os.getenv('API_HASH') or "abcdef1234567890abcdef1234567890"
bot_token = os.getenv('TOKEN') or "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# --- Configuración de compresión por defecto ---
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

# --- Funciones auxiliares ---
def update_video_settings(command: str):
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        if key in video_settings:
            video_settings[key] = value

def get_video_duration(filepath):
    """Obtiene duración en segundos usando ffprobe"""
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'format=duration',
        '-of', 'json', filepath
    ], stdout=subprocess.PIPE, text=True)
    data = json.loads(result.stdout)
    return float(data['format']['duration']) if 'format' in data else None

def timestamp_to_seconds(timestamp):
    h, m, s = timestamp.split(":")
    return int(h)*3600 + int(m)*60 + float(s)

def render_progress_bar(current, total, length=20):
    ratio = min(current / total, 1.0)
    done = int(ratio * length)
    remaining = length - done
    bar = "█" * done + "─" * remaining
    return f"[{bar}] {ratio * 100:.1f}%"

# --- Comando /calidad ---
@app.on_message(filters.command(["calidad", "config"]))
async def quality_command(client, message):
    try:
        update_video_settings(message.text.split(maxsplit=1)[1])
        config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
        await message.reply(
            f"⚙️ **Configuración actualizada:**\n{config_text}\n\n"
            f"Envíame un video para comprimir automáticamente."
        )
    except Exception as e:
        await message.reply(f"❌ Error:\n`{str(e)}`")

# --- Comando /start ---
@app.on_message(filters.command(["start", "ayuda"]))
async def start_command(client, message):
    config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
    await message.reply(
        "🎥 **Video Compressor Bot activo**\n\n"
        "**Configuración actual:**\n"
        f"{config_text}\n\n"
        "Simplemente envíame un video y lo comprimiré automáticamente.\n"
        "🛠️ Desarrollado por RaziHEL"
    )

# --- Compresión automática al recibir video ---
@app.on_message(filters.video)
async def auto_compress(client: Client, message: Message):
    status = await message.reply("📤 Descargando video...")

    # Simulación visual de descarga
    for i in range(8):
        dots = "." * (i % 4)
        await status.edit_text(f"📤 Descargando video{dots}")
        await asyncio.sleep(0.5)

    start_time = datetime.datetime.now()
    original_video_path = await client.download_media(message.video)
    download_time = datetime.datetime.now() - start_time
    original_size = os.path.getsize(original_video_path)
    speed_mbps = (original_size * 8 / download_time.total_seconds()) / (1024 * 1024)

    await status.edit_text(
        f"✅ Descarga completada\n"
        f"📦 Tamaño original: {original_size // (1024 * 1024)} MB\n"
        f"⚡ Velocidad: {speed_mbps:.2f} Mbps\n"
        f"⏱️ Tiempo: {str(download_time).split('.')[0]}\n"
        f"🗜️ Iniciando compresión..."
    )

    compressed_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
    total_duration = get_video_duration(original_video_path)
    ffmpeg_command = [
        'ffmpeg', '-y', '-i', original_video_path,
        '-s', video_settings['resolution'],
        '-crf', video_settings['crf'],
        '-b:a', video_settings['audio_bitrate'],
        '-r', video_settings['fps'],
        '-preset', video_settings['preset'],
        '-c:v', video_settings['codec'],
        compressed_path
    ]

    process = subprocess.Popen(
        ffmpeg_command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )

    # Bucle de compresión con barra de progreso
    while True:
        line = process.stderr.readline()
        if "time=" in line:
            current_time = line.split("time=")[1].split(" ")[0]
            current_sec = timestamp_to_seconds(current_time)
            progress_bar = render_progress_bar(current_sec, total_duration)
            elapsed = str(datetime.timedelta(seconds=int(current_sec)))
            estimated_total = str(datetime.timedelta(seconds=int(total_duration)))

            await status.edit_text(
                f"🗜️ Comprimiendo video...\n"
                f"{progress_bar}\n"
                f"⏱️ Tiempo: {elapsed} / {estimated_total}\n"
                f"📦 Tamaño original: {original_size // (1024 * 1024)} MB\n"
            )
        if process.poll() is not None:
            break

    if process.returncode != 0:
        await status.edit_text("❌ Error en la compresión")
        return

    compressed_size = os.path.getsize(compressed_path)
    total_time = datetime.datetime.now() - start_time
    reduction = (1 - compressed_size/original_size) * 100

    caption = (
        f"🗜️ **Compresión completada** 📥\n"
        f"📦 Original: {original_size // (1024 * 1024)} MB\n"
        f"📉 Comprimido: {compressed_size // (1024 * 1024)} MB\n"
        f"📉 Reducción: {reduction:.1f}%\n"
        f"⏱️ Tiempo total: {str(total_time).split('.')[0]}\n\n"
        f"⚙️ Resolución: {video_settings['resolution']}\n"
        f"⚙️ FPS: {video_settings['fps']}\n"
        f"⚙️ CRF: {video_settings['crf']}\n\n"
        f"🛠️ Desarrollado por RaziHEL"
    )

    await client.send_video(chat_id=message.chat.id, video=compressed_path, caption=caption)
    await status.delete()

    for path in [original_video_path, compressed_path]:
        if os.path.exists(path):
            os.remove(path)

# --- Ejecutar el bot ---
if __name__ == "__main__":
    print("✅ Bot iniciado con barra de progreso en tiempo real")
    app.run()
    
