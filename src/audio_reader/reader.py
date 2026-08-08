from pathlib import Path

def load_paragraphs(filepath: str) -> list[str]:
    current_dir = Path.cwd()
    book_path = current_dir / "books" / filepath
    if not book_path.exists():
        raise FileNotFoundError("The given file doesn't exist")
    with open(book_path, "r", encoding="utf-8") as file:
        contents = file.read()
    # paragraphs in a .txt file are usually split by two newline chars 
    paras = contents.strip().split("\n\n")
    # project gutenberg adds a single \n every 70 characters
    clean_paras = [para.strip().replace("\n", " ") for para in paras if para]
    return clean_paras

def list_available_books() -> None:
    current_dir = Path.cwd()
    book_dir = current_dir / "books"
    if not book_dir.exists():
        raise FileNotFoundError("Books dir doesn't exist")
    books = []
    for book in book_dir.iterdir():
        books.append(book.name)

    print("List of available books:")
    for index, book in enumerate(books, start=1):
        print(f"{index}. {book}")
