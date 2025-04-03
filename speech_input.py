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
from discord.opus import Decoder
from config import DISCORD_TOKEN, VAD_AGGRESSIVENESS, SAMPLE_RATE
from ai_handler import get_ai_response
from azure import play_audio
from pydub import AudioSegment

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DiscordBot')

# Suppress Discord and FFmpeg logs (INFO level)
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

# Audio recording parameters
WAVE_OUTPUT_FILENAME = "input.wav"
RESPONSE_WAVE_FILENAME = "response.wav"
SAMPLE_RATE_DISCORD = 48000  # Discord uses 48kHz by default
CHANNELS = 1

# Signal file for voice mode
VOICE_MODE_SIGNAL = "voice_mode.signal"

# Custom audio buffer
class AudioBuffer:
    def __init__(self):
        self.buffers = {}  # Dictionary to store audio buffers per user
        self.timestamps = {}  # Timestamps for each user's audio

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
    try:
        with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(SAMPLE_RATE_DISCORD)
            wf.writeframes(audio_data)

        audio_segment = AudioSegment.from_wav(WAVE_OUTPUT_FILENAME)
        audio_segment = audio_segment.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
        audio_segment.export(WAVE_OUTPUT_FILENAME, format="wav")

        with sr.AudioFile(WAVE_OUTPUT_FILENAME) as source:
            audio = recognizer.record(source)

        if not is_speech(audio.frame_data, sample_rate=SAMPLE_RATE):
            logger.info("No speech detected in audio.")
            return None

        text = recognizer.recognize_google(audio).lower()
        logger.info(f"Transcribed text: {text}")
        return text

    except sr.UnknownValueError:
        logger.info("Couldn't understand speech.")
        return None
    except sr.RequestError as e:
        logger.error(f"SpeechRecognition error: {str(e)[:100]}")
        return None
    finally:
        if os.path.exists(WAVE_OUTPUT_FILENAME):
            os.remove(WAVE_OUTPUT_FILENAME)

# New function for live microphone input
def recognize_live_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        logger.info("Listening to microphone... Say something!")
        audio = recognizer.listen(source, timeout=5)  # Listen for 5 seconds
    try:
        text = recognizer.recognize_google(audio).lower()
        logger.info(f"Transcribed from microphone: {text}")
        return text
    except sr.UnknownValueError:
        logger.info("Couldn't understand speech from microphone.")
        return None
    except sr.RequestError as e:
        logger.error(f"SpeechRecognition error: {str(e)[:100]}")
        return None
    except Exception as e:
        logger.error(f"Microphone error: {str(e)[:100]}")
        return None

# In-memory conversation history
conversation_history = []

def get_response(user_input):
    global conversation_history
    conversation_history.append(f"User: {user_input}")
    ai_response = get_ai_response(user_input, conversation_history)
    conversation_history.append(f"Miku: {ai_response}")
    return ai_response

# Bot events
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    print(f'Logged in as {bot.user}')
    # No auto-join; wait for !join command

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel is not None and not hasattr(bot, 'vc'):
        logger.info(f"Bot joined voice channel: {after.channel.name}")
        if not bot.voice_clients:
            voice_client = await after.channel.connect()
            bot.vc = voice_client
            await start_listening(voice_client)

async def start_listening(voice_client):
    audio_buffer = AudioBuffer()
    while voice_client.is_connected():
        await asyncio.sleep(1)  # Placeholder for audio processing
        for user_id in list(audio_buffer.buffers.keys()):
            user = bot.get_user(int(user_id))
            if not user:
                continue
            user_audio = audio_buffer.get_user_audio(user)
            if user_audio and (time.time() - audio_buffer.get_user_time(user) > 5):
                text = await recognize_speech(user_audio)
                audio_buffer.clear_user_audio(user)
                if text:
                    channel = voice_client.channel
                    await channel.send(f"{user.display_name} said: {text}")
                    response = get_response(text)
                    if response:
                        await channel.send(response)
                        await play_response_audio(voice_client, response)
        await asyncio.sleep(1)

async def play_response_audio(voice_client, text):
    try:
        play_audio(text, save_to_file=RESPONSE_WAVE_FILENAME)
        source = discord.FFmpegPCMAudio(RESPONSE_WAVE_FILENAME)
        voice_client.play(source)
        audio = AudioSegment.from_wav(RESPONSE_WAVE_FILENAME)
        duration = len(audio) / 1000.0
        await asyncio.sleep(duration)
    except Exception as e:
        logger.error(f"Error playing response audio: {str(e)[:100]}")
    finally:
        if os.path.exists(RESPONSE_WAVE_FILENAME):
            os.remove(RESPONSE_WAVE_FILENAME)

# Handle text messages
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # Check for input mode selection after joining
    if hasattr(bot, 'awaiting_input_mode') and bot.awaiting_input_mode:
        if message.content.lower() in ['voice', 'text']:
            mode = message.content.lower()
            with open("input_mode.signal", "w") as f:
                f.write(mode)
            logger.info(f"User selected input mode: {mode}, signaled to main.py")
            bot.awaiting_input_mode = False
            await message.channel.send(f"Input mode set to {mode}. You can now provide input locally.")
            return
        else:
            await message.channel.send("Please choose 'voice' or 'text'.")
            return

    # Ignore chat messages if in voice mode
    if os.path.exists(VOICE_MODE_SIGNAL):
        logger.info(f"Ignoring chat message '{message.content}' due to voice mode")
        return

    # Handle regular messages
    logger.info(f"Received message from {message.author.name}: {message.content}")
    response = get_response(message.content)
    if response:
        await message.channel.send(response)
        if bot.vc and bot.vc.is_connected():
            await play_response_audio(bot.vc, response)

# Bot commands
@bot.command()
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        voice_client = await ctx.author.voice.channel.connect()
        bot.vc = voice_client
        await ctx.send(f"Joined {ctx.author.voice.channel.name}")
        # Signal to main.py that the bot has joined
        with open("bot_joined.signal", "w") as f:
            f.write("joined")
        logger.info("Signaled main.py that bot has joined voice channel")
        # Ask user to choose input mode
        bot.awaiting_input_mode = True
        await ctx.send("Please choose your input mode: type 'voice' or 'text'.")
        await start_listening(voice_client)
    else:
        await ctx.send("You are not in a voice channel!")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        bot.vc = None
        bot.awaiting_input_mode = False
        # Remove voice mode signal
        if os.path.exists(VOICE_MODE_SIGNAL):
            os.remove(VOICE_MODE_SIGNAL)
        await ctx.send("Left the voice channel!")
        # Remove signal files
        for signal_file in ["bot_joined.signal", "input_mode.signal"]:
            if os.path.exists(signal_file):
                os.remove(signal_file)
    else:
        await ctx.send("I’m not in a voice channel!")

# Run the bot
bot.run(DISCORD_TOKEN)