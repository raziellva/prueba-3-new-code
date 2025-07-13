import os
import asyncio
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

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

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# — Ajustes por usuario —
video_settings = {
    "resolution":    "854x480",
    "crf":           "32",
    "audio_bitrate": "60k",
    "fps":           "18",
    "preset":        "veryfast",
    "codec":         "libx264"
}

def update_video_settings(cmd: str):
    for setting in cmd.split():
        key, value = setting.split("=")
        video_settings[key] = value

async def safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

# — Lógica de compresión de video — 
async def compress_video(client: Client, message: Message):
    if not (message.reply_to_message and message.reply_to_message.video):
        return await message.reply("Responde a un video para comprimirlo.")

    input_path = await client.download_media(message.reply_to_message.video)
    orig_mb    = os.path.getsize(input_path) // (1024*1024)
    await message.reply(f"📥 Original: {orig_mb} MB\n🗜️ Iniciando compresión…")

    base = os.path.splitext(input_path)[0]
    output_path = f"{base}_compressed.mkv"
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

    start = datetime.datetime.now()
    proc = await asyncio.create_subprocess_exec(
        *cmd, stderr=asyncio.subprocess.PIPE
    )
    # opcional: leer progreso en tiempo real
    await proc.wait()

    comp_mb = os.path.getsize(output_path) // (1024*1024)
    elapsed = str(datetime.datetime.now() - start).split(".")[0]

    caption = (
        f"✅ Comprimido correctamente\n"
        f"• Original: {orig_mb} MB\n"
        f"• Comprimido: {comp_mb} MB\n"
        f"• Tiempo: {elapsed}\n\n"
        f"⚙️ Ajustes:\n"
        f"  - Resolución: {video_settings['resolution']}\n"
        f"  - CRF: {video_settings['crf']}\n"
        f"  - FPS: {video_settings['fps']}"
    )
    await client.send_video(message.chat.id, video=output_path, caption=caption)

    await safe_remove(input_path)
    await safe_remove(output_path)

# — Manejo de comandos — 
@app.on_message(filters.text)
async def handler(client: Client, message: Message):
    user_id = message.from_user.id
    text    = message.text.strip()

    if user_id in ban_users:
        return

    if text.startswith(("/start",)):
        await message.reply("🤖 Bot operativo")
    elif text.startswith(("/convert",)):
        await compress_video(client, message)
    elif text.startswith(("/calidad",)):
        parts = text.split(maxsplit=1)
        if len(parts)==2:
            try:
                update_video_settings(parts[1])
                await message.reply(f"Ajustes actualizados:\n{video_settings}")
            except Exception:
                await message.reply("Formato inválido. Usa: /calidad key=value")
        else:
            await message.reply("Uso: /calidad key=value")

# — Ejecución — 
app.run()
