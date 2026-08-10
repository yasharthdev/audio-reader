from audio_reader.reader import load_paragraphs, list_available_books, list_avaiable_voices
from audio_reader.engine import stream_audiobook
from audio_reader.epub_parser import get_epub_paragraphs
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
    # add optional voice argument
    parser.add_argument(
        "-v", "--voice",
        type=str,
        # other male voices, AndrewNeural, BrianNeural
        default="en-US-BrianNeural",
        help="Choose the voice of the audio reader, say Brian"
    )
    # the speech rate or speed argument
    parser.add_argument(
        "-s", "--speed",
        type=str,
        default="+0%",
        help="The speech rate of the reader, say +50 or -50"
    )
    # list all avaiable voices
    parser.add_argument(
        "-lv", "--list-voices",
        action="store_true",
        help="List all avaiable voices for the audio reader"
    )
    # read whatever was passed into the terminal and store it in args
    args = parser.parse_args()

    # ensure that args.speed has a percent sign at the end
    if not args.speed.endswith("%"):
        args.speed += "%"
    # ensure that we have en-US- at the start of the voice model name
    if not args.voice.startswith("en-US-") or not args.voice.endswith("Neural"):
        args.voice = f"en-US-{args.voice}Neural"

    if args.list:
        list_available_books()
        sys.exit(0)

    elif args.list_voices:
        list_avaiable_voices()
        sys.exit(0)

    elif args.filepath:
            # THE ROUTER: Check the extension and parse accordingly
            if args.filepath.endswith('.epub'):
                print(f"[System] Routing to EPUB Parser...")
                paragraphs = get_epub_paragraphs(args.filepath)
            elif args.filepath.endswith('.txt'):
                print(f"[System] Routing to Text Parser...")
                paragraphs = load_paragraphs(args.filepath)
            else:
                print("Error: Unsupported file format. Please provide a .txt or .epub file.")
                sys.exit(1)

            # Safety check: ensure the parser actually found text
            if not paragraphs:
                print("Error: No text could be extracted from the file.")
                sys.exit(1)

            # Stream the audiobook (engine doesn't care where the text came from)
            stream_audiobook(paragraphs, args.voice, args.speed)
            
    else:
        print("Please provide book_name.txt or use --list to see available books")
        sys.exit(1)


if __name__ == "__main__":
    main()
