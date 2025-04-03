import ollama
import sounddevice as sd
import numpy as np
import speech_recognition as sr
from TTS.api import TTS
import time
import webrtcvad
import re
import json
import os

# Initialize Coqui TTS
tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")

# Initialize WebRTC VAD
vad = webrtcvad.Vad(2)

# Memory configuration
MEMORY_LIMIT = 5
MEMORY_FILE = "tai_chan_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

conversation_memory = load_memory()

def get_ai_response(prompt, memory):
    memory_str = "\n".join(memory[-MEMORY_LIMIT:])
    
    neuro_prompt = f"""
    You are Tai-Chan, an AI VTuber known for deadpan humor and sarcasm.
    - Stay playful, witty, and mischievous, but never be too aggressive.
    - Never use asterisks (*) or stage directions
    - Avoid dramatic pauses, sighs, or whispers
    - Deliver information directly first, then add humor
    - Keep responses concise (1-2 sentences max)
    - Always remember numbers/names accurately

    Conversation History:
    {memory_str}

    User: {prompt}
    Tai-chan:"""
    
    response = ollama.generate(model='llama3', prompt=neuro_prompt)
    return clean_ai_response(response['response'])

def clean_ai_response(text):
    text = re.sub(r'[*()]', '', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\b(?:sigh|whisper|dramatic pause)\b', '', text, flags=re.IGNORECASE)
    return text.strip()

def prioritize_memory(memory_list):
    prioritized = []
    for msg in memory_list:
        if any(c.isdigit() for c in msg) or "remember" in msg.lower():
            prioritized.insert(0, msg)
        else:
            prioritized.append(msg)
    return prioritized[-MEMORY_LIMIT:]

def clean_text_for_tts(text):
    text = re.sub(r'[^\w\s,.!?\'-]', '', text)
    return ' '.join(text.split())

def ensure_min_length(text, min_chars=10):
    if len(text) < min_chars:
        text += " ..."
    return text

def play_audio(text):
    try:
        text = clean_text_for_tts(text)
        text = ensure_min_length(text)
        text = re.sub(r'(\d+)', r'\1 ', text)
        
        # Add model-specific parameters here
        audio = tts.tts(
            text=text,
            decoder_iterations=500,  # Add here
            noise_scale=0.5,         # Add here
            length_scale=0.9         # Add here
        )
        
        audio_np = np.array(audio, dtype=np.float32)
        audio_np /= np.max(np.abs(audio_np))
        sd.play(audio_np, samplerate=22050)
        sd.wait()
    except Exception as e:
        print(f"TTS Error: {str(e)[:100]}")

def is_speech(audio_data, sample_rate=16000, frame_duration=30):
    frame_size = int(sample_rate * frame_duration / 1000)
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    for i in range(0, len(audio_np), frame_size):
        frame = audio_np[i:i+frame_size].tobytes()
        if vad.is_speech(frame, sample_rate):
            return True
    return False

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone(sample_rate=16000) as source:
        print("Listening... Speak anytime.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        while True:
            try:
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=5)
                if not is_speech(audio.frame_data, sample_rate=16000):
                    continue
                text = recognizer.recognize_google(audio).lower()
                print(f"You said: {text}")
                return text
            except sr.UnknownValueError:
                print("Couldn't understand speech. Try again.")
            except sr.RequestError:
                print("SpeechRecognition error. Check your internet.")
                return None

def typed_input():
    text = input("You (text): ")
    return text.strip()

def main():
    global conversation_memory
    mode = ""
    while mode not in ["v", "t"]:
        mode = input("Choose input mode - voice (v) or text (t): ").lower().strip()
    print("AI VTuber Backend - Chat Started")
    print("Type or say 'exit' to quit.\n")
    try:
        while True:
            if mode == "v":
                user_input = recognize_speech()
            else:
                user_input = typed_input()
            if not user_input:
                continue
            if user_input.lower() == "exit":
                break
            conversation_memory.append(f"User: {user_input}")
            ai_response = get_ai_response(user_input, conversation_memory)
            print(f"AI: {ai_response}")
            conversation_memory.append(f"Tai-chan: {ai_response}")
            play_audio(ai_response)
    finally:
        save_memory(conversation_memory)
        print("\nMemory saved for next session!")

if __name__ == '__main__':
    main()