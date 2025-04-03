from TTS.api import TTS
import numpy as np
import sounddevice as sd
import re
from config import TTS_MODEL, SAMPLE_RATE

tts = TTS(model_name=TTS_MODEL)

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
        
        audio = tts.tts(text=text)
        audio_np = np.array(audio, dtype=np.float32)
        audio_np /= np.max(np.abs(audio_np))
        
        # Play at TTS sample rate (22050 Hz)
        sd.play(audio_np, samplerate=SAMPLE_RATE)
        sd.wait()
    except Exception as e:
        print(f"TTS Error: {str(e)[:100]}")