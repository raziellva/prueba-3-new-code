import os
import glob
from pyrogram import Client, filters
import zipfile
import shutil
import random
import string
import hashlib
import py7zr
import datetime
import subprocess
from pyrogram.types import Message
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Filtro para excluir comandos que comienzan con "/"
exclude_commands = filters.create(lambda _, __, m: not (m.text and m.text.startswith("/")))

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

# Administradores y Usuarios del bot
admin_users = list(map(int, os.getenv('ADMINS', '').split(','))) if os.getenv('ADMINS') else []
users = list(map(int, os.getenv('USERS', '').split(','))) if os.getenv('USERS') else []
temp_users = []
temp_chats = []
ban_users = []
allowed_users = admin_users + users + temp_users + temp_chats
app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración de compresión
compression_size = 10  # Tamaño de compresión por defecto en MB
user_comp = {}
image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

# Configuración de compresión de video
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

# Limpiar directorio temporal al iniciar
if os.path.exists('./server'):
    shutil.rmtree('./server')
os.makedirs('./server', exist_ok=True)

def update_video_settings(command: str):
    """Actualiza la configuración de compresión de video"""
    settings = command.split()
    for setting in settings:
        if '=' in setting:
            key, value = setting.split('=', 1)
            if key in video_settings:
                video_settings[key] = value

def generate_random_filename(extension):
    """Genera un nombre de archivo aleatorio"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + f".{extension}"

async def auto_compress_video(client, message: Message):
    """Comprime automáticamente cualquier video enviado al bot"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Verificar si el usuario está baneado
    if user_id in ban_users:
        return
    
    # Verificar permisos en bots privados
    if not BOT_IS_PUBLIC and user_id not in allowed_users and chat_id not in allowed_users:
        return
    
    # Crear carpeta temporal para el usuario
    user_temp_dir = f"./server/{user_id}_{chat_id}"
    os.makedirs(user_temp_dir, exist_ok=True)
    
    # Descargar video
    status_msg = await message.reply("📥 **Descargando video...**")
    video_path = await message.download(file_name=os.path.join(user_temp_dir, generate_random_filename("mp4")))
    
    # Comprimir video
    try:
        await status_msg.edit("🗜️ **Iniciando compresión...**")
        output_path = await process_video_compression(video_path, user_temp_dir, status_msg)
        
        # Enviar video comprimido
        await send_compressed_video(client, message, video_path, output_path, status_msg)
        
    except Exception as e:
        await status_msg.edit(f"❌ **Error en compresión:** `{str(e)}`")
    finally:
        # Limpiar archivos temporales
        shutil.rmtree(user_temp_dir, ignore_errors=True)

async def process_video_compression(input_path, output_dir, status_msg):
    """Procesa la compresión del video"""
    # Obtener información del video original
    original_size = os.path.getsize(input_path)
    duration = get_video_duration(input_path)
    
    await status_msg.edit(
        f"🗜️ **Comprimiendo video...**\n"
        f"• Tamaño original: `{format_size(original_size)}`\n"
        f"• Duración: `{duration}`\n"
        f"• Configuración: {video_settings['resolution']}@{video_settings['fps']}fps"
    )
    
    # Crear ruta de salida
    output_path = os.path.join(output_dir, "compressed_" + os.path.basename(input_path))
    
    # Construir comando FFmpeg
    ffmpeg_command = [
        'ffmpeg', '-y', '-i', input_path,
        '-s', video_settings['resolution'],
        '-crf', video_settings['crf'],
        '-b:a', video_settings['audio_bitrate'],
        '-r', video_settings['fps'],
        '-preset', video_settings['preset'],
        '-c:v', video_settings['codec'],
        output_path
    ]
    
    # Ejecutar compresión
    start_time = datetime.datetime.now()
    process = await asyncio.create_subprocess_exec(
        *ffmpeg_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Monitorear progreso
    last_update = datetime.datetime.now()
    while True:
        line = await process.stderr.readline()
        if not line:
            break
            
        line = line.decode().strip()
        if "time=" in line:
            current_time = datetime.datetime.now()
            if (current_time - last_update).seconds > 5:  # Actualizar cada 5 segundos
                time_str = line.split('time=')[1].split()[0]
                await status_msg.edit(f"⏳ **Comprimiendo...** `{time_str}`")
                last_update = current_time
    
    # Verificar si se completó correctamente
    if await process.wait() != 0 or not os.path.exists(output_path):
        error = (await process.stderr.read()).decode()
        raise Exception(f"FFmpeg error: {error[:200]}" if error else "La compresión falló")
    
    return output_path

def get_video_duration(file_path):
    """Obtiene la duración del video usando FFprobe"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 
             'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        duration_sec = float(result.stdout.strip())
        return str(datetime.timedelta(seconds=duration_sec)).split('.')[0]
    except:
        return "Desconocida"

def format_size(size_bytes):
    """Formatea el tamaño en bytes a una cadena legible"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

async def send_compressed_video(client, message, original_path, compressed_path, status_msg):
    """Envía el video comprimido con información de compresión"""
    # Calcular métricas
    original_size = os.path.getsize(original_path)
    compressed_size = os.path.getsize(compressed_path)
    compression_ratio = (1 - (compressed_size / original_size)) * 100
    
    # Crear mensaje de resultado
    caption = (
        "🎬 **Video Comprimido Exitosamente**\n\n"
        f"• Tamaño original: `{format_size(original_size)}`\n"
        f"• Tamaño final: `{format_size(compressed_size)}`\n"
        f"• Reducción: `{compression_ratio:.1f}%`\n\n"
        "⚙️ **Configuración usada:**\n"
        f"Resolución: `{video_settings['resolution']}`\n"
        f"Calidad (CRF): `{video_settings['crf']}` | FPS: `{video_settings['fps']}`"
    )
    
    # Enviar video comprimido
    await status_msg.edit("⬆️ **Subiendo video comprimido...**")
    
    await client.send_video(
        chat_id=message.chat.id,
        video=compressed_path,
        caption=caption,
        duration=get_video_duration(compressed_path),
        thumb="thumb.jpg" if os.path.exists("thumb.jpg") else None,
        progress=upload_progress,
        progress_args=(status_msg,)
    )
    
    await status_msg.delete()

async def upload_progress(current, total, status_msg):
    """Muestra el progreso de la subida"""
    percent = current * 100 / total
    await status_msg.edit(f"⬆️ **Subiendo video...** {percent:.1f}%")

# Comandos administrativos
async def add_user(client, message):
    if message.from_user.id in admin_users:
        try:
            new_user_id = int(message.text.split()[1])
            if new_user_id not in temp_users:
                temp_users.append(new_user_id)
                allowed_users.append(new_user_id)
                await message.reply(f"✅ Usuario {new_user_id} añadido temporalmente.")
            else:
                await message.reply("⚠️ El usuario ya está en la lista temporal.")
        except:
            await message.reply("❌ Formato incorrecto. Use: /adduser <user_id>")

async def remove_user(client, message):
    if message.from_user.id in admin_users:
        try:
            rem_user_id = int(message.text.split()[1])
            if rem_user_id in temp_users:
                temp_users.remove(rem_user_id)
                allowed_users.remove(rem_user_id)
                await message.reply(f"✅ Usuario {rem_user_id} eliminado temporalmente.")
            else:
                await message.reply("⚠️ Usuario no encontrado en la lista temporal.")
        except:
            await message.reply("❌ Formato incorrecto. Use: /remuser <user_id>")

async def add_chat(client, message):
    if message.from_user.id in admin_users:
        chat_id = message.chat.id
        if chat_id not in temp_chats:
            temp_chats.append(chat_id)
            allowed_users.append(chat_id)
            await message.reply(f"✅ Chat {chat_id} añadido temporalmente.")
        else:
            await message.reply("⚠️ Este chat ya está en la lista temporal.")

async def remove_chat(client, message):
    if message.from_user.id in admin_users:
        chat_id = message.chat.id
        if chat_id in temp_chats:
            temp_chats.remove(chat_id)
            allowed_users.remove(chat_id)
            await message.reply(f"✅ Chat {chat_id} eliminado temporalmente.")
        else:
            await message.reply("⚠️ Chat no encontrado en la lista temporal.")

async def ban_user(client, message):
    if message.from_user.id in admin_users:
        try:
            ban_user_id = int(message.text.split()[1])
            if ban_user_id not in admin_users and ban_user_id not in ban_users:
                ban_users.append(ban_user_id)
                await message.reply(f"⛔ Usuario {ban_user_id} baneado.")
            elif ban_user_id in admin_users:
                await message.reply("❌ No puedes banear a un administrador.")
            else:
                await message.reply("⚠️ El usuario ya está baneado.")
        except:
            await message.reply("❌ Formato incorrecto. Use: /banuser <user_id>")

async def unban_user(client, message):
    if message.from_user.id in admin_users:
        try:
            unban_user_id = int(message.text.split()[1])
            if unban_user_id in ban_users:
                ban_users.remove(unban_user_id)
                await message.reply(f"✅ Usuario {unban_user_id} desbaneado.")
            else:
                await message.reply("⚠️ Usuario no encontrado en la lista de baneados.")
        except:
            await message.reply("❌ Formato incorrecto. Use: /unbanuser <user_id>")

async def set_quality(client, message):
    """Cambia la configuración de compresión"""
    try:
        new_settings = message.text.split(' ', 1)[1]
        update_video_settings(new_settings)
        await message.reply(
            f"⚙️ **Configuración actualizada:**\n"
            f"Resolución: `{video_settings['resolution']}`\n"
            f"Calidad (CRF): `{video_settings['crf']}`\n"
            f"FPS: `{video_settings['fps']}`\n"
            f"Preset: `{video_settings['preset']}`\n"
            f"Códec: `{video_settings['codec']}`"
        )
    except Exception as e:
        await message.reply(f"❌ **Error al actualizar:** {str(e)}\n\n"
                          "📝 **Formato correcto:**\n"
                          "`/calidad resolution=1280x720 crf=25 fps=30 preset=medium codec=libx265`")

async def handle_start(client, message):
    """Muestra el mensaje de bienvenida"""
    await message.reply(
        "🎥 **Video Compressor Bot**\n\n"
        "Envía cualquier video y lo comprimiré automáticamente\n\n"
        "⚙️ **Configuración actual:**\n"
        f"• Resolución: `{video_settings['resolution']}`\n"
        f"• Calidad (CRF): `{video_settings['crf']}`\n"
        f"• FPS: `{video_settings['fps']}`\n\n"
        "🔧 **Comandos disponibles:**\n"
        "/calidad - Cambiar configuración de compresión\n"
        "/status - Ver configuración actual\n"
        "/help - Mostrar ayuda completa"
    )

async def show_status(client, message):
    """Muestra la configuración actual"""
    await message.reply(
        "⚙️ **Configuración actual de compresión:**\n"
        f"• Resolución: `{video_settings['resolution']}`\n"
        f"• Calidad (CRF): `{video_settings['crf']}`\n"
        f"• FPS: `{video_settings['fps']}`\n"
        f"• Preset: `{video_settings['preset']}`\n"
        f"• Códec: `{video_settings['codec']}`\n\n"
        "Usa `/calidad [parámetros]` para cambiar"
    )

async def show_help(client, message):
    """Muestra la ayuda completa"""
    await message.reply(
        "📚 **Ayuda del Video Compressor Bot**\n\n"
        "**Uso básico:**\n"
        "Simplemente envía cualquier video y será comprimido automáticamente\n\n"
        "**Comandos disponibles:**\n"
        "/start - Iniciar el bot\n"
        "/help - Mostrar esta ayuda\n"
        "/status - Ver configuración actual\n"
        "/calidad - Cambiar parámetros de compresión\n"
        "  Ejemplo: `/calidad resolution=1280x720 crf=25 fps=30`\n\n"
        "**Parámetros de compresión:**\n"
        "• `resolution`: Tamaño de salida (ej: 1280x720)\n"
        "• `crf`: Calidad (23-28 normal, 30+ alta compresión)\n"
        "• `fps`: Fotogramas por segundo\n"
        "• `preset`: Velocidad de compresión (ultrafast, veryfast, medium, slow)\n"
        "• `codec`: Códec de video (libx264, libx265)\n\n"
        "**Comandos administrativos:**\n"
        "/adduser <id> - Añadir usuario temporal\n"
        "/remuser <id> - Remover usuario temporal\n"
        "/banuser <id> - Banear usuario\n"
        "/unbanuser <id> - Desbanear usuario"
    )

# Manejo de variables de entorno
BOT_IS_PUBLIC = os.getenv("BOT_IS_PUBLIC", "false").lower() == "true"

# Manejadores de mensajes (CORREGIDOS)
@app.on_message(filters.video & exclude_commands)
async def video_handler(client, message: Message):
    await auto_compress_video(client, message)

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await handle_start(client, message)

@app.on_message(filters.command("help"))
async def help_handler(client, message: Message):
    await show_help(client, message)

@app.on_message(filters.command("status"))
async def status_handler(client, message: Message):
    await show_status(client, message)

@app.on_message(filters.command("calidad"))
async def quality_handler(client, message: Message):
    await set_quality(client, message)

@app.on_message(filters.command("adduser"))
async def adduser_handler(client, message: Message):
    await add_user(client, message)

@app.on_message(filters.command("remuser"))
async def remuser_handler(client, message: Message):
    await remove_user(client, message)

@app.on_message(filters.command("banuser"))
async def banuser_handler(client, message: Message):
    await ban_user(client, message)

@app.on_message(filters.command("unbanuser"))
async def unbanuser_handler(client, message: Message):
    await unban_user(client, message)

@app.on_message(filters.command("addchat"))
async def addchat_handler(client, message: Message):
    await add_chat(client, message)

@app.on_message(filters.command("remchat"))
async def remchat_handler(client, message: Message):
    await remove_chat(client, message)

# Iniciar el bot
if __name__ == "__main__":
    print("✅ Bot iniciado correctamente")
    app.run()
