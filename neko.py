import os
import datetime
import subprocess
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
            process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True)
            await app.send_message(chat_id=message.chat.id, text="🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...")
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            # Recuperar tamaño y duración
            compressed_size = os.path.getsize(compressed_video_path)
            duration = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                                                 compressed_video_path])
            duration = float(duration.strip())
            duration_str = str(datetime.timedelta(seconds=duration))
            processing_time = datetime.datetime.now() - start_time
            processing_time_str = str(processing_time).split('.')[0]  # Formato sin microsegundos
            # Descripción para el video comprimido
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
            # Enviar el video comprimido con la descripción
            await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description)
        except Exception as e:
            await app.send_message(chat_id=message.chat.id, text=f"Ocurrió un error al comprimir el video: {e}")
        finally:
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