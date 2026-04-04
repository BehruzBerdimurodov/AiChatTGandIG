"""ManyChat External Request javob formati"""

MAX_MSG_LEN = 620


def format_manychat_response(text: str) -> dict:
    messages = [{"type": "text", "text": p} for p in _split(text, MAX_MSG_LEN)]
    return {"version": "v2", "content": {"messages": messages}}


def _split(text: str, max_len: int) -> list[str]:
    parts = []
    while len(text) > max_len:
        cut = text[:max_len].rfind(" ")
        if cut == -1:
            cut = max_len
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts
