import edge_tts
import subprocess
import asyncio
from pathlib import Path

def speak_paragraph(text: str, voice: str, speed: str) -> None:
    # calling the async helper function
    asyncio.run(_generate_audio(text, "temp.mp3", voice, speed))
    # playing temp.mp3 with afplay (native macOS audio player command)
    subprocess.run(["afplay", "temp.mp3"])
    # deleting the temp.mp3 file to save space
    Path("temp.mp3").unlink()


async def _generate_audio(text: str, file_path: str, voice: str, speed: str) -> None:
    # edge-tts requires a voice string. "en-US-AriaNeural" is a great default.
    communicate = edge_tts.Communicate(text, voice, rate=speed)
    await communicate.save(file_path)