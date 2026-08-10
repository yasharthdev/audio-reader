from audio_reader.reader import load_paragraphs, list_available_books, list_avaiable_voices
from audio_reader.player import download_audio, play_audio, is_playing_audio, cleanup_audio, cleanup_all_audio
from pynput import keyboard
import argparse
import sys
import pygame
import subprocess
import threading
import queue

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
        paragraphs = load_paragraphs(args.filepath)

        
        # pynput automatically passes a key here, whenever pressed by the user
        def on_press(key):
            try:
                # key.char gives the actual letter pressed (like 'q' or 's')
                if key.char == "q":
                    playback_state["quit"] = True
                elif key.char == "s":
                    playback_state["skip"] = True
            except AttributeError:
                # this is the block where keys like shift, enter, etc are sent
                if key == keyboard.Key.space:
                    # if pause if False, it changes to True and vice versa
                    playback_state["pause"] = not(playback_state["pause"])


        # start the listener once in the background
        listener = keyboard.Listener(on_press=on_press)
        # start() runs in the background without freezing python
        listener.start()

        # the tray that holds exactly five files
        audio_queue = queue.Queue(maxsize=5)

        def background_downloader(paragraphs: list[str], voice: str, speed: str) -> None:
            """Download 5 paras, put them in audio_queue"""
            for i, para in enumerate(paragraphs):
                filepath = f"temp_{i}.mp3"
                # download the file
                download_audio(para, filepath, voice, speed)
                # Put it on the tray (if the tray is full, it waits automatically)
                audio_queue.put(filepath)

        # run the downloader thread in the background
        threading.Thread(
            target=background_downloader,
            args=(paragraphs, args.voice, args.speed),
            daemon=True
        ).start()
        
        for i, para in enumerate(paragraphs):
            playback_state = {"quit": False, "skip": False, "pause": False}

            # to clear the terminal before printing any paragraphs
            subprocess.run(["clear"])            
            print(para)

            try:
                audio_file = audio_queue.get()
                play_audio(audio_file)

                was_paused = False

                while True:
                    # check for pause
                    if playback_state["pause"] and not was_paused:
                        pygame.mixer.music.pause()
                        was_paused = True
                    # check if we unpaused
                    elif not playback_state["pause"] and was_paused:
                        pygame.mixer.music.unpause()
                        was_paused = False
                        # give pygame 50ms to wake up before checking get_busy()
                        pygame.time.wait(50)
                    # if we aren't paused and the audio isn't playing, break the loop
                    if not playback_state["pause"] and not is_playing_audio():
                        break
                    
                    # check for skip
                    if playback_state["skip"]:
                        pygame.mixer.music.stop()
                        # exit the while loop and continue to next para
                        break
                    # check for quit
                    if playback_state["quit"]:
                        pygame.mixer.music.stop()
                        # exit the while loop **
                        break
                    pygame.time.Clock().tick(10)            

            # clean up the audio every time, even in accidental shutdown cases 
            finally:
                cleanup_audio(audio_file)

            # ** break the for loop to completely quit the program
            if playback_state["quit"]:
                break

        # clean up the background listener after we're done
        listener.stop()

        # delete any leftover downloaded files by the downloader
        cleanup_all_audio()
    else:
        print("Please provide book_name.txt or use --list to see available books")
        sys.exit(1)


if __name__ == "__main__":
    main()
