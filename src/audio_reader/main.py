from audio_reader.reader import load_paragraphs, list_available_books
from audio_reader.player import speak_paragraph

def main():
    list_available_books()
    user_book = input("Which book would you like to read? ")
    paragraphs = load_paragraphs(user_book)
    for para in paragraphs:
        print(para)
        speak_paragraph(para)
        user_input = input("Press Enter to continue or q to quit... ")
        if user_input.lower() == "q":
            break

if __name__ == "__main__":
    main()
