import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def get_epub_data(filepath: str) -> tuple[list[str], list[dict]]:
    """Parses an EPUB file and returns a flat list of text paragraphs and a chapter map."""
    try:
        book = epub.read_epub(filepath)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        return [], []

    paragraphs = []
    chapter_map = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                text = tag.get_text(strip=True)
                if not text:
                    continue
                
                if tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    chapter_map.append({
                        "title": text,
                        "start_index": len(paragraphs)
                    })
                    paragraphs.append(text)
                elif tag.name == 'p':
                    paragraphs.append(text)
                    
    return paragraphs, chapter_map

def get_epub_paragraphs(filepath: str) -> list[str]:
    """Parses an EPUB file and returns a flat list of text paragraphs."""
    paragraphs, _ = get_epub_data(filepath)
    return paragraphs