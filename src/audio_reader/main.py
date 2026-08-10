from audio_reader.reader import load_paragraphs, list_available_books, list_avaiable_voices
from audio_reader.player import download_audio, play_audio, is_playing_audio, cleanup_audio, cleanup_all_audio
from audio_reader.engine import stream_audiobook
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
        # load the paragraphs from the audiobook
        paragraphs = load_paragraphs(args.filepath)
        # stream the audiobook
        stream_audiobook(paragraphs, args.voice, args.speed)
    else:
        print("Please provide book_name.txt or use --list to see available books")
        sys.exit(1)


if __name__ == "__main__":
    main()
