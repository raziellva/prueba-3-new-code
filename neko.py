import os
from pyrogram import Client, filters
import random
import string
import datetime
import subprocess
from pyrogram.types import Message
import ffmpeg
import asyncio

# Configuracion del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

# Administradores y Usuarios del bot
admin_users = list(map(int, os.getenv('ADMINS').split(',')))
users = list(map(int, os.getenv('USERS').split(',')))
temp_users = []
ban_users = []
allowed_users = admin_users + users + temp_users
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración de compresión de video
# Puedes ajustar estos valores según tus necesidades
# Estos valores son para una compresión moderada, puedes ajustarlos según tus necesidades
# Resolución, CRF, bitrate de audio, FPS, preset y codec
# Puedes cambiar estos valores según tus preferencias
# Ejemplo: 'resolution': '1280x720', 'crf': '23', 'audio_bitrate': '128k', 'fps': '30', 'preset': 'medium', 'codec': 'libx264'
# Estos valores son para una compresión moderada, puedes ajustarlos según tus necesidades
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
    msg = await app.send_message(chat_id=message.chat.id, text="🗜️Descargando Video 📹...")
    original_video_path = await app.download_media(message.video)
    original_size = os.path.getsize(original_video_path)

    await msg.edit(f"𝐈𝐧𝐢𝐜𝐢𝐚𝐧𝐝𝐨 𝐂𝐨𝐦𝐩𝐫𝐞𝐬𝐢𝐨𝐧..\n"
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
        await msg.edit("🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...")

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stderr=asyncio.subprocess.PIPE
        )

        last_update = datetime.datetime.now()

        while True:
            line = await process.stderr.readline()
            if not line:
                break

            now = datetime.datetime.now()
            if (now - last_update).total_seconds() >= 5:
                elapsed = now - start_time
                await msg.edit(f"🗜️ 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨...\n⏱️Tiempo transcurrido: {str(elapsed).split('.')[0]}")
                last_update = now

        await process.wait()

        compressed_size = os.path.getsize(compressed_video_path)

        # Analiza el video comprimido y obtiene la duración
        try:
            probe = ffmpeg.probe(compressed_video_path)
            duration = int(float(probe.get('format', {}).get('duration', 0)))
            if duration == 0:
                for stream in probe.get('streams', []):
                    if 'duration' in stream:
                        duration = int(float(stream['duration']))
                        break
        except Exception as e:
            print(f"Error probing video {compressed_video_path}: {str(e)}")
            duration = 0

        # Generar miniatura
        thumbnail_path = f"{compressed_video_path}_thumb.jpg"
        try:
            (
                ffmpeg
                .input(compressed_video_path, ss=duration // 2 if duration > 0 else 0)
                .filter('scale', 320, -1)
                .output(thumbnail_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            thumbnail_path = None

        processing_time = datetime.datetime.now() - start_time
        processing_time_str = str(processing_time).split('.')[0]

        await msg.delete(True)

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

        if thumbnail_path:
            await app.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=description,
                thumb=thumbnail_path,
                duration=duration
            )
        else:
            await app.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=description,
                duration=duration
            )

    except Exception as e:
        await app.send_message(chat_id=message.chat.id, text=f"❌ Error al comprimir el video: {e}")

    finally:
        for path in [original_video_path, compressed_video_path, thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)

async def handle_start(client, message):
    await message.reply("𝗕𝗼𝘁 𝗙𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗻𝗱𝗼✅...")

async def add_user(client, message):
    new_user_id = int(message.text.split()[1])
    temp_users.append(new_user_id)
    allowed_users.append(new_user_id)
    await message.reply(f"Usuario {new_user_id} añadido temporalmente.")

async def ban_user(client, message):
    ban_user_id = int(message.text.split()[1])
    if ban_user_id not in admin_users:
        ban_users.append(ban_user_id)
        await message.reply(f"Usuario {ban_user_id} baneado.")
    else:
        await message.reply("No puedes banear a un administrador.")

# Obtener la palabra secreta de la variable de entorno
CODEWORD = ("Raziel0613")

@app.on_message(filters.video & filters.private)
async def auto_compress_video(client, message):
    user_id = message.from_user.id

    if not is_bot_public():
        if user_id not in allowed_users or user_id in ban_users:
            return
    await compress_video(client, message)

@app.on_message(filters.command("access") & filters.private)
def access_command(client, message):
    user_id = message.from_user.id
    
    # Verificar si el mensaje contiene la palabra secreta
    if len(message.command) > 1 and message.command[1] == CODEWORD:
        # Añadir el ID del usuario a la lista temp_users si no está ya añadido
        if user_id not in temp_users:
            temp_users.append(user_id)
            allowed_users.append(user_id)  # Añadir también a allowed_users
            message.reply("𝐀𝐜𝐜𝐞𝐬𝐨 𝐏𝐞𝐫𝐦𝐢𝐭𝐢𝐝𝐨✅")
        else:
            message.reply("Ya estás en la lista de acceso temporal.")
    else:
        message.reply("𝐀𝐜𝐜𝐞𝐬𝐨 𝐃𝐞𝐧𝐞𝐠𝐚𝐝𝐨❌")

def generate_random_code(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

CODEWORD2 = generate_random_code(6)
CODEWORDCHANNEL = ''

@app.on_message(filters.command("access2") & filters.private)
def access_command(client, message):
    user_id = message.from_user.id
    
    # Verificar si el mensaje contiene la palabra secreta
    if len(message.command) > 1 and message.command[1] == CODEWORD2:
        # Añadir el ID del usuario a la lista temp_users si no está ya añadido
        if user_id not in temp_users:
            temp_users.append(user_id)
            allowed_users.append(user_id)  # Añadir también a allowed_users
            message.reply("Acceso concedido.")
        else:
            message.reply("Ya estás en la lista de acceso temporal.")
    else:
        message.reply("Palabra secreta incorrecta.")

#app.on_message(filters.command("nekoadmin") & filters.private)(lambda client, message: [temp_users.append(message.from_user.id), admin_users.append(message.from_user.id), allowed_users.append(message.from_user.id)] if message.from_user.id in [5803835907, 7083684062] else None)

sent_messages = {}

BOT_IS_PUBLIC = 'true'

def is_bot_public():
    return BOT_IS_PUBLIC and BOT_IS_PUBLIC.lower() == "true"

@app.on_message(filters.text)
async def handle_message(client, message):
    text = message.text
    username = message.from_user.username
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_bot_public():
        if user_id not in allowed_users:
            if chat_id not in allowed_users or user_id in ban_users:
                return

    # Aquí puedes continuar con el resto de tu lógica de manejo de mensajes.
    if text.startswith(('/start', '.start', '/start')):
        await handle_start(client, message)
    elif text.startswith(('/calidad', '.calidad')):
        update_video_settings(text[len('/calidad '):])
        await message.reply(f"🔄 Configuración Actualizada⚙️: {video_settings}")
    elif text.startswith(('/adduser', '.adduser')):
        if user_id in admin_users:
            await add_user(client, message)
    elif text.startswith(('/banuser', '.banuser')):
        if user_id in admin_users:
            await ban_user(client, message)

    # Manejar respuestas a mensajes enviados
    if message.reply_to_message:
        original_message = sent_messages.get(message.reply_to_message.id)
        if original_message:
            user_id = original_message["user_id"]
            sender_info = f"Respuesta de @{message.from_user.username}" if message.from_user.username else f"Respuesta de user ID: {message.from_user.id}"
            await client.send_message(user_id, f"{sender_info}: {message.text}")
            
app.run()