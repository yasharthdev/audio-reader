from audio_reader.reader import load_paragraphs, list_available_books, list_avaiable_voices
from audio_reader.player import start_reading, is_playing_audio, cleanup_audio
import argparse
import sys
import pygame

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
        default="en-US-AriaNeural",
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
        paragraphs = load_paragraphs(args.filepath)
        for para in paragraphs:
            print(para)
            try:
                start_reading(para, args.voice, args.speed)
                while is_playing_audio():
                    pygame.time.Clock().tick(10)            
            # clean up the audio every time, even in accidental shutdown cases 
            finally:
                cleanup_audio()
    else:
        print("Please provide book_name.txt or use --list to see available books")
        sys.exit(1)


if __name__ == "__main__":
    main()
