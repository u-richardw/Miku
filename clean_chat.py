import re

def clean_chat_data():
    with open("chat_log.txt", "r", encoding="utf-8") as file:
        lines = file.readlines()

    cleaned_lines = []
    for line in lines:
        cleaned = re.sub(r"http\S+|@\S+|#[\S]+", "", line).strip().split(": ", 1)
        if len(cleaned) == 2 and len(cleaned[1]) > 2:  # Ignore short messages
            cleaned_lines.append(cleaned[1])

    with open("clean_chat_data.txt", "w", encoding="utf-8") as file:
        file.writelines("\n".join(cleaned_lines))

clean_chat_data()
