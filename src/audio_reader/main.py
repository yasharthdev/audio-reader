from audio_reader.reader import load_paragraphs, list_available_books
from audio_reader.player import speak_paragraph
import argparse
import sys

def main():
    # initializing the parser
    parser = argparse.ArgumentParser(description="A CLI AudioBook Player")
    # the optional filepath argument
    parser.add_argument("filepath", nargs="?", help="The path to the book's .txt file")
    parser.add_argument(
        "-l", "--list", action="store_true", help="List all available books"
    )
    # read whatever was passed into the terminal and store it in args
    args = parser.parse_args()
    if args.list:
        list_available_books()
        sys.exit(0)
    elif args.filepath:
        paragraphs = load_paragraphs(args.filepath)
        for para in paragraphs:
            print(para)
            speak_paragraph(para)
            user_input = input("Press Enter to continue or q to quit... ")
            if user_input.lower() == "q":
                break
    else:
        print("Please provide book_name.txt or use --list to see available books")
        sys.exit(1)


if __name__ == "__main__":
    main()
