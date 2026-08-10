from audio_reader.player import download_audio, play_audio, is_playing_audio
from audio_reader.player import cleanup_all_audio, cleanup_audio
from pynput import keyboard
import threading
import queue
import pygame
import subprocess

def stream_audiobook(paragraphs: list[str], voice: str, speed: str) -> None:
    """Handles all threading, queuing, and playback of the audiobook"""

    # initialize the playback state
    playback_state = {"quit": False, "skip": False, "pause": False, "listening": True}

    # pynput automatically passes a key here, whenever pressed by the user
    def on_press(key):
        try:
            # force python to check key first to trigger AttributeError for special keys
            character = key.char
            if playback_state["listening"]:
                # key.char gives the actual letter pressed (like 'q' or 's')
                if character == "q":
                    playback_state["quit"] = True
                elif character == "s":
                    playback_state["skip"] = True

        except AttributeError:
            # the master toggle, one that always listens
            if key == keyboard.Key.esc:
                playback_state["listening"] = not playback_state["listening"]
                # print status message
                if playback_state["listening"]:
                    print("\n[!] Listener ON (App controls active)")
                else:
                    print("\n[!] Listener OFF (Safe to type elsewhere)")
            
            # space bar only works if master toggle is ON
            elif key == keyboard.Key.space and playback_state["listening"]:
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
        args=(paragraphs, voice, speed),
        daemon=True
    ).start()

    for para in paragraphs:
        # Reset the keys for every new paragraph
        playback_state["skip"] = False
        playback_state["pause"] = False
    
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