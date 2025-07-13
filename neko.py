import os
import datetime
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración predeterminada de compresión
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

def update_video_settings(command: str):
    """Actualiza configuración usando clave=valor"""
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        if key in video_settings:
            video_settings[key] = value

@app.on_message(filters.command(["calidad", "config"]))
async def quality_command(client, message):
    """Actualiza los parámetros de calidad"""
    try:
        update_video_settings(message.text.split(maxsplit=1)[1])
        config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
        await message.reply(
            f"⚙️ **Configuración actualizada**\n\n{config_text}\n\n"
            f"Ahora puedes enviarme un video para comprimirlo automáticamente."
        )
    except Exception as e:
        await message.reply(f"❌ Error al actualizar configuración:\n`{str(e)}`")

@app.on_message(filters.command(["start", "ayuda"]))
async def start_command(client, message):
    """Muestra parámetros actuales de compresión"""
    config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
    await message.reply(
        "🎥 **Bienvenido al Video Compressor Bot**\n\n"
        "**Configuración actual de compresión:**\n"
        f"{config_text}\n\n"
        "📩 Simplemente envíame un video y lo comprimiré automáticamente.\n"
        "🛠️ Desarrollado por RaziHEL"
    )

@app.on_message(filters.video)
async def auto_compress(client: Client, message: Message):
    """Compresión automática con métricas detalladas"""
    status = await message.reply("📤 Descargando video...")

    # Simulación de progreso de descarga
    for i in range(8):
        dots = "." * (i % 4)
        await status.edit_text(f"📤 Descargando video{dots}")
        await asyncio.sleep(0.5)

    start_time = datetime.datetime.now()
    original_video_path = await client.download_media(message.video)
    download_time = datetime.datetime.now() - start_time
    original_size = os.path.getsize(original_video_path)
    speed_bps = original_size / download_time.total_seconds()
    speed_mbps = speed_bps * 8 / (1024 * 1024)

    await status.edit_text(
        f"✅ Descarga completada\n"
        f"📦 Peso original: {original_size // (1024 * 1024)} MB\n"
        f"⚡ Velocidad: {speed_mbps:.2f} Mbps\n"
        f"⏱️ Tiempo: {str(download_time).split('.')[0]}\n"
        f"🗜️ Iniciando compresión..."
    )

    compressed_video_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
    ffmpeg_command = [
        'ffmpeg', '-y', '-i', original_video_path,
        '-s', video_settings['resolution'],
        '-crf', video_settings['crf'],
        '-b:a', video_settings['audio_bitrate'],
        '-r', video_settings['fps'],
        '-preset', video_settings['preset'],
        '-c:v', video_settings['codec'],
        compressed_video_path
    ]

    process = subprocess.Popen(
        ffmpeg_command,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )

    while True:
        line = process.stderr.readline()
        if "time=" in line:
            timestamp_str = line.split("time=")[1].split(" ")[0]
            await status.edit_text(f"🗜️ Comprimiendo... Tiempo transcurrido: `{timestamp_str}`")
        if process.poll() is not None:
            break

    if process.returncode != 0:
        await status.edit_text("❌ Error en la compresión")
        return

    compressed_size = os.path.getsize(compressed_video_path)
    total_time = datetime.datetime.now() - start_time
    reduction = (1 - compressed_size/original_size) * 100

    caption = (
        f"🗜️ **Video comprimido exitosamente** 📥\n"
        f"📦 Original: {original_size // (1024 * 1024)} MB\n"
        f"📉 Comprimido: {compressed_size // (1024 * 1024)} MB\n"
        f"📉 Reducción: {reduction:.1f}%\n"
        f"⏱️ Tiempo total: {str(total_time).split('.')[0]}\n\n"
        f"⚙️ Resolución: {video_settings['resolution']}\n"
        f"⚙️ FPS: {video_settings['fps']}\n"
        f"⚙️ CRF: {video_settings['crf']}\n\n"
        f"🛠️ Desarrollado por RaziHEL"
    )

    await client.send_video(
        chat_id=message.chat.id,
        video=compressed_video_path,
        caption=caption
    )

    await status.delete()

    for path in [original_video_path, compressed_video_path]:
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    print("✅ Bot de compresión automática iniciado")
    app.run()
