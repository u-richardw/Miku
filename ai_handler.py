# ai_handler.py
import requests
import re
from config import MEMORY_LIMIT  # Keep your absolute import

API_URL = "https://api.deepseek.com/v1/chat/completions"  # Correct API endpoint
API_KEY = "sk-dc69e6b36cc14eb38f9eb24bfb6a7ee7"  # Ensure this is correct

PROMPT_TEMPLATE = """
You are Miku, an AI VTuber known for deadpan humor and sarcasm.
- Stay playful, witty, and mischievous, but never be too aggressive.
- Never use asterisks (*) or stage directions
- Avoid dramatic pauses, sighs, or whispers
- Deliver information directly first, then add humor
- Keep responses concise (1-2 sentences max)
- Always remember numbers/names accurately

Conversation History:
{memory}

User: {prompt}
Miku:"""

def get_ai_response(prompt, memory):
    memory_str = "\n".join(memory[-MEMORY_LIMIT:])
    full_prompt = PROMPT_TEMPLATE.format(memory=memory_str, prompt=prompt)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",  # Ensure this matches your model
        "messages": [{"role": "user", "content": full_prompt}]
    }

    response = requests.post(API_URL, headers=headers, json=data)
    
    try:
        response_json = response.json()
        if "choices" in response_json and response_json["choices"]:
            return clean_ai_response(response_json["choices"][0]["message"]["content"])
        else:
            return f"⚠️ API Error: {response_json}"  # Return error to the bot
    except requests.exceptions.JSONDecodeError:
        return "⚠️ API returned a non-JSON response"

def clean_ai_response(text):
    text = re.sub(r'[*()]', '', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\b(?:sigh|whisper|dramatic pause)\b', '', text, flags=re.IGNORECASE)
    return text.strip()