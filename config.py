# Azure TTS Configuration
DISCORD_TOKEN = "MTAzODI3NDA4MDk4MzUwMjk0OA.GjhEJL.rs-PONDGGsEaP_EcXwPAjqgu0kCto8_ThJypic"
AZURE_API_KEY = "A3B7CxnCrdzixMNPhiC32zBj1feidWfwjyKN22Js3JUIrAXUFm0dJQQJ99BCACYeBjFXJ3w3AAAYACOGRRXw"  # Replace with your Azure API key
AZURE_REGION = "eastus"  # Replace with your Azure region
AZURE_TTS_URL = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
AZURE_VOICE = "en-US-SaraNeural"  # Example voice (choose from Azure's voice list)

# Audio settings
SAMPLE_RATE = 24000  # Watson supports 22050 Hz

# Voice Activity Detection (VAD) settings
VAD_AGGRESSIVENESS = 2  # 0 = least aggressive, 3 = most aggressive

# Memory settings
MEMORY_LIMIT = 5
MEMORY_FILE = "tai_chan_memory.json"