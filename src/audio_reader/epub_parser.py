import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def _parse_toc(toc_items, href_to_index):
    """Recursively parse book.toc into a nested list of dicts."""
    parsed_toc = []
    for item in toc_items:
        if isinstance(item, tuple):
            section, sub_items = item
            title = section.title
            href = section.href
            
            # Map exact anchor if exists, otherwise fallback to base filename
            start_index = href_to_index.get(href)
            if start_index is None and href:
                base_href = href.split('#')[0]
                start_index = href_to_index.get(base_href, 0)
            elif start_index is None:
                start_index = 0
                
            parsed_toc.append({
                "title": title,
                "start_index": start_index,
                "children": _parse_toc(sub_items, href_to_index)
            })
        elif isinstance(item, epub.Link):
            title = item.title
            href = item.href
            
            start_index = href_to_index.get(href)
            if start_index is None and href:
                base_href = href.split('#')[0]
                start_index = href_to_index.get(base_href, 0)
            elif start_index is None:
                start_index = 0
                
            parsed_toc.append({
                "title": title,
                "start_index": start_index,
                "children": []
            })
    return parsed_toc

def get_epub_data(filepath: str) -> tuple[list[str], list[dict]]:
    """Parses an EPUB file and returns a flat list of text paragraphs and a hierarchical chapter map."""
    try:
        book = epub.read_epub(filepath)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        return [], []

    paragraphs = []
    href_to_index = {}
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            href_to_index[item.file_name] = len(paragraphs)
            
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
                text = tag.get_text(strip=True)
                if not text:
                    continue
                
                if tag.get('id'):
                    href_to_index[f"{item.file_name}#{tag.get('id')}"] = len(paragraphs)
                    
                paragraphs.append(text)
                    
    chapter_map = _parse_toc(book.toc, href_to_index)
    return paragraphs, chapter_map

def get_epub_paragraphs(filepath: str) -> list[str]:
    """Parses an EPUB file and returns a flat list of text paragraphs."""
    paragraphs, _ = get_epub_data(filepath)
    return paragraphs