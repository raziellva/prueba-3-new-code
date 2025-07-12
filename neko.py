import os
import datetime
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Parámetros por defecto para compresión de video
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

def update_video_settings(command: str):
    """
    Actualiza video_settings con pares clave=valor válidos
    Ejemplo de comando: "resolution=1280x720 crf=28 fps=24"
    """
    for setting in command.split():
        if '=' not in setting:
            continue
        key, value = setting.split('=', 1)
        if key in video_settings:
            video_settings[key] = value

@app.on_message(filters.command("start") & filters.private)
async def handle_start(client, message):
    await message.reply("✅ Bot de compresión de video operativo.\n"
                        "Usa /convert (en respuesta a un video) para comprimir.\n"
                        "Ajusta calidad con /calidad resolución=… crf=… fps=…")

@app.on_message(filters.command("calidad") & filters.private)
async def handle_calidad(client, message: Message):
    params = message.text[len('/calidad '):]
    update_video_settings(params)
    await message.reply(f"🔧 Configuración actualizada:\n{video_settings}")

@app.on_message(filters.command("convert") & filters.private)
async def handle_convert(client, message: Message):
    # Verifica que sea respuesta a un video
    if not (message.reply_to_message and message.reply_to_message.video):
        return await message.reply("❗️ Responde a un video para iniciar la compresión.")
    
    # Descarga y muestra tamaño original
    input_path = await client.download_media(message.reply_to_message.video)
    original_mb = os.path.getsize(input_path) // (1024 * 1024)
    await client.send_message(message.chat.id, f"📚 Tamaño original: {original_mb} MB")

    # Prepara ruta de salida y comando ffmpeg
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_compressed.mkv"
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-s', video_settings['resolution'],
        '-crf', video_settings['crf'],
        '-b:a', video_settings['audio_bitrate'],
        '-r', video_settings['fps'],
        '-preset', video_settings['preset'],
        '-c:v', video_settings['codec'],
        output_path
    ]

    # Ejecuta ffmpeg y mide tiempo
    start = datetime.datetime.now()
    result = subprocess.run(ffmpeg_cmd, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        return await client.send_message(
            message.chat.id,
            f"⚠️ Error en ffmpeg:\n{result.stderr}"
        )

    # Calcula estadísticas
    compressed_mb = os.path.getsize(output_path) // (1024 * 1024)
    duration = float(subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        output_path
    ]).strip())
    elapsed = datetime.datetime.now() - start
    time_str = str(elapsed).split('.')[0]

    # Envía video comprimido con descripción
    caption = (
        f"🗜️ Video comprimido con éxito\n"
        f"┠ Original: {original_mb} MB\n"
        f"┠ Comprimido: {compressed_mb} MB\n"
        f"┖ Tiempo: {time_str}\n\n"
        f"⚙️ Ajustes usados:\n"
        f"• Resolución: {video_settings['resolution']}\n"
        f"• CRF: {video_settings['crf']}\n"
        f"• FPS: {video_settings['fps']}"
    )
    await client.send_video(message.chat.id, video=output_path, caption=caption)

    # Limpia archivos temporales
    os.remove(input_path)
    os.remove(output_path)
    
    from pyrogram import filters

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
        elif text.startswith(('/banuser', '.banuser')):
            if user_id in admin_users:
                await remove_user(client, message)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.reply("⚠️ Ocurrió un error al procesar tu solicitud.")

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()