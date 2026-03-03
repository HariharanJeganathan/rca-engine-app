import re
import json
from typing import List

INC_PATTERN = re.compile(r'INC\d{7,}', re.IGNORECASE)

def chunk_text(text: str, max_chars: int) -> List[str]:
    """Split text into chunks"""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            words = sentence.split()
            temp = ""
            for word in words:
                if len(temp) + len(word) + 1 <= max_chars:
                    temp += word + " "
                else:
                    if temp:
                        chunks.append(temp.strip())
                    temp = word + " "
            if temp:
                chunks.append(temp.strip())
        else:
            if len(current_chunk) + len(sentence) + 1 > max_chars:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
            else:
                current_chunk += sentence + " "
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text]

def safe_json_loads(json_str: str) -> dict | None:
    """Safely parse JSON string"""
    if not json_str:
        return None
    
    try:
        json_str = json_str.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        
        return json.loads(json_str.strip())
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        return None