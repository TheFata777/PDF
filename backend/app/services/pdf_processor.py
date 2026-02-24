import fitz  # PyMuPDF
from typing import List, Dict

def extract_text_chunks(pdf_path: str, chunk_size: int = 1000) -> List[Dict]:
    """
    Извлекает текст из PDF с помощью PyMuPDF, разбивает на чанки.
    """
    chunks = []
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if not text:
            continue
        # Разбиваем текст на фрагменты
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i+chunk_size]
            chunks.append({
                "page_number": page_num + 1,
                "chunk_index": i // chunk_size,
                "content": chunk_text
            })
    doc.close()
    return chunks