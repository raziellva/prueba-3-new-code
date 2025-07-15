import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import ffmpeg
import random
import string
from datetime import timedelta, datetime
import psutil
import shutil
import platform
from pyrogram.types import Message
import ffmpeg
import asyncio
from time import time
from pymongo import MongoClient
from config import *

compression_queue = asyncio.Queue()
processing_task = None

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]
users_col = db["users"]

# Asegúrate de que la colección de usuarios existe
if "users" not in db.list_collection_names():
    db.create_collection("users")

# Añadir o mantener admins válidos
for admin in ADMINS_IDS:
    users_col.update_one(
        {"user_id": admin},
        {
            "$set": {
                "role": "admin"
            }
        },
        upsert=True
    )

# Buscar admins en BD que NO estén en ADMINS_IDS y degradarlos
db_admins = users_col.find({"role": "admin"})
for user in db_admins:
    if user["user_id"] not in ADMINS_IDS:
        users_col.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"role": "temp"}}  # o puedes usar "temp" si lo prefieres
        )

# Administradores y Usuarios del bot
admin_users = [doc["user_id"] for doc in users_col.find({"role": "admin"})]
users = [doc["user_id"] for doc in users_col.find({"role": "user"})]
temp_users = [doc["user_id"] for doc in users_col.find({"role": "temp"})]
ban_users = [doc["user_id"] for doc in users_col.find({"role": "banned"})]
allowed_users = admin_users + users + temp_users
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

def load_user_settings(user_id):
    user = users_col.find_one({"user_id": user_id})
    return user.get("compression_settings", video_settings.copy()) if user else video_settings.copy()

def update_video_settings(command: str):
    global video_settings
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        video_settings[key] = value

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.2f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f%s%s" % (num, "Yi", suffix)

def create_progress_bar(current, total, proceso, length=15):
    if total == 0:
        total = 1
    percent = current / total
    filled = int(length * percent)
    bar = '▰' * filled + '▱' * (length - filled)
    return (
        f'┠ **BOT**\n'
        f'┠ [{bar}] {round(percent * 100)}%\n'
        f'┠ **Procesado:** {sizeof_fmt(current)}/{sizeof_fmt(total)}\n'
        f'┠ **Estado:** __#{proceso}__'
    )

last_progress_update = {}

async def progress_callback(current, total, msg, proceso, start_time):
    try:
        now = datetime.now()
        key = msg.chat.id, msg.id
        last_time = last_progress_update.get(key)

        if last_time and (now - last_time) < timedelta(seconds=5):
            return  # No han pasado 5 segundos, omitir actualización

        last_progress_update[key] = now  # Actualiza el último tiempo

        elapsed = time() - start_time
        percentage = current / total
        speed = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        progress_bar = create_progress_bar(current, total, proceso)
        await msg.edit(
            f"{progress_bar}\n"
            f"┠ **Velocidad:** {sizeof_fmt(speed)}/s\n"
            f"┖ **ETA:** {int(eta)}s"
        )
    except Exception as e:
        print(f"Progress update error: {e}")

async def compress_video(client, message: Message):
    start = time()
    msg = await app.send_message(chat_id=message.chat.id, text="🗜️Descargando Video 📹...")
    original_video_path = await app.download_media(message.video, progress=progress_callback, progress_args=(msg, "DESCARGA", start))
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
        start_time = datetime.now()
        await msg.edit("🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...")

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stderr=asyncio.subprocess.PIPE
        )

        last_update = datetime.now()

        updater_task = asyncio.create_task(update_elapsed_time(msg, start_time, process))
        await process.wait()
        updater_task.cancel()

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

        processing_time = datetime.now() - start_time
        processing_time_str = str(processing_time).split('.')[0]

        await msg.delete(True)

        description = (
            f"🗜️𝐕𝐢𝐝𝐞𝐨 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐝𝐨 𝐂𝐨𝐫𝐫𝐞𝐜𝐭𝐚𝐦𝐞𝐧𝐭𝐞📥\n"
            f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗼𝗿𝗶𝗴𝗶𝗻𝗮𝗹: {sizeof_fmt(original_size)}\n"
            f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗰𝗼𝗺𝗽𝗿𝗶𝗺𝗶𝗱𝗼: {sizeof_fmt(compressed_size)}\n"
            f" ┖• 𝗧𝗶𝗲𝗺𝗽𝗼 𝗱𝗲 𝗽𝗿𝗼𝗰𝗲𝘀𝗮𝗺𝗶𝗲𝗻𝘁𝗼: {processing_time_str}\n"
        )

        if thumbnail_path:
            start = time()
            msg = await app.send_message(chat_id=message.chat.id, text="📤 Subiendo video comprimido...")
            await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description, thumb=thumbnail_path, duration=duration, progress=progress_callback, progress_args=(msg, "SUBIDA", start))
            await msg.delete(True)
        else:
            start = time()
            msg = await app.send_message(chat_id=message.chat.id, text="📤 Subiendo video comprimido sin miniatura...")
            await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description, duration=duration, progress=progress_callback, progress_args=(msg, "SUBIDA", start)
            )
            await msg.delete(True)

    except Exception as e:
        await app.send_message(chat_id=message.chat.id, text=f"❌ Error al comprimir el video: {e}")

    for pat in [original_video_path, compressed_video_path, thumbnail_path]:
            if pat and os.path.exists(pat):
                os.remove(pat)

@app.on_message(filters.command("status") & filters.user(admin_users))
async def server_status(client, message):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    os_info = f"{platform.system()} {platform.release()}"

    info = (
        f"🖥 **Información del Servidor** 🧠\n\n"
        f"📟 **Sistema:** {os_info}\n"
        f"🔢 **CPU:** {cpu}%\n"
        f"🧠 **RAM:** {sizeof_fmt(ram.used)} / {sizeof_fmt(ram.total)} ({ram.percent}%)\n"
        f"💽 **Almacenamiento:** {sizeof_fmt(disk.used)} / {sizeof_fmt(disk.total)} ({int(disk.used / disk.total * 100)}%)\n"
    )
    await message.reply(info)

@app.on_message(filters.command("settings") & filters.private)
async def settings_menu(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Animes/Animados", callback_data="anime")],
        [InlineKeyboardButton("🎬 Reels/Videos cortos", callback_data="reels")],
        [InlineKeyboardButton("🖥 Películas/Series HD", callback_data="hd")],
        [InlineKeyboardButton("📼 Películas/Series LOW", callback_data="low")],
        [InlineKeyboardButton("📣 Shows/Reality", callback_data="shows")],
        [InlineKeyboardButton("🛠 General V1", callback_data="generalv1")],
        [InlineKeyboardButton("🛠 General V2", callback_data="generalv2")]
    ])

    await message.reply("🔷 Elige tu configuración de compresión preferida:", reply_markup=keyboard)

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    config_map = {
        "anime": "resolution=720x420 crf=30 audio_bitrate=60k fps=25 preset=veryfast codec=libx264",
        "reels": "resolution=420x720 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264",
        "hd": "resolution=854x480 crf=25 audio_bitrate=60k fps=30 preset=veryfast codec=libx264",
        "low": "resolution=854x480 crf=32 audio_bitrate=60k fps=18 preset=veryfast codec=libx264",
        "shows": "resolution=854x480 crf=35 audio_bitrate=60k fps=18 preset=veryfast codec=libx264",
        "generalv1": "resolution=720x420 crf=28 audio_bitrate=64k fps=25 preset=veryfast codec=libx264",
        "generalv2": "resolution=740x480 crf=30 audio_bitrate=65k fps=24 preset=veryfast codec=libx264"
    }

    config = config_map.get(callback_query.data)

    if config:
        update_video_settings(config)

        # DEBUG opcional
        print(f"[DEBUG] Guardando configuración para {callback_query.from_user.id}: {video_settings}")

        users_col.update_one(
            {"user_id": callback_query.from_user.id},
            {"$set": {"compression_settings": video_settings}},
            upsert=True
        )

        await callback_query.message.edit_text(f"⚙️ Configuración actualizada:\n`{config}`")
    else:
        await callback_query.answer("Opción inválida.", show_alert=True)

async def handle_start(client, message):
    await app.send_photo(chat_id=message.chat.id, photo="logo.jpg", caption="🗜️𝐁𝐨𝐭 𝐂𝐨𝐦𝐩𝐫𝐞𝐬𝐨𝐫 𝐃𝐞 𝐕í𝐝𝐞𝐨𝐬🎬\n\nBienvenido a nuestro bot, actualmente esta en desarrollo y estamos intentando implementar actualualizaciones lo mas regular posible para su correcto funcionamiento.\n\nUsa el comando /settings para elegir la calidad que prefieres.")

async def add_user(client, message):
    new_user_id = int(message.text.split()[1])
    temp_users.append(new_user_id)
    allowed_users.append(new_user_id)
    users_col.update_one(
        {"user_id": new_user_id},
        {"$set": {"role": "temp"}},
        upsert=True
    )
    await message.reply(f"Usuario {new_user_id} añadido temporalmente.")

async def ban_user(client, message):
    ban_user_id = int(message.text.split()[1])
    if ban_user_id not in admin_users:
        ban_users.append(ban_user_id)
        users_col.update_one(
            {"user_id": ban_user_id},
            {"$set": {"role": "banned"}},
            upsert=True
        )
        await message.reply(f"Usuario {ban_user_id} baneado.")
    else:
        await message.reply("No puedes banear a un administrador.")

async def update_elapsed_time(msg, start_time, process):
    while not process.returncode:
        elapsed = datetime.now() - start_time
        try:
            await msg.edit(f"🗜️ 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨...\n⏱️Tiempo transcurrido: {str(elapsed).split('.')[0]}")
        except:
            pass
        await asyncio.sleep(5)

async def process_compression_queue():
    while True:
        client, message, wait_msg = await compression_queue.get()

        try:
            await wait_msg.edit("🗜️ Iniciando la compresión de tu video...")
            await wait_msg.delete(True)
            await compress_video(client, message)
        except Exception as e:
            await app.send_message(message.chat.id, f"❌ Error al procesar el video: {str(e)}")
        finally:
            compression_queue.task_done()
            mongo_client[DATABASE_NAME]["pending"].delete_one({"video_id": message.video.file_id})

async def load_pending_from_mongo():
    pendientes = mongo_client[DATABASE_NAME]["pending"].find().sort("timestamp", 1)

    for item in pendientes:
        try:
            user_id = item["user_id"]
            chat_id = item["chat_id"]
            message_id = item["message_id"]

            message = await app.get_messages(chat_id, message_id)
            wait_msg = await app.send_message(chat_id, f"📤 Recuperado desde cola persistente.")

            await compression_queue.put((app, message, wait_msg))
        except Exception as e:
            print(f"[ERROR] No se pudo cargar item de la cola persistente: {e}")

# Obtener la palabra secreta de la variable de entorno
CODEWORD = ("Raziel0613")

@app.on_message(filters.video & filters.private)
async def auto_compress_video(client, message):
    global processing_task

    if processing_task is None or processing_task.done():
        processing_task = asyncio.create_task(process_compression_queue())

    user_id = message.from_user.id

    if not is_bot_public():
        if user_id not in allowed_users or user_id in ban_users:
            await message.reply("🚫 No tienes permiso para usar este bot.")
            return

    global video_settings
    video_settings = load_user_settings(user_id)

    queue_position = compression_queue.qsize()
    if processing_task is not None and not processing_task.done():
        queue_position += 1

    wait_msg = await message.reply(f"⏳ Tu video ha sido añadido a la cola.\n📊 Posición en cola: {queue_position}")

    # Guardar en MongoDB
    mongo_client[DATABASE_NAME]["pending"].insert_one({
        "user_id": user_id,
        "video_id": message.video.file_id,
        "file_name": message.video.file_name,
        "chat_id": message.chat.id,
        "message_id": message.id,
        "timestamp": datetime.utcnow()
    })

    await compression_queue.put((client, message, wait_msg))


@app.on_message(filters.command("cola") & filters.user(admin_users))
async def ver_cola(client, message):
    cola = list(mongo_client[DATABASE_NAME]["pending"].find().sort("timestamp", 1))

    if not cola:
        await message.reply("📭 La cola está vacía.")
        return

    respuesta = "📋 **Cola de Compresión Activa (Persistente)**\n\n"
    for i, item in enumerate(cola, 1):
        user_id = item["user_id"]
        file_name = item.get("file_name", "¿?")
        tiempo = item.get("timestamp")
        tiempo_str = tiempo.strftime("%H:%M:%S") if tiempo else "¿?"
        respuesta += f"{i}. 👤 ID: `{user_id}` | 📁 {file_name} | 🕒 {tiempo_str}\n"

    await message.reply(respuesta)

@app.on_message(filters.command("task_status") & filters.user(admin_users))
async def task_status(_, message):
    global processing_task
    if processing_task is None:
        await message.reply("❌ Task no está inicializada.")
    elif processing_task.done():
        await message.reply(f"⚠️ Task terminó con error: {processing_task.exception()}")
    else:
        await message.reply("✅ Task está activa y funcionando.")

@app.on_message(filters.command("access") & filters.private)
def access_command(client, message):
    user_id = message.from_user.id
    if len(message.command) > 1 and message.command[1] == CODEWORD:
        if user_id not in temp_users:
            temp_users.append(user_id)
            allowed_users.append(user_id)
            users_col.update_one(
                {"user_id": user_id},
                {"$set": {"role": "temp"}},
                upsert=True
            )
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

sent_messages = {}

BOT_IS_PUBLIC = 'false'

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
                await message.reply("🚫 No tienes permiso para usar este bot.")
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
            await app.send_message(user_id, f"{sender_info}: {message.text}")

#app.start()
#app.loop.run_forever()

@app.on_message(filters.command("start") & filters.user(admin_users))
async def startup_command(client, message):
    global processing_task
    msg = await message.reply("🔄 Iniciando procesamiento de la cola...")

    # 1. Cargar pendientes desde Mongo
    pendientes = mongo_client[DATABASE_NAME]["pending"].find().sort("timestamp", 1)
    for item in pendientes:
        try:
            user_id = item["user_id"]
            chat_id = item["chat_id"]
            message_id = item["message_id"]

            msg = await app.get_messages(chat_id, message_id)
            wait_msg = await app.send_message(chat_id, f"📤 Recuperado desde cola persistente.")
            await compression_queue.put((app, msg, wait_msg))
        except Exception as e:
            print(f"[ERROR al cargar de Mongo] {e}")

    # 2. Iniciar el procesador
    if processing_task is None or processing_task.done():
        processing_task = asyncio.create_task(process_compression_queue())
    await msg.edit("✅ Procesamiento de cola iniciado.")

app.run()
