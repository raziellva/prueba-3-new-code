import os
import datetime
import subprocess
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración predeterminada para compresión de video
video_settings = {
    'resolution': '740x480',
    'crf': '30',
    'audio_bitrate': '65k',
    'fps': '24',
    'preset': 'veryfast',
    'codec': 'libx264'
}

# Almacenar procesos activos por chat
active_compressions = {}

def update_video_settings(command: str):
    """Actualiza la configuración de compresión de video"""
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        if key in video_settings:
            video_settings[key] = value

async def compress_video(client: Client, message: Message):
    """Comprime videos usando FFmpeg con configuración personalizable"""
    status_message = None
    if message.reply_to_message and message.reply_to_message.video:
        try:
            # Descargar el video original
            original_video_path = await client.download_media(message.reply_to_message.video)
            original_size = os.path.getsize(original_video_path)
            
            # Preparar ruta para video comprimido
            compressed_video_path = f"{os.path.splitext(original_video_path)[0]}_compressed.mkv"
            
            # Construir comando FFmpeg
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
            
            # Crear teclado para cancelación
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancelar compresión ❌", callback_data=f"cancel_{message.chat.id}")]
            ])
            
            # Enviar mensaje de estado con botón de cancelación
            status_message = await message.reply(
                f"🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...\n\n"
                f"📏 Tamaño original: {original_size // (1024 * 1024)} MB\n"
                f"⚙️ Configuración:\n"
                f"  • Resolución: {video_settings['resolution']}\n"
                f"  • CRF: {video_settings['crf']}\n"
                f"  • FPS: {video_settings['fps']}",
                reply_markup=keyboard
            )
            
            # Registrar proceso en activo
            active_compressions[message.chat.id] = {
                'process': None,
                'status_message_id': status_message.id,
                'cancelled': False
            }
            
            # Ejecutar compresión
            start_time = datetime.datetime.now()
            process = subprocess.Popen(
                ffmpeg_command,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True
            )
            
            # Actualizar proceso en registro
            active_compressions[message.chat.id]['process'] = process
            
            # Esperar a que termine la compresión
            while process.poll() is None:
                await asyncio.sleep(1)
                if active_compressions.get(message.chat.id, {}).get('cancelled'):
                    process.terminate()
                    break
            
            # Verificar si fue cancelado
            if active_compressions.get(message.chat.id, {}).get('cancelled'):
                await status_message.edit("❌ **Compresión cancelada** ❌")
                return
            
            # Verificar resultado
            if process.returncode != 0:
                error = process.stderr.read()[:1000] if process.stderr else "Error desconocido"
                raise Exception(f"Error en FFmpeg (código {process.returncode}):\n{error}")
            
            # Calcular métricas
            compressed_size = os.path.getsize(compressed_video_path)
            processing_time = datetime.datetime.now() - start_time
            compression_ratio = (1 - compressed_size/original_size) * 100
            
            # Crear descripción con resultados
            caption = (
                f"🗜️𝐕𝐢𝐝𝐞𝐨 𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐝𝐨 𝐂𝐨𝐫𝐫𝐞𝐜𝐭𝐚𝐦𝐞𝐧𝐭𝐞📥\n"
                 "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗼𝗿𝗶𝗴𝗶𝗻𝗮𝗹: {original_size // (1024 * 1024)} MB\n"
                f" ┠• 𝗧𝗮𝗺𝗮ñ𝗼 𝗰𝗼𝗺𝗽𝗿𝗶𝗺𝗶𝗱𝗼: {compressed_size // (1024 * 1024)} MB\n"
                f" ┠• 𝗥𝗲𝗱𝘂𝗰𝗰𝗶𝗼𝗻: {compression_ratio:.1f}%\n"
                f" ┠• 𝗧𝗶𝗲𝗺𝗽𝗼 𝗱𝗲 𝗣𝗿𝗼𝗰𝗲𝘀𝗮𝗺𝗶𝗲𝗻𝘁𝗼: {str(processing_time).split('.')[0]}\n\n"
                 "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
                f"⚙️𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗰𝗶𝗼𝗻 𝘂𝘀𝗮𝗱𝗮⚙️\n"
                f"•𝑹𝒆𝒔𝒐𝒍𝒖𝒄𝒊𝒐‌𝒏:  {video_settings['resolution']}\n" 
                f"•𝑪𝑹𝑭: {video_settings['crf']}\n"
                f"•𝑭𝑷𝑺: {video_settings['fps']}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            )
            
            # Enviar video comprimido
            await client.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=caption
            )
            
            # Eliminar mensaje de estado
            await status_message.delete()
            
        except Exception as e:
            if status_message and not active_compressions.get(message.chat.id, {}).get('cancelled'):
                await status_message.delete()
            await message.reply(f"❌ **Error en compresión**:\n`{str(e)}`")
            
        finally:
            # Limpiar procesos activos
            if message.chat.id in active_compressions:
                del active_compressions[message.chat.id]
                
            # Limpiar archivos temporales
            for path in [original_video_path, compressed_video_path]:
                if path and os.path.exists(path):
                    os.remove(path)
                    
    else:
        await message.reply("⚠️ Responde a un video para comprimirlo")

@app.on_callback_query(filters.regex(r"cancel_(\d+)"))
async def cancel_compression(client, callback_query):
    """Maneja la solicitud de cancelación de compresión"""
    chat_id = int(callback_query.data.split('_')[1])
    
    if chat_id in active_compressions:
        # Marcar como cancelado
        active_compressions[chat_id]['cancelled'] = True
        
        # Eliminar botones
        await callback_query.edit_message_reply_markup(reply_markup=None)
        
        # Confirmar cancelación al usuario
        await callback_query.answer("Compresión cancelada", show_alert=True)
    else:
        await callback_query.answer("No hay compresión activa para cancelar", show_alert=True)

@app.on_message(filters.command(["convert", "comprimir"]))
async def convert_command(client, message):
    """Maneja el comando de compresión de video"""
    await compress_video(client, message)

@app.on_message(filters.command(["calidad", "config"]))
async def quality_command(client, message):
    """Configura los parámetros de compresión"""
    try:
        update_video_settings(message.text.split(maxsplit=1)[1])
        config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
        await message.reply(
            f"⚙️ **Configuración actualizada** ⚙️\n\n{config_text}\n\n"
            f"🗜️Responde a un video con /convert para comprimirlo🛠️"
        )
    except Exception as e:
        await message.reply(f"❌ Error en configuración:\n`{str(e)}`")

@app.on_message(filters.command(["start", "ayuda"]))
async def start_command(client, message):
    """Muestra ayuda y parámetros actuales"""
    config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
    await message.reply(
        "🗜️ **Compress Bot** 🎬\n\n"
        "⚙️ **Configuración Actual** 📝\n"
        f"{config_text}\n\n"
        f"👾 **𝘊𝘳𝘦𝘢𝘥𝘰 𝘱𝘰𝘳 @InfiniteNetworkAdmin** 👾\n"
    )

if __name__ == "__main__":
    print("✅ Bot de compresión de videos iniciado")
    app.run()
