# main.py
import multiprocessing
import subprocess
import os
import sys
import logging
import threading
import time
from ai_handler import get_ai_response
from speech_input import recognize_live_speech, typed_input
from azure import play_audio

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Main')

# Signal files
BOT_JOINED_SIGNAL = "bot_joined.signal"
INPUT_MODE_SIGNAL = "input_mode.signal"
VOICE_MODE_SIGNAL = "voice_mode.signal"

# Function to stream subprocess output in a separate thread
def stream_output(process, logger, prefix):
    while True:
        stdout_line = process.stdout.readline()
        if stdout_line:
            logger.info(f"{prefix} output: {stdout_line.strip()}")
        stderr_line = process.stderr.readline()
        if stderr_line:
            logger.error(f"{prefix} error: {stderr_line.strip()}")
        if process.poll() is not None:
            logger.info(f"{prefix} process terminated with return code {process.poll()}")
            break

# Function to run the Discord bot as a subprocess
def run_discord_bot():
    logger.info("Starting speech_input.py")
    python_exe = sys.executable
    bot_script = os.path.join(os.path.dirname(__file__), 'speech_input.py')
    if not os.path.exists(bot_script):
        logger.error(f"speech_input.py not found at {bot_script}")
        return None

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [python_exe, bot_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    output_thread = threading.Thread(target=stream_output, args=(process, logger, "speech_input.py"))
    output_thread.daemon = True
    output_thread.start()
    logger.info("Discord bot subprocess launched")
    return process

def get_response(user_input, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    conversation_history.append(f"User: {user_input}")
    ai_response = get_ai_response(user_input, conversation_history)
    conversation_history.append(f"Tai-chan: {ai_response}")
    return ai_response

def main():
    # Remove any existing signal files
    for signal_file in [BOT_JOINED_SIGNAL, INPUT_MODE_SIGNAL, VOICE_MODE_SIGNAL]:
        if os.path.exists(signal_file):
            os.remove(signal_file)
            logger.info(f"Removed existing signal file: {signal_file}")

    # Start the Discord bot automatically
    discord_process = run_discord_bot()
    if discord_process is None:
        logger.error("Failed to start Discord bot, exiting.")
        return

    # Wait for the bot to join a voice channel
    logger.info(f"Waiting for user to join a voice channel and use !join command. Checking for {BOT_JOINED_SIGNAL}...")
    timeout = time.time() + 60  # Wait up to 60 seconds
    while not os.path.exists(BOT_JOINED_SIGNAL):
        if discord_process.poll() is not None:
            logger.error(f"Discord bot process terminated unexpectedly with code {discord_process.poll()}")
            return
        if time.time() > timeout:
            logger.error(f"Timeout waiting for {BOT_JOINED_SIGNAL} after 60 seconds")
            return
        logger.debug(f"Checking for {BOT_JOINED_SIGNAL}... (exists: {os.path.exists(BOT_JOINED_SIGNAL)})")
        time.sleep(1)

    logger.info(f"Signal file {BOT_JOINED_SIGNAL} detected, bot has joined voice channel")

    # Wait for the user to select input mode
    logger.info(f"Waiting for user to select input mode. Checking for {INPUT_MODE_SIGNAL}...")
    timeout = time.time() + 60  # Wait up to 60 seconds
    while not os.path.exists(INPUT_MODE_SIGNAL):
        if discord_process.poll() is not None:
            logger.error(f"Discord bot process terminated unexpectedly with code {discord_process.poll()}")
            return
        if time.time() > timeout:
            logger.error(f"Timeout waiting for {INPUT_MODE_SIGNAL} after 60 seconds")
            return
        logger.debug(f"Checking for {INPUT_MODE_SIGNAL}... (exists: {os.path.exists(INPUT_MODE_SIGNAL)})")
        time.sleep(1)

    # Read the input mode
    try:
        with open(INPUT_MODE_SIGNAL, "r") as f:
            mode = f.read().strip()
        logger.info(f"Input mode selected: {mode}")
    except Exception as e:
        logger.error(f"Error reading input mode signal file: {str(e)}")
        mode = "text"  # Default to text mode on error

    if mode not in ["voice", "text"]:
        logger.error(f"Invalid input mode '{mode}', defaulting to text")
        mode = "text"

    print("AI VTuber Backend - Chat Started (Local Mode)")
    print(f"Using {mode} input mode. Say or type 'exit' to quit.\n")

    # In-memory conversation history
    conversation_history = []

    try:
        if mode == "voice":
            # Create voice mode signal to disable chat processing in bot
            logger.info("Entering voice mode...")
            try:
                with open(VOICE_MODE_SIGNAL, "w") as f:
                    f.write("active")
                logger.info("Voice mode signal file created")
            except Exception as e:
                logger.error(f"Error creating voice mode signal file: {str(e)}")
                return
            while True:
                logger.info("Starting microphone listening loop...")
                user_input = recognize_live_speech()
                if not user_input:
                    logger.info("No speech detected, retrying...")
                    time.sleep(1)  # Wait before next attempt
                    continue
                if user_input.lower() == "exit":
                    logger.info("Exit command detected, exiting voice mode")
                    break
                conversation_history.append(f"User: {user_input}")
                ai_response = get_response(user_input, conversation_history)
                print(f"AI: {ai_response}")
                play_audio(ai_response)
        else:  # text mode
            logger.info("Entering text mode...")
            while True:
                user_input = typed_input()
                if not user_input:
                    continue
                if user_input.lower() == "exit":
                    logger.info("Exit command detected, exiting text mode")
                    break
                conversation_history.append(f"User: {user_input}")
                ai_response = get_response(user_input, conversation_history)
                print(f"AI: {ai_response}")
                play_audio(ai_response)

    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
    finally:
        print("\nSession ended!")
        # Remove voice mode signal
        if os.path.exists(VOICE_MODE_SIGNAL):
            os.remove(VOICE_MODE_SIGNAL)
            logger.info("Removed voice mode signal file")
        if discord_process:
            discord_process.terminate()
            discord_process.join()
            logger.info("Discord bot process terminated.")
        # Clean up signal files
        for signal_file in [BOT_JOINED_SIGNAL, INPUT_MODE_SIGNAL]:
            if os.path.exists(signal_file):
                os.remove(signal_file)
                logger.info(f"Cleaned up signal file: {signal_file}")

if __name__ == '__main__':
    main()