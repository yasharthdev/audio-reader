import os

# to hide the welcome message from pygame
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"


from pathlib import Path
import edge_tts
import asyncio
import pygame

def start_reading(text: str, voice: str, speed: str) -> None:
    # calling the async helper function
    asyncio.run(_generate_audio(text, "temp.mp3", voice, speed))
    # playing the audio asynchronously using pygame.mixer
    # initialize the mixer
    pygame.mixer.init()
    # load the music file
    pygame.mixer.music.load("temp.mp3")    
    # play the music
    pygame.mixer.music.play()

def is_playing_audio() -> bool:
    return pygame.mixer.music.get_busy()

def cleanup_audio() -> None:
    # unload the music file just in case pygame forgot to
    pygame.mixer.music.unload()
    # finally delete the temp file to save space
    Path("temp.mp3").unlink()


async def _generate_audio(text: str, file_path: str, voice: str, speed: str) -> None:
    # edge-tts requires a voice string. "en-US-AriaNeural" is a great default.
    communicate = edge_tts.Communicate(text, voice, rate=speed)
    await communicate.save(file_path)