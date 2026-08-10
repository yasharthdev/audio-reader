import os

# to hide the welcome message from pygame
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"


from pathlib import Path
import edge_tts
import asyncio
import pygame
import glob

def download_audio(text: str, filepath: str, voice: str, speed: str) -> None:
    asyncio.run(_generate_audio(text, filepath, voice, speed))

def play_audio(filepath: str) -> None:
    # playing the audio asynchronously using pygame.mixer
    # initialize the mixer
    pygame.mixer.init()
    # load the music file
    pygame.mixer.music.load(filepath)    
    # play the music
    pygame.mixer.music.play() 

def is_playing_audio() -> bool:
    return pygame.mixer.music.get_busy()

def cleanup_audio(filepath: str) -> None:
    # unload the music file just in case pygame forgot to
    pygame.mixer.music.unload()
    # delete the audio file
    Path(filepath).unlink(missing_ok=True)
    
    # delete the matching vtt file
    vtt_path = filepath.replace(".mp3", ".srt")
    Path(vtt_path).unlink(missing_ok=True)

def cleanup_all_audio() -> None:
    """Sweeps the directory and deletes any leftover temporary files."""
    # Find all mp3 AND vtt files
    orphaned_files = glob.glob("temp_*.mp3") + glob.glob("temp_*.srt")
    
    for file in orphaned_files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Could not delete {file}: {e}")


async def _generate_audio(text: str, file_path: str, voice: str, speed: str) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=speed)
    sub_maker = edge_tts.SubMaker()
    audio_data = b""

    # Open the stream and catch the chunks as they arrive
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            # Use .get() to safely extract the bytes and satisfy the linter
            audio_chunk = chunk.get("data")
            if isinstance(audio_chunk, bytes):
                audio_data += audio_chunk
                
        elif chunk["type"] == "WordBoundary":
            # The new edge-tts API takes the entire chunk directly!
            sub_maker.feed(chunk)

    # 1. Save the final MP3 file
    with open(file_path, "wb") as file:
        file.write(audio_data)
        
    # 2. Save the subtitle file right next to it (edge-tts uses SRT natively now)
    srt_path = file_path.replace(".mp3", ".srt")
    with open(srt_path, "w", encoding="utf-8") as file:
        file.write(sub_maker.get_srt())