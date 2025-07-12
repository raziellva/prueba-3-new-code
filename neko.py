import os
import datetime
import subprocess
from pyrogram import Client, filters, types
from pyrogram.types import Message

# Configuración del bot
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('TOKEN')

app = Client("video_compressor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Configuración predeterminada para compresión de video
video_settings = {
    'resolution': '854x480',
    'crf': '32',
    'audio_bitrate': '60k',
    'fps': '18',
    'preset': 'veryfast',
    'codec': 'libx264'
}

def update_video_settings(command: str):
    """Actualiza la configuración de compresión de video"""
    settings = command.split()
    for setting in settings:
        key, value = setting.split('=')
        if key in video_settings:
            video_settings[key] = value

def estimate_compression_ratio(crf: str) -> int:
    """Estima el porcentaje de compresión basado en el valor CRF"""
    try:
        crf_value = int(crf)
        # Mapeo de valores CRF a porcentajes estimados
        if crf_value < 23:
            return 30
        elif 23 <= crf_value < 27:
            return 50
        elif 27 <= crf_value < 31:
            return 65
        elif 31 <= crf_value < 35:
            return 75
        else:
            return 85
    except ValueError:
        return 60  # Valor predeterminado

async def compress_video(client: Client, message: Message):
    """Comprime videos usando FFmpeg con configuración personalizable"""
    status_message = None  # Para almacenar el mensaje de estado
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
            
            # Calcular porcentaje estimado
            estimated_ratio = estimate_compression_ratio(video_settings['crf'])
            
            # Informar al usuario
            status_message = await message.reply(
                f"🗜️𝐂𝐨𝐦𝐩𝐫𝐢𝐦𝐢𝐞𝐧𝐝𝐨 𝐕𝐢𝐝𝐞𝐨 📹...\n"
                f"⚙️ Configuración:\n"
                f"  • Resolución: {video_settings['resolution']}\n"
                f"  • CRF: {video_settings['crf']}\n"
                f"  • FPS: {video_settings['fps']}"
            )
            
            # Ejecutar compresión
            start_time = datetime.datetime.now()
            process = subprocess.run(ffmpeg_command, stderr=subprocess.PIPE, text=True)
            
            # Verificar resultado
            if process.returncode != 0:
                raise Exception(f"Error en FFmpeg:\n{process.stderr[:1000]}")
            
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
                f" ┖• 𝗧𝗶𝗲𝗺𝗽𝗼 𝗱𝗲 𝗽𝗿𝗼𝗰𝗲𝘀𝗮𝗺𝗶𝗲𝗻𝘁𝗼: {processing_time_str}\n"
                 "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
                f"⚙️𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗮𝗰𝗶𝗼𝗻 𝘂𝘀𝗮𝗱𝗮⚙️\n"
                f"•𝑹𝒆𝒔𝒐𝒍𝒖𝒄𝒊𝒐‌𝒏:  {video_settings['resolution']}\n" 
                f"•𝑪𝑹𝑭: {video_settings['crf']}\n"
                f"•𝑭𝑷𝑺: {video_settings['fps']}\n"
                "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            )
            
            # Enviar video comprimido y eliminar mensaje de estado
            await client.send_video(
                chat_id=message.chat.id,
                video=compressed_video_path,
                caption=caption
            )
            
            # Eliminar mensaje de estado si existe
            if status_message:
                await status_message.delete()
            
        except Exception as e:
            await message.reply(f"❌ **Error en compresión**:\n`{str(e)}`")
            # Intentar eliminar mensaje de estado si existe
            if status_message:
                try:
                    await status_message.delete()
                except:
                    pass
            
        finally:
            # Limpiar archivos temporales
            for path in [original_video_path, compressed_video_path]:
                if path and os.path.exists(path):
                    os.remove(path)
                    
    else:
        await message.reply("⚠️ Responde a un video para comprimirlo")

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
            f"⚙️ **Configuración actualizada**\n\n{config_text}\n\n"
            f"Ahora responde a un video con /convert"
        )
    except Exception as e:
        await message.reply(f"❌ Error en configuración:\n`{str(e)}`")

@app.on_message(filters.command(["start", "ayuda"]))
async def start_command(client, message):
    """Muestra ayuda y parámetros actuales"""
    config_text = "\n".join([f"• **{k}**: `{v}`" for k, v in video_settings.items()])
    await message.reply(
        "🎥 **Video Compressor Bot**\n\n"
        "**Comandos disponibles:**\n"
        "• /convert - Comprime un video (responde al video)\n"
        "• /calidad - Configura parámetros (ej: `/calidad resolution=1280x720 crf=28`)\n\n"
        "**Parámetros actuales:**\n"
        f"{config_text}\n\n"
        "⚙️ Parámetros modificables: `resolution`, `crf`, `fps`, `preset`, `audio_bitrate`, `codec`"
    )

if __name__ == "__main__":
    print("✅ Bot de compresión de videos iniciado")
    app.run()
