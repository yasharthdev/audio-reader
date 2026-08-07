from audio_reader.reader import load_paragraphs, list_available_books

def main():
    list_available_books()
    user_book = input("Which book would you like to read? ")
    paragraphs = load_paragraphs(user_book)
    print(f"Total paragraphs loaded: {len(paragraphs)}")
    print(f"Here's the first paragraph of the book you requested:")
    print(paragraphs[0])


if __name__ == "__main__":
    main()
