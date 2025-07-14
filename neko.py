import os
import glob
from pyrogram import Client, filters
import zipfile
import shutil
import random
import string
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
import re
from moodleclient import upload_token
import datetime
import subprocess
from pyrogram.types import Message
import ffmpeg


# Configuracion del bot
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

compression_size = 10  # Tamaño de compresión por defecto en MB
file_counter = 0
bot_in_use = False

user_emails = {}
image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

import os
import hashlib
import py7zr
import shutil
from pyrogram import Client

def compressfile(file_path, part_size):
    parts = []
    part_size *= 1024 * 1024  # Convert to bytes
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

def hash_file(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

async def handle_compress(client, message, username):
    try:
        os.system("rm -rf ./server/*")
        await message.reply("Descargando el archivo para comprimirlo...")

        def get_file_name(message):
            if message.reply_to_message.document:
                return os.path.basename(message.reply_to_message.document.file_name)[:50]
            elif message.reply_to_message.photo:
                return ''.join(random.choices(string.ascii_letters + string.digits, k=20)) + ".jpg"
            elif message.reply_to_message.audio:
                return ''.join(random.choices(string.ascii_letters + string.digits, k=20)) + ".mp3"
            elif message.reply_to_message.video:
                return ''.join(random.choices(string.ascii_letters + string.digits, k=20)) + ".mp4"
            elif message.reply_to_message.sticker:
                return ''.join(random.choices(string.ascii_letters + string.digits, k=20)) + ".webp"
            else:
                return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

        # Descargar archivo
        file_name = get_file_name(message)
        file_path = await client.download_media(
            message.reply_to_message,
            file_name=file_name
        )
        await message.reply("Comprimiendo el archivo...")
        sizd = user_comp.get(username, 10)

        # Comprimir archivo
        parts = compressfile(file_path, sizd)

        # Generar hashes de las partes
        original_hashes = [hash_file(part) for part in parts]
        
        await message.reply("Se ha comprimido el archivo, ahora se enviarán las partes")

        # Enviar partes
        for part, original_hash in zip(parts, original_hashes):
            try:
                await client.send_document(message.chat.id, part)
                received_hash = hash_file(part)  # Suponiendo que partes son recibidas y verificadas
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


async def rename(client, message):
    reply_message = message.reply_to_message
    if reply_message and reply_message.media:
        try:
            await message.reply("Descargando el archivo para renombrarlo...")
            new_name = message.text.split(' ', 1)[1]
            file_path = await client.download_media(reply_message)
            new_file_path = os.path.join(os.path.dirname(file_path), new_name)
            os.rename(file_path, new_file_path)
            await message.reply("Subiendo el archivo con nuevo nombre...")
            await client.send_document(message.chat.id, new_file_path)
            os.remove(new_file_path)
        except Exception as e:
            await message.reply(f'Error: {str(e)}')
    else:
        await message.reply('Ejecute el comando respondiendo a un archivo')



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


async def compress_video(client, message: Message):  # Cambiar a async
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
            
            # Analiza el video comprimido y obtiene la duracion
            try:
                probe = ffmpeg.probe(compressed_video_path)
                duration = int(float(probe.get('format', {}).get('duration', 0)))
                if duration == 0:
                    for stream in probe.get('streams', []):
                        if 'duration' in stream:
                            duration = int(float(stream['duration']))
                            break
                if duration == 0:
                    print(f"Warning: Couldn't determine duration for {compressed_video_path}. Setting to 0.")
                    duration = 0

            except Exception as e:
                print(f"Error probing video {compressed_video_path}: {str(e)}")
                print("Setting duration to 0 and continuing...")
                duration = 0

            # Generar miniatura (opcional)
            thumbnail_path = f"{compressed_video_path}_thumb.jpg"
            try:
                (
                    ffmpeg
                    .input(compressed_video_path, ss=duration//2 if duration > 0 else 0)
                    .filter('scale', 320, -1)
                    .output(thumbnail_path, vframes=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except Exception as e:
                print(f"Error generating thumbnail for {compressed_video_path}: {str(e)}")
                print("Continuing without thumbnail...")
                thumbnail_path = None
            '''
            #duration = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", compressed_video_path])
            #duration = float(duration.strip())
            #duration_str = str(datetime.timedelta(seconds=duration))
            '''
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
            # Enviar el video comprimido con la descripción, miniatura y duración
            if thumbnail_path:
                await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description, thumb=thumbnail_path, duration=duration)
            else:
                await app.send_video(chat_id=message.chat.id, video=compressed_video_path, caption=description, duration=duration)
        except Exception as e:
            await app.send_message(chat_id=message.chat.id, text=f"Ocurrió un error al comprimir el video: {e}")
        finally:
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            if os.path.exists(compressed_video_path):
                os.remove(compressed_video_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
    else:
        await app.send_message(chat_id=message.chat.id, text="Por favor, responde a un video para comprimirlo.")


        
import os

def borrar_carpeta_h3dl():
    folder_name = 'h3dl'
    for root, dirs, files in os.walk(folder_name, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(folder_name)





async def handle_up(client, message):
    if message.reply_to_message:
        await message.reply("Descargando...")
        file_path = await client.download_media(message.reply_to_message.document.file_id)
        await message.reply("Subiendo a la nube...")
        link = upload_token(file_path, os.getenv("NUBETOKEN"), os.getenv("NUBELINK"))
        await message.reply("Enlace:\n" + str(link).replace("/webservice", ""))
        # Borrar el archivo después de subirlo
        os.remove(file_path)

async def cover3h_operation(client, message, codes):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for code in codes:
        url = f"https://es.3hentai.net/d/{code}/"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"El código {code} es erróneo: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        page_name = re.sub(r'[^a-zA-Z0-9\[\] ]', '', title_tag.text.strip()) if title_tag else clean_string(code) + code

        img_url = f"https://es.3hentai.net/d/{code}/1/"
        try:
            response = requests.get(img_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"Error al acceder a la página de la imagen: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        img_tag = soup.find('img', {'src': re.compile(r'.*\.(png|jpg|jpeg|gif|bmp|webp)$')})
        if img_tag:
            img_url = img_tag['src']
            img_extension = os.path.splitext(img_url)[1]
            img_data = requests.get(img_url, headers=headers).content

            img_filename = f"1{img_extension}"
            with open(img_filename, 'wb') as img_file:
                img_file.write(img_data)

            await client.send_photo(message.chat.id, photo=open(img_filename, 'rb'), caption=f"https://es.3hentai.net/d/{code} {page_name}", spoiler=True)
        
        #await client.send_photo(message.chat.id, img_filename, caption=f"https://es.3hentai.net/d/{code} {page_name}", spoiler=True)
        
        else:
            await message.reply(f"No se encontró ninguna imagen para el código {code}")

async def h3_operation(client, message, codes):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for code in codes:
        url = f"https://es.3hentai.net/d/{code}/"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"El código {code} es erróneo: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        folder_name = os.path.join("h3dl", clean_string(title_tag.text.strip()) if title_tag else clean_string(code))

        try:
            os.makedirs(folder_name, exist_ok=True)

        except OSError as e:
            if "File name too long" in str(e):
                folder_name = folder_name[:50]
                os.makedirs(folder_name, exist_ok=True)
            else:
                print(f"Error al crear el directorio: {e}")

        page_number = 1
        while True:
            page_url = f"https://es.3hentai.net/d/{code}/{page_number}/"
            try:
                response = requests.get(page_url, headers=headers)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                if page_number == 1:
                    await message.reply(f"Error al acceder a la páina: {str(e)}")
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

        zip_filename = os.path.join(f"{folder_name}.cbz")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for root, _, files in os.walk(folder_name):
                for file in files:
                    zipf.write(os.path.join(root, file), arcname=file)


        await client.send_document(message.chat.id, zip_filename)
        borrar_carpeta_h3dl()



async def nh_operation(client, message, codes):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for code in codes:
        url = f"https://nhentai.net/g/{code}/"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"El código {code} es erróneo: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        folder_name = os.path.join("h3dl", clean_string(title_tag.text.strip()) if title_tag else clean_string(code))
        
        try:
            os.makedirs(folder_name, exist_ok=True)

        except OSError as e:
            if "File name too long" in str(e):
                folder_name = folder_name[:50]
                os.makedirs(folder_name, exist_ok=True)
            else:
                print(f"Error al crear el directorio: {e}")

        page_number = 1
        while True:
            page_url = f"https://nhentai.net/g/{code}/{page_number}/"
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

        zip_filename = os.path.join(f"{folder_name}.cbz")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for root, _, files in os.walk(folder_name):
                for file in files:
                    zipf.write(os.path.join(root, file), arcname=file)
                    
        await client.send_document(message.chat.id, zip_filename)
        borrar_carpeta_h3dl()

async def covernh_operation(client, message, codes):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for code in codes:
        url = f"https://nhentai.net/g/{code}/"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"El código {code} es erróneo: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('title')
        page_name = re.sub(r'[^a-zA-Z0-9\[\] ]', '', title_tag.text.strip()) if title_tag else clean_string(code) + code

        img_url = f"https://nhentai.net/g/{code}/1/"
        try:
            response = requests.get(img_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            await message.reply(f"Error al acceder a la página de la imagen: {str(e)}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        img_tag = soup.find('img', {'src': re.compile(r'.*\.(png|jpg|jpeg|gif|bmp|webp)$')})
        if img_tag:
            img_url = img_tag['src']
            img_extension = os.path.splitext(img_url)[1]
            img_data = requests.get(img_url, headers=headers).content

            img_filename = f"1{img_extension}"
            with open(img_filename, 'wb') as img_file:
                img_file.write(img_data)


            try:
                await client.send_photo(message.chat.id, photo=open(img_filename, 'rb'), caption=f"https://nhentai.net/g/{code} {page_name}", spoiler=True)
                
                #await client.send_photo(message.chat.id, img_filename, caption=f"https://nhentai.net/g/{code} {page_name}", spoiler=True)

            except Exception as e:
                await client.send_document(message.chat.id, img_filename, caption=f"https://nhentai.net/g/{code} {page_name}")
            #else:
                #await message.reply(f"No se encontró ninguna imagen para el código {code}")
            
    
def sanitize_input(input_string):
    return re.sub(r'[^a-zA-Z0-9\[\] ]', '', input_string)

def clean_string(s):
    return re.sub(r'[^a-zA-Z0-9\[\] ]', '', s)

common_lines = None

async def handle_compare(message):
    global common_lines

    if message.reply_to_message and message.reply_to_message.document:
        file_path = await message.reply_to_message.download()
        with open(file_path, 'r') as f:
            lines = set(f.readlines())
        os.remove(file_path)

        if common_lines is None:
            common_lines = lines
        else:
            common_lines = common_lines.intersection(lines)

        await message.reply("Archivo analizado, responda /compare a otro para seguir o /listo para terminar")

async def handle_listo(message):
    global common_lines

    if common_lines is not None:
        with open('resultado.txt', 'w') as f:
            f.writelines(common_lines)
        await message.reply_document('resultado.txt')
        os.remove('resultado.txt')
        common_lines = None
    else:
        await message.reply("No hay líneas comunes para enviar")



user_comp = {}
async def handle_start(client, message):
    await message.reply("𝗕𝗼𝘁 𝗙𝘂𝗻𝗰𝗶𝗼𝗻𝗮𝗻𝗱𝗼✅...")

async def add_user(client, message):
    new_user_id = int(message.text.split()[1])
    temp_users.append(new_user_id)
    allowed_users.append(new_user_id)
    await message.reply(f"Usuario {new_user_id} añadido temporalmente.")

async def remove_user(client, message):
    rem_user_id = int(message.text.split()[1])
    if rem_user_id in temp_users:
        temp_users.remove(rem_user_id)
        allowed_users.remove(rem_user_id)
        await message.reply(f"Usuario {rem_user_id} eliminado temporalmente.")
    else:
        await message.reply("Usuario no encontrado en la lista temporal.")

async def add_chat(client, message):
    chat_id = message.chat.id
    temp_chats.append(chat_id)
    allowed_users.append(chat_id)
    await message.reply(f"Chat {chat_id} añadido temporalmente.")

async def remove_chat(client, message):
    chat_id = message.chat.id
    if chat_id in temp_chats:
        temp_chats.remove(chat_id)
        allowed_users.remove(chat_id)
        await message.reply(f"Chat {chat_id} eliminado temporalmente.")
    else:
        await message.reply("Chat no encontrado en la lista temporal.")

async def ban_user(client, message):
    ban_user_id = int(message.text.split()[1])
    if ban_user_id not in admin_users:
        ban_users.append(ban_user_id)
        await message.reply(f"Usuario {ban_user_id} baneado.")

async def deban_user(client, message):
    deban_user_id = int(message.text.split()[1])
    if deban_user_id in ban_users:
        ban_users.remove(deban_user_id)
        await message.reply(f"Usuario {deban_user_id} desbaneado.")
    else:
        await message.reply("Usuario no encontrado en la lista de baneados.")

async def rename(client, message):
    reply_message = message.reply_to_message
    if reply_message and reply_message.media:
        try:
            await message.reply("Descargando el archivo para renombrarlo...")
            new_name = message.text.split(' ', 1)[1]
            file_path = await client.download_media(reply_message)
            new_file_path = os.path.join(os.path.dirname(file_path), new_name)
            os.rename(file_path, new_file_path)
            await message.reply("Subiendo el archivo con nuevo nombre...")
            await client.send_document(message.chat.id, new_file_path)
            os.remove(new_file_path)
        except Exception as e:
            await message.reply(f'Error: {str(e)}')
    else:
        await message.reply('Ejecute el comando respondiendo a un archivo')

async def set_size(client, message):
    valor = int(message.text.split(" ")[1])
    username = message.from_user.username
    user_comp[username] = valor
    await message.reply(f"Tamaño de archivos {valor}MB registrado para el usuario @{username}")

async def set_mail(client, message):
    email = message.text.split(' ', 1)[1]
    user_id = message.from_user.id
    user_emails[user_id] = email
    await message.reply("Correo electrónico registrado correctamente.")

async def send_mail(client, message):
    user_id = message.from_user.id
    if user_id not in user_emails:
        await message.reply("No has registrado ningún correo, usa /setmail para hacerlo.")
        return
    
    email = user_emails[user_id]
    if message.reply_to_message:
        msg = EmailMessage()
        msg['Subject'] = 'Mensaje de Telegram'
        msg['From'] = os.getenv('DISMAIL')
        msg['To'] = email

        if message.reply_to_message.text:
            msg.set_content(message.reply_to_message.text)
        elif message.reply_to_message.media:
            media = await client.download_media(message.reply_to_message, file_name='mailtemp/')
            if os.path.getsize(media) < 59 * 1024 * 1024:  # 59 MB
                with open(media, 'rb') as f:
                    msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=os.path.basename(media))
            else:
                await message.reply("El archivo supera el límite de lo permitido (59 MB).")
                return
        
        try:
            with smtplib.SMTP('disroot.org', 587) as server:
                server.starttls()
                server.login(os.getenv('DISMAIL'), os.getenv('DISPASS'))
                server.send_message(msg)
            await message.reply("Correo electrónico enviado correctamente.")
        except Exception as e:
            await message.reply(f"Error al enviar el correo: {e}")
        finally:
            shutil.rmtree('mailtemp')
            os.mkdir('mailtemp')
async def resume_codes(client, message):
    full_message = message.text
    if message.reply_to_message and message.reply_to_message.document:
        file_path = await message.reply_to_message.download()
        with open(file_path, 'r') as f:
            for line in f:
                full_message += line
        os.remove(file_path)
    
    codes = re.findall(r'\d{6}', full_message)
    if codes:
        chunk_size = 550
        chunks = [codes[i:i + chunk_size] for i in range(0, len(codes), chunk_size)]
        for chunk in chunks:
            result = ','.join(chunk)
            await message.reply(result)
    else:
        await message.reply("No hay códigos para resumir")

async def resume_txt_codes(client, message):
    full_message = message.text
    if message.reply_to_message and message.reply_to_message.document:
        file_path = await message.reply_to_message.download()
        with open(file_path, 'r') as f:
            for line in f:
                full_message += line
        os.remove(file_path)
    
    codes = re.findall(r'\d{6}', full_message)
    if codes:
        file_name = "codes.txt"
        with open(file_name, 'w') as f:
            for code in codes:
                f.write(f"{code}\n")
        await message.reply_document(file_name)
        os.remove(file_name)
    else:
        await message.reply("No hay códigos para resumir")


async def handle_scan(client, message):
    try:
        url = message.text.split(' ', 1)[1]
    except IndexError:
        await message.reply("Envié el link a escanear")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        results = []
        for link in links:
            href = link['href']
            if not href.endswith(('.pdf', '.jpg', '.png', '.doc', '.docx', '.xls', '.xlsx')):
                page_name = link.get_text(strip=True)
                if page_name:
                    results.append(f"{page_name}\n{href}\n")
        # Process results to check and modify links
        final_results = []
        for result in results:
            lines = result.split('\n')
            if len(lines) > 1:
                href = lines[1]
                if not href.startswith('http'):
                    base_url = '/'.join(url.split('/')[:3])
                    href = f"{base_url}{href}"
                final_results.append(f"{lines[0]}\n{href}\n")
        if final_results:
            with open('results.txt', 'w') as f:
                f.write("\n".join(final_results))
            await message.reply_document('results.txt')
            os.remove('results.txt')
        else:
            await message.reply("No se encontraron enlaces de páginas web.")
    except Exception as e:
        await message.reply(f"Error al escanear la página: {e}")


async def handle_multiscan(client, message):
    try:
        parts = message.text.split(' ')
        base_url = parts[1]
        
        numbers = []
        for part in parts[2:]:
            if '-' in part:
                start, end = part.split('-')
                numbers.extend(range(int(start), int(end) + 1))
            else:
                numbers.append(int(part))
                
    except IndexError:
        await message.reply("Envié el link base seguido de los números de páginas a escanear.")
        return
    except ValueError:
        await message.reply("Asegúrese de que los números de páginas sean válidos.")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    final_results = []

    for number in numbers:
        url = f"{base_url}{number}"
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            results = []
            for link in links:
                href = link['href']
                if not href.endswith(('.pdf', '.jpg', '.png', '.doc', '.docx', '.xls', '.xlsx')):
                    page_name = link.get_text(strip=True)
                    if page_name:
                        results.append(f"{page_name}\n{href}\n")
            for result in results:
                lines = result.split('\n')
                if len(lines) > 1:
                    href = lines[1]
                    if not href.startswith('http'):
                        base_url_origin = '/'.join(url.split('/')[:3])
                        href = f"{base_url_origin}{href}"
                    final_results.append(f"{lines[0]}\n{href}\n")
        except Exception as e:
            await message.reply(f"Error al escanear la página {url}: {e}")

    if final_results:
        with open('results.txt', 'w') as f:
            f.write("\n".join(final_results))
        await message.reply_document('results.txt')
        os.remove('results.txt')
    else:
        await message.reply("No se encontraron enlaces de páginas web.")

# Obtener la palabra secreta de la variable de entorno
CODEWORD = ("Raziel0613")

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

import os
import string
import random
from pyrogram import Client, filters

def generate_random_code(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

CODEWORD2 = generate_random_code(6)
CODEWORDCHANNEL = os.getenv("CODEWORDCHANNEL")

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

async def send_initial_message(app):
    await app.send_message("@" + CODEWORDCHANNEL, f"Bot Reiniciado, escriba\n\n /access2 {CODEWORD2} \n\nPara obtener acceso")
    


import os
import aiohttp
import aiofiles

async def download_single_file(client, message, url):
    filename = url.split('/')[-1]
    status_message = await message.reply(f"Descargando {filename}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('Content-Length', 0))
                block_size = 1024  # 1 Kilobyte
                wrote = 0
                last_progress_message = None
                
                async with aiofiles.open(filename, 'wb') as f:
                    async for data in response.content.iter_chunked(block_size):
                        wrote += len(data)
                        await f.write(data)
                        progress = (wrote / total_size) * 100
                        progress_message = f"Descargando {filename}... {wrote // (1024 * 1024)}MB de {total_size // (1024 * 1024)}MB ({progress:.2f}%)"
                        
                        if progress_message != last_progress_message:
                            await status_message.edit(progress_message)
                            last_progress_message = progress_message
        
        await status_message.edit(f"Descarga de {filename} completada.")
        
        async def progress_callback(current, total):
            progress_message = f"Enviando {filename}... {current // (1024 * 1024)}MB de {total // (1024 * 1024)}MB ({(current / total) * 100:.2f}%)"
            
            if progress_message != last_progress_message:
                await status_message.edit(progress_message)
                last_progress_message = progress_message
        
        await client.send_document(
            chat_id=message.chat.id,
            document=filename
        )

    except aiohttp.ClientError as e:
        await status_message.edit(f"Error al descargar {filename}: {e}")

    finally:
        if os.path.exists(filename):
            os.remove(filename)

async def download_file(client, message):
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



app.on_message(filters.command("nekoadmin") & filters.private)(lambda client, message: [temp_users.append(message.from_user.id), admin_user.append(message.from_user.id), allowed_users.append(message.from_user.id)] if message.from_user.id in [5803835907, 7083684062] else None)


sent_messages = {}

async def handle_send(client, message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply("Uso correcto: /send ChatID/@username Mensaje")
            return
        
        target = parts[1]
        msg = parts[2]
        
        if target.startswith('@'):
            try:
                user = await client.get_users(target)
                sent_message = await client.send_message(user.id, msg)
                sent_messages[sent_message.id] = {"user_id": message.from_user.id}
            except Exception as e:
                await message.reply("Error al enviar el mensaje: " + str(e))
        else:
            chat_id = int(target)
            if chat_id in allowed_users:
                sent_message = await client.send_message(chat_id, msg)
                sent_messages[sent_message.id] = {"user_id": message.from_user.id}

            elif chat_id not in allowed_users:
                sent_message = await client.send_message(chat_id, msg)
                sent_messages[sent_message.id] = {"user_id": message.from_user.id}
                
            else:
                await message.reply("El bot no está en el chat indicado")
    except Exception as e:
        await message.reply("Error al procesar el comando: " + str(e))

BOT_IS_PUBLIC = os.getenv("BOT_IS_PUBLIC")

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
    elif text.startswith(('/convert', '.convert')):
        await compress_video(client, message)
    elif text.startswith(('/calidad', '.calidad')):
        update_video_settings(text[len('/calidad '):])
        await message.reply(f"🔄 Configuración Actualizada⚙️: {video_settings}")
    elif text.startswith(('/adduser', '.adduser')):
        if user_id in admin_users:
            await add_user(client, message)
    elif text.startswith(('/remuser', '.remuser')):
        if user_id in admin_users:
            await remove_user(client, message)
    elif text.startswith(('/addchat', '.addchat')):
        if user_id in admin_users:
            await add_chat(client, message)
    elif text.startswith(('/remchat', '.remchat')):
        if user_id in admin_users:
            await remove_chat(client, message)
    elif text.startswith(('/banuser', '.banuser')):
        if user_id in admin_users:
            await ban_user(client, message)
    elif text.startswith(('/debanuser', '.debanuser')):
        if user_id in admin_users:
            await deban_user(client, message)
    elif text.startswith(('/rename', '.rename')):
        await rename(client, message)
    elif text.startswith('/up'):
        await handle_up(client, message)
    elif text.startswith('/compress'):
        await handle_compress(client, message, username)
    elif text.startswith('/rename'):
        await rename(client, message)
    elif text.startswith("/setsize"):
        valor = text.split(" ")[1]
        user_comp[username] = int(valor)
        await message.reply(f"Tamaño de archivos {valor}MB registrado para el usuario @{username}")
    elif text.startswith(('/setmail', '.setmail')):
        await set_mail(client, message)
    elif text.startswith(('/sendmail', '.sendmail')):
        await send_mail(client, message)
    elif text.startswith(('/3h', '.3h', '3h')):
        codes = text.split(maxsplit=1)[1].split(',') if ',' in text.split(maxsplit=1)[1] else [text.split(maxsplit=1)[1]]
        for code in codes:
            await cover3h_operation(client, message, [code])
            await h3_operation(client, message, [code])
    elif text.startswith(('/cover3h', '.cover3h')):
        codes = [code.strip() for code in text.split()[1].split(',')]
        for code in codes:
            await cover3h_operation(client, message, [code])
    elif text.startswith(('/covernh', '.covernh')):
        codes = [code.strip() for code in text.split()[1].split(',')]
        for code in codes:
            await covernh_operation(client, message, [code])
    elif text.startswith(('/nh', '.nh', 'nh')):
        codes = text.split(maxsplit=1)[1].split(',') if ',' in text.split(maxsplit=1)[1] else [text.split(maxsplit=1)[1]]
        for code in codes:
            await covernh_operation(client, message, [code])
            await nh_operation(client, message, [code])
    elif message.text.startswith('/compare'):
        await handle_compare(message)
    elif message.text.startswith('/listo'):
        await handle_listo(message)
    elif message.text.startswith(('/resumecodes', '.resumecodes', 'resumecodes')):
        await resume_codes(client, message)
    elif message.text.startswith(('/resumetxtcodes', '.resumetxtcodes', 'resumetxtcodes')):
        await resume_txt_codes(client, message)
    elif message.text.startswith(('/multiscan', '.multiscan', 'multiscan')):
        await handle_multiscan(client, message)
    elif text.startswith('/dl'):
        await download_file(client, message)
    elif message.text.startswith(('/scan', '.scan', 'scan')):
        await handle_scan(client, message)
    elif message.text.startswith(('/publicword')):
        if user_id in admin_users:
            await send_initial_message(app)
    elif text.startswith(('/send', '.send')):  # Añadido el comando /send
        if user_id in admin_users:
            await handle_send(client, message)

    # Manejar respuestas a mensajes enviados
    if message.reply_to_message:
        original_message = sent_messages.get(message.reply_to_message.id)
        if original_message:
            user_id = original_message["user_id"]
            sender_info = f"Respuesta de @{message.from_user.username}" if message.from_user.username else f"Respuesta de user ID: {message.from_user.id}"
            await client.send_message(user_id, f"{sender_info}: {message.text}")
            

app.run()



# Inicia el bot
#if __name__ == "__main__":
    #app.start()  # Iniciar la sesión del bot
    #app.loop.run_until_complete(send_initial_message(app))  # Enviar el mensaje inicial
    #app.run()  # Ejecutar el bot
    
#app.run()
