import json
import os
from config import MEMORY_FILE, MEMORY_LIMIT  # Absolute import

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def prioritize_memory(memory_list):
    prioritized = []
    for msg in memory_list:
        if any(c.isdigit() for c in msg) or "remember" in msg.lower():
            prioritized.insert(0, msg)
        else:
            prioritized.append(msg)
    return prioritized[-MEMORY_LIMIT:]