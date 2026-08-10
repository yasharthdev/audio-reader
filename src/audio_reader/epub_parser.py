import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def get_epub_paragraphs(book_name: str) -> list[str]:
    """Parses an EPUB file and returns a flat list of text paragraphs."""
    try:
        filepath = f"books/{book_name}"
        book = epub.read_epub(filepath)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        return []

    paragraphs = []
    
    # Iterate through the book's items in their official reading order
    for item in book.get_items():
        # We only care about document files containing text (HTML/XHTML)
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # BeautifulSoup parses the raw HTML and makes it searchable
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Find every single paragraph tag and extract the raw text
            for p_tag in soup.find_all('p'):
                text = p_tag.get_text(strip=True)
                
                # Ignore empty strings or whitespace
                if text:
                    paragraphs.append(text)
                    
    return paragraphs