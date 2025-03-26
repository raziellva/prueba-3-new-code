import os
import re
import time
import random
import string
import hashlib
import py7zr
import shutil
import zipfile
import smtplib
import requests
import datetime
import subprocess
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from email.message import EmailMessage
from pyrogram import Client, filters
from pyrogram.types import Message
from moodleclient import upload_token

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')
BOT_IS_PUBLIC = os.getenv("BOT_IS_PUBLIC", "").lower() == "true"

# Configuración de usuarios
admin_users = list(map(int, os.getenv('ADMINS', '').split(','))
users = list(map(int, os.getenv('USERS', '').split(','))
temp_users = []
temp_chats = []
ban_users = []
allowed_users = admin_users + users + temp_users + temp_chats

# Configuración de compresión
compression_size = 10  # Tamaño por defecto en MB
user_comp = {}
user_emails = {}
image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

# Configuración de video
video_settings = {
    'resolution': '854x480',
    'crf': '35',
    'audio_bitrate': '60k',
    'fps': '15',
    'preset': 'veryfast',
    'codec': 'libx264'
}

# Inicialización del cliente Pyrogram
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# --------------------------
# Funciones de Utilidad
# --------------------------

def clean_string(s):
    """Limpia una cadena de caracteres no deseados"""
    return re.sub(r'[^a-zA-Z0-9\[\] ]', '', s)

def hash_file(file_path):
    """Calcula el hash MD5 de un archivo"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def display_progress(user, user_id, total_size, downloaded_size, start_time):
    """Genera un mensaje de progreso para descargas"""
    progress_bar_length = 25
    progress = downloaded_size / total_size if total_size > 0 else 0
    filled_length = int(progress_bar_length * progress)
    bar = '█' * filled_length + '□' * (progress_bar_length - filled_length)
    
    past_time = int(time.time() - start_time)
    eta = int((total_size - downloaded_size) / (downloaded_size / past_time)) if downloaded_size > 0 else 0
    speed = downloaded_size / past_time if past_time > 0 else 0
    
    return (
        f"#Zee1...(Processing)\n"
        f"{bar} [{progress:.2%}]\n"
        f"┠• Done: {downloaded_size:.2f} MiB of {total_size:.2f} MiB\n"
        f"┠• Status: #Download 📥\n"
        f"┠• Past: {past_time}s\n"
        f"┠• Eta: {eta // 60}m:{eta % 60}s\n"
        f"┠• Speed: {speed:.2f} MiB/s\n"
        f"┠• User: {user}\n"
        f"┖• ID: {user_id}\n\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
    )

# --------------------------
# Funciones de Compresión
# --------------------------

def compressfile(file_path, part_size):
    """Comprime un archivo en partes de tamaño especificado"""
    parts = []
    part_size *= 1024 * 1024  # Convertir a bytes
    archive_path = f"{file_path}.7z"
    
    with py7zr.SevenZipFile(archive_path, 'w') as archive:
        archive.write(file_path, os.path.basename(file_path))
    
    with open(archive_path, 'rb') as archive:
        part_num = 1
        while True:
            part_data = archive.read(part_size)
            if not part_data:
                break
            part_file = f"{archive_path}.{part_num:03d}"
            with open(part_file, 'wb') as part:
                part.write(part_data)
            parts.append(part_file)
            part_num += 1
    
    return parts

async def handle_compress(client, message, username):
    """Maneja el comando de compresión de archivos"""
    try:
        os.system("rm -rf ./server/*")
        await message.reply("Descargando el archivo para comprimirlo...")

        def get_file_name(msg):
            """Obtiene el nombre del archivo basado en el tipo de mensaje"""
            if msg.reply_to_message.document:
                return os.path.basename(msg.reply_to_message.document.file_name)[:50]
            elif msg.reply_to_message.photo:
                return f"{''.join(random.choices(string.ascii_letters + string.digits, k=20))}.jpg"
            elif msg.reply_to_message.audio:
                return f"{''.join(random.choices(string.ascii_letters + string.digits, k=20))}.mp3"
            elif msg.reply_to_message.video:
                return f"{''.join(random.choices(string.ascii_letters + string.digits, k=20))}.mp4"
            elif msg.reply_to_message.sticker:
                return f"{''.join(random.choices(string.ascii_letters + string.digits, k=20))}.webp"
            return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

        # Descargar archivo
        file_name = get_file_name(message)
        file_path = await client.download_media(message.reply_to_message, file_name=file_name)
        await message.reply("Comprimiendo el archivo...")
        sizd = user_comp.get(username, 10)

        # Comprimir archivo
        parts = compressfile(file_path, sizd)
        original_hashes = [hash_file(part) for part in parts]
        
        await message.reply("Se ha comprimido el archivo, ahora se enviarán las partes")

        # Enviar partes
        for part, original_hash in zip(parts, original_hashes):
            try:
                await client.send_document(message.chat.id, part)
                received_hash = hash_file(part)
                if received_hash != original_hash:
                    await message.reply(f"El archivo {part} recibido está corrupto.")
            except Exception as e:
                print(f"Error al enviar la parte {part}: {e}")
                await message.reply(f"Error al enviar la parte {part}: {e}")

        await message.reply("Esas son todas las partes")
        shutil.rmtree('server')
        os.mkdir('server')

    except Exception as e:
        await message.reply(f'Error: {str(e)}')

# --------------------------
# Funciones de Video
# --------------------------

def update_video_settings(command: str):
    """Actualiza la configuración de compresión de video"""
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        video_settings[key] = value

async def compress_video(client, message: Message):
    """Comprime un video según la configuración establecida"""
    if not (message.reply_to_message and message.reply_to_message.video):
        return await message.reply("Por favor, responde a un video para comprimirlo.")

    try:
        original_video_path = await app.download_media(message.reply_to_message.video)
        original_size = os.path.getsize(original_video_path)
        
        # Mensaje inicial con barra de progreso
        start_msg = await message.reply(
            "🗜️ **Iniciando Compresión de Video**\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            "🔄 **Progreso:** □□□□□□□□□□ 0%\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"
        )

        compressed_video_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
        ffmpeg_command = [
            'ffmpeg', '-y', '-i', original_video_path,
            '-s', video_settings['resolution'], '-crf', video_settings['crf'],
            '-b:a', video_settings['audio_bitrate'], '-r', video_settings['fps'],
            '-preset', video_settings['preset'], '-c:v', video_settings['codec'],
            compressed_video_path
        ]
        
        start_time = datetime.datetime.now()
        process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True, universal_newlines=True)
        
        # Obtener duración total del video
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", 
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
            original_video_path
        ])
        total_duration = float(duration.strip())
        
        last_update_time = 0
        progress_pattern = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.\d{2}')
        
        while True:
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            
            # Actualizar progreso
            match = progress_pattern.search(output)
            if match:
                hours, minutes, seconds = map(int, match.groups())
                current_time = hours * 3600 + minutes * 60 + seconds
                progress_percent = min(100, int((current_time / total_duration) * 100))
                
                if progress_percent >= last_update_time + 5 or (datetime.datetime.now() - start_time).seconds >= 5:
                    last_update_time = progress_percent
                    progress_bar = "■" * (progress_percent // 5) + "□" * (20 - (progress_percent // 5))
                    
                    try:
                        await start_msg.edit(
                            "🗜️ **Comprimiendo Video**\n"
                            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                            f"🔄 **Progreso:** [{progress_bar}] [{progress_percent}%]\n"
                            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"
                        )
                    except:
                        pass

        # Calcular métricas finales
        compressed_size = os.path.getsize(compressed_video_path)
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            compressed_video_path
        ])
        duration = float(duration.strip())
        processing_time = datetime.datetime.now() - start_time
        processing_time_str = str(processing_time).split('.')[0]

        await start_msg.delete()

        description = (
            "🗜️𝐕𝐢𝐝𝐞𝐨 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐝𝐨 𝐂𝐨𝐫𝐫𝐞𝐜𝐭𝐚𝐦𝐞𝐧𝐭𝐞📥\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"┠• **Tamaño Original:** {original_size // (1024 * 1024)} MB\n"
            f"┠• **Tamaño Comprimido:** {compressed_size // (1024 * 1024)} MB\n"
            f"┖• **Tiempo de Proceso:** {processing_time_str}\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            f"⚙️𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗰𝗶𝗼𝗻 𝘂𝘀𝗮𝗱𝗮⚙️\n"
            f"•𝑹𝒆𝒔𝒐𝒍𝒖𝒄𝒊𝒐‌𝒏:  {video_settings['resolution']}\n" 
            f"•𝑪𝑹𝑭: {video_settings['crf']}\n"
            f"•𝑭𝑷𝑺: {video_settings['fps']}\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        )
        
        await app.send_document(chat_id=message.chat.id, document=compressed_video_path, caption=description)

    except Exception as e:
        await app.send_message(chat_id=message.chat.id, text=f"Ocurrió un error al comprimir el video: {e}")
    finally:
        if os.path.exists(original_video_path):
            os.remove(original_video_path)
        if os.path.exists(compressed_video_path):
            os.remove(compressed_video_path)

# --------------------------
# Funciones de Descarga
# --------------------------

async def download_single_file(client, message, url):
    """Descarga un archivo individual con progreso"""
    filename = url.split('/')[-1]
    user = message.from_user.username or str(message.from_user.id)
    user_id = message.from_user.id
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('Content-Length', 0)) / (1024 * 1024)
                downloaded_size = 0
                block_size = 1024 * 1024
                progress_message = await message.reply(
                    display_progress(user, user_id, total_size, downloaded_size, start_time)
                )
                
                async with aiofiles.open(filename, 'wb') as f:
                    async for data in response.content.iter_chunked(block_size):
                        await f.write(data)
                        downloaded_size += len(data) / (1024 * 1024)
                        
                        if time.time() - start_time % 0.5 < 0.1:
                            try:
                                await progress_message.edit(
                                    display_progress(user, user_id, total_size, downloaded_size, start_time))
                            except:
                                pass
                
                await progress_message.edit(
                    f"✅ **Descarga completada!**\n"
                    f"┠• Archivo: `{filename}`\n"
                    f"┠• Tamaño: {total_size:.2f} MiB\n"
                    f"┠• Tiempo: {int(time.time() - start_time)}s\n"
                    f"┖• Usuario: {user}")

    except Exception as e:
        error_msg = f"❌ **Error en la descarga**\n┖• Razón: {str(e)}"
        if 'progress_message' in locals():
            await progress_message.edit(error_msg)
        else:
            await message.reply(error_msg)
        return

    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=filename,
            caption=f"📤 {filename} ({total_size:.2f} MiB)"
        )
    except Exception as e:
        await message.reply(f"Error al enviar el archivo: {str(e)}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

async def download_file(client, message):
    """Maneja el comando de descarga de archivos"""
    if (message.reply_to_message and message.reply_to_message.document 
        and message.reply_to_message.document.file_name.endswith('.txt')):
        file_path = await client.download_media(message.reply_to_message.document)
        
        async with aiofiles.open(file_path, 'r') as f:
            links = await f.readlines()
        
        for link in links:
            link = link.strip()
            if link:
                await download_single_file(client, message, link)
    else:
        url = message.text.split(maxsplit=1)[1]
        await download_single_file(client, message, url)

# --------------------------
# Funciones de Hentai (3H y NH)
# --------------------------

def borrar_carpeta_h3dl():
    """Elimina la carpeta temporal de descargas Hentai"""
    folder_name = 'h3dl'
    for root, dirs, files in os.walk(folder_name, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(folder_name)

async def download_hentai_images(base_url, code, folder_name, client, message):
    """Descarga imágenes de un hentai dado su código"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        os.makedirs(folder_name, exist_ok=True)
    except OSError as e:
        if "File name too long" in str(e):
            folder_name = folder_name[:50]
            os.makedirs(folder_name, exist_ok=True)
        else:
            await message.reply(f"Error al crear directorio: {e}")
            return

    page_number = 1
    while True:
        page_url = f"{base_url}{code}/{page_number}/"
        try:
            response = requests.get(page_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if page_number == 1:
                await message.reply(f"Error al acceder a la página: {str(e)}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        img_tag = soup.find('img', {'src': re.compile(r'.*\.(png|jpg|jpeg|gif|bmp|webp)$')})
        if not img_tag:
            break

        img_url = img_tag['src']
        img_extension = os.path.splitext(img_url)[1]
        img_data = requests.get(img_url, headers=headers).content

        img_filename = os.path.join(folder_name, f"{page_number}{img_extension}")
        with open(img_filename, 'wb') as img_file:
            img_file.write(img_data)

        page_number += 1

    return folder_name

async def hentai_common_operation(client, message, codes, base_url, cover_func=None):
    """Operación común para manejar códigos Hentai"""
    for code in codes:
        try:
            # Descargar cover si se especifica la función
            if cover_func:
                await cover_func(client, message, [code])
            
            # Descargar todas las imágenes
            url = f"{base_url}{code}/"
            response = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            title_tag = soup.find('title')
            folder_name = os.path.join("h3dl", clean_string(title_tag.text.strip()) if title_tag else clean_string(code))
            
            await download_hentai_images(base_url, code, folder_name, client, message)
            
            # Crear archivo comprimido
            zip_filename = f"{folder_name}.cbz"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for root, _, files in os.walk(folder_name):
                    for file in files:
                        zipf.write(os.path.join(root, file), arcname=file)

            await client.send_document(message.chat.id, zip_filename)
            borrar_carpeta_h3dl()

        except requests.exceptions.RequestException as e:
            await message.reply(f"El código {code} es erróneo: {str(e)}")
        except Exception as e:
            await message.reply(f"Error al procesar el código {code}: {str(e)}")

# --------------------------
# Funciones de Administración
# --------------------------

async def handle_start(client, message):
    """Maneja el comando de inicio"""
    await message.reply("𝗕𝗼𝘁 𝗙𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗻𝗱𝗼✅...")

async def manage_user_list(client, message, action, list_name):
    """Función genérica para manejar listas de usuarios/chats"""
    try:
        target_id = int(message.text.split()[1]) if action != "add_chat" else message.chat.id
    except (IndexError, ValueError):
        return await message.reply("ID inválido")

    target_list = globals()[f"{list_name}_users"]
    allowed_list = globals()["allowed_users"]

    if action.startswith("add"):
        if target_id not in target_list:
            target_list.append(target_id)
            allowed_list.append(target_id)
            await message.reply(f"ID {target_id} añadido a {list_name}")
        else:
            await message.reply(f"ID {target_id} ya está en {list_name}")
    else:
        if target_id in target_list:
            target_list.remove(target_id)
            allowed_list.remove(target_id)
            await message.reply(f"ID {target_id} eliminado de {list_name}")
        else:
            await message.reply(f"ID {target_id} no encontrado en {list_name}")

# --------------------------
# Manejador Principal
# --------------------------

@app.on_message(filters.text)
async def handle_message(client, message):
    """Manejador principal de mensajes"""
    text = message.text.lower()
    username = message.from_user.username
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Verificar permisos
    if not BOT_IS_PUBLIC and user_id not in allowed_users and chat_id not in allowed_users or user_id in ban_users:
        return

    # Mapeo de comandos a funciones
    command_map = {
        'start': handle_start,
        'convert': compress_video,
        'compress': lambda c, m: handle_compress(c, m, username),
        'setsize': lambda c, m: set_size(c, m, username),
        'rename': rename,
        'up': handle_up,
        'dl': download_file,
        '3h': lambda c, m: hentai_common_operation(c, m, extract_codes(m), "https://es.3hentai.net/d/", cover3h_operation),
        'nh': lambda c, m: hentai_common_operation(c, m, extract_codes(m), "https://nhentai.net/g/", covernh_operation)
    }

    # Manejar comandos administrativos
    if user_id in admin_users:
        admin_commands = {
            'adduser': lambda c, m: manage_user_list(c, m, "add", "temp"),
            'remuser': lambda c, m: manage_user_list(c, m, "remove", "temp"),
            'addchat': lambda c, m: manage_user_list(c, m, "add_chat", "temp"),
            'remchat': lambda c, m: manage_user_list(c, m, "remove_chat", "temp"),
            'banuser': lambda c, m: manage_user_list(c, m, "add", "ban"),
            'debanuser': lambda c, m: manage_user_list(c, m, "remove", "ban"),
            'calidad': lambda c, m: update_video_settings(m.text[len('/calidad '):]) or m.reply(f"Configuración actualizada: {video_settings}")
        }
        command_map.update(admin_commands)

    # Ejecutar comando correspondiente
    for cmd_prefix, handler in command_map.items():
        if text.startswith(('/', f'.{cmd_prefix}', cmd_prefix)):
            await handler(client, message)
            break

# Iniciar el bot
if __name__ == "__main__":
    app.run()