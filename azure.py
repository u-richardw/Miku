import requests
from pydub import AudioSegment
from pydub.playback import play
from io import BytesIO
from config import AZURE_API_KEY, AZURE_REGION, AZURE_TTS_URL, AZURE_VOICE

# Headers for Azure TTS API
AZURE_HEADERS = {
    "Ocp-Apim-Subscription-Key": AZURE_API_KEY,
    "Content-Type": "application/ssml+xml",
    "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3"  # Use 24 kHz MP3
}

def play_audio(text, save_to_file=None):
    try:
        # SSML with Neuro-sama pitch and slight speed adjustment
        body = f"""
        <speak version='1.0' xml:lang='en-US'>
            <voice name='{AZURE_VOICE}'>
                <prosody pitch="+9.5%" rate="1">{text}</prosody>
            </voice>
        </speak>
        """

        # Make the API request
        response = requests.post(AZURE_TTS_URL, headers=AZURE_HEADERS, data=body)

        # Check for errors
        if response.status_code != 200:
            print(f"Azure TTS Error: {response.status_code}, {response.text}")
            return

        # Save audio to file if requested (for Discord playback)
        if save_to_file:
            with open(save_to_file, "wb") as f:
                f.write(response.content)
            
            return  # Skip local playback when saving for Discord

        # Only play locally if no file is being saved (e.g., for main.py local modes)
        audio_data = BytesIO(response.content)
        audio = AudioSegment.from_mp3(audio_data)
        print(f"Playing audio: sample_rate={audio.frame_rate}, channels={audio.channels}")
        play(audio)
        
    except Exception as e:
        print(f"Azure TTS Error: {str(e)[:100]}")