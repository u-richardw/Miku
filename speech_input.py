# speech_input.py
import discord
from discord.ext import commands
import asyncio
import speech_recognition as sr
import webrtcvad
import numpy as np
import wave
import logging
import os
import time
import uuid
from discord.opus import Decoder
from config import DISCORD_TOKEN, VAD_AGGRESSIVENESS, SAMPLE_RATE
from ai_handler import get_ai_response
from azure import play_audio
from pydub import AudioSegment

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DiscordBot')

# Suppress Discord and FFmpeg logs
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.player').setLevel(logging.WARNING)

# Initialize VAD
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

# Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Bot client with commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Audio parameters
RESPONSE_WAVE_FILENAME = "response.wav"  # Will use temp files later
SAMPLE_RATE_DISCORD = 48000
CHANNELS = 1

# In-memory state tracking
bot.voice_mode = False
bot.awaiting_input_mode = False
bot.joined_voice = False
bot.input_mode = None
bot.conversation_history = []

class AudioBuffer:
    def __init__(self):
        self.buffers = {}
        self.timestamps = {}

    def add_audio(self, data, user):
        user_id = str(user.id)
        if user_id not in self.buffers:
            self.buffers[user_id] = bytearray()
            self.timestamps[user_id] = time.time()
        self.buffers[user_id].extend(data)

    def get_user_audio(self, user):
        user_id = str(user.id)
        return self.buffers.get(user_id, bytearray())

    def get_user_time(self, user):
        user_id = str(user.id)
        return self.timestamps.get(user_id, time.time())

    def clear_user_audio(self, user):
        user_id = str(user.id)
        if user_id in self.buffers:
            self.buffers[user_id] = bytearray()
            self.timestamps[user_id] = time.time()

def is_speech(audio_data, sample_rate=SAMPLE_RATE, frame_duration=30):
    frame_size = int(sample_rate * frame_duration / 1000)
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    for i in range(0, len(audio_np), frame_size):
        frame = audio_np[i:i+frame_size]
        if len(frame) < frame_size:
            continue
        try:
            if vad.is_speech(frame.tobytes(), sample_rate):
                return True
        except:
            return False
    return False

async def recognize_speech(audio_data):
    recognizer = sr.Recognizer()
    temp_wav = f"temp_input_{uuid.uuid4().hex}.wav"
    try:
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE_DISCORD)
            wf.writeframes(audio_data)

        audio_segment = AudioSegment.from_wav(temp_wav)
        audio_segment = audio_segment.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
        audio_segment.export(temp_wav, format="wav")

        with sr.AudioFile(temp_wav) as source:
            audio = recognizer.record(source)

        if not is_speech(audio.frame_data, sample_rate=SAMPLE_RATE):
            logger.info("No speech detected")
            return None

        text = recognizer.recognize_google(audio).lower()
        logger.info(f"Transcribed: {text}")
        return text

    except sr.UnknownValueError:
        logger.info("Couldn't understand speech")
        return None
    except Exception as e:
        logger.error(f"Recognition error: {str(e)[:100]}")
        return None
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

async def play_response_audio(voice_client, text):
    temp_wav = f"temp_response_{uuid.uuid4().hex}.wav"
    try:
        play_audio(text, save_to_file=temp_wav)
        source = discord.FFmpegPCMAudio(temp_wav)
        
        play_event = asyncio.Event()
        def after_playback(error):
            if error:
                logger.error(f"Playback error: {error}")
            play_event.set()
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
        
        voice_client.play(source, after=after_playback)
        await play_event.wait()

    except Exception as e:
        logger.error(f"Audio play error: {str(e)[:100]}")
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel and not hasattr(bot, 'vc'):
        logger.info(f"Joined voice channel: {after.channel.name}")
        voice_client = await after.channel.connect()
        bot.vc = voice_client
        bot.voice_mode = True
        await start_listening(voice_client)

async def start_listening(voice_client):
    audio_buffer = AudioBuffer()
    while voice_client.is_connected():
        await asyncio.sleep(1)
        for user_id in list(audio_buffer.buffers.keys()):
            user = bot.get_user(int(user_id))
            if not user:
                continue
            user_audio = audio_buffer.get_user_audio(user)
            if user_audio and (time.time() - audio_buffer.get_user_time(user) > 5):
                text = await recognize_speech(user_audio)
                audio_buffer.clear_user_audio(user)
                if text:
                    response = get_ai_response(text, bot.conversation_history)
                    await voice_client.channel.send(response)
                    await play_response_audio(voice_client, response)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    if bot.awaiting_input_mode:
        if message.content.lower() in ['voice', 'text']:
            bot.input_mode = message.content.lower()
            bot.awaiting_input_mode = False
            bot.voice_mode = (bot.input_mode == 'voice')
            await message.channel.send(f"Input mode set to {bot.input_mode}")
            return
        else:
            await message.channel.send("Please choose 'voice' or 'text'")
            return

    if bot.voice_mode:
        logger.info("Ignoring message (voice mode active)")
        return

    response = get_ai_response(message.content, bot.conversation_history)
    if response:
        await message.channel.send(response)
        if hasattr(bot, 'vc') and bot.vc.is_connected():
            await play_response_audio(bot.vc, response)

@bot.command()
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        voice_client = await ctx.author.voice.channel.connect()
        bot.vc = voice_client
        bot.joined_voice = True
        bot.awaiting_input_mode = True
        await ctx.send(f"Joined {ctx.author.voice.channel.name}")
        await ctx.send("Choose input mode: 'voice' or 'text'")
    else:
        await ctx.send("You're not in a voice channel!")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        bot.vc = None
        bot.voice_mode = False
        bot.joined_voice = False
        bot.awaiting_input_mode = False
        await ctx.send("Left voice channel!")
    else:
        await ctx.send("I'm not in a voice channel!")

bot.run(DISCORD_TOKEN)