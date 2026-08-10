import sys
import time
import pygame
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton)

# Import your actual functions!
from audio_reader.player import download_audio, play_audio, is_playing_audio, cleanup_audio

# ==========================================
# 1. SRT PARSING HELPERS
# ==========================================
def time_to_ms(time_str: str) -> int:
    """Bulletproof timestamp converter."""
    try:
        time_str = time_str.strip().replace(',', '.')
        parts = time_str.split(':')
        
        if len(parts) == 3:
            h, m, s_ms = parts
        elif len(parts) == 2:
            h = 0
            m, s_ms = parts
        else:
            return 0
            
        if '.' in s_ms:
            s, ms = s_ms.split('.')
        else:
            s = s_ms
            ms = 0
            
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
    except Exception:
        return 0

def parse_srt(filepath: str) -> list[dict]:
    """A parser that automatically polyfills missing word boundaries."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return []

    words_data = []
    for i, line in enumerate(lines):
        if '-->' in line:
            if i + 1 < len(lines):
                # Grab both the start AND end times
                times = line.split('-->')
                start_ms = time_to_ms(times[0])
                end_ms = time_to_ms(times[1])
                
                text_block = lines[i + 1].strip()
                
                # --- THE POLYFILL ---
                # If Edge TTS sent a full sentence, split it!
                words = text_block.split()
                if len(words) > 1:
                    # Mathematically calculate the time per word
                    total_duration = end_ms - start_ms
                    time_per_word = total_duration / len(words)
                    
                    for w_idx, w in enumerate(words):
                        word_start = start_ms + int(w_idx * time_per_word)
                        words_data.append({"word": w, "start": word_start})
                else:
                    # It is already a single word
                    words_data.append({"word": text_block, "start": start_ms})
                
    print(f"[DEBUG] Interpolated {len(words_data)} words from {filepath}")
    return words_data

# ==========================================
# 2. THE BACKGROUND WORKER
# ==========================================
class AudioEngineThread(QThread):
    paragraph_changed = pyqtSignal(str)

    def __init__(self, paragraphs, voice="en-US-BrianNeural", speed="+0%"):
        super().__init__()
        self.paragraphs = paragraphs
        self.voice = voice
        self.speed = speed
        
        self.is_running = True
        self.is_paused = False
        self.is_skipped = False

    def run(self):
        for i, para in enumerate(self.paragraphs):
            if not self.is_running:
                break
            
            self.is_skipped = False
            self.is_paused = False
            
            # Send the initial un-highlighted text to the UI
            self.paragraph_changed.emit(para)
            
            filepath = f"temp_{i}.mp3"
            download_audio(para, filepath, self.voice, self.speed)
            play_audio(filepath)
            was_paused = False
            
            # Load the SRT data we just downloaded!
            srt_path = filepath.replace(".mp3", ".srt")
            srt_data = parse_srt(srt_path)
            current_word_idx = 0
            
            while True:
                if self.is_paused and not was_paused:
                    pygame.mixer.music.pause()
                    was_paused = True
                    
                elif not self.is_paused and was_paused:
                    pygame.mixer.music.unpause()
                    was_paused = False
                    pygame.time.wait(50)
                
                # --- THE SYNC LOOP ---
                if not self.is_paused and is_playing_audio():
                    # Get the current milliseconds from the Pygame clock
                    current_time = pygame.mixer.music.get_pos()
                    
                    # Check if it is time to highlight the next word
                    if current_word_idx < len(srt_data):
                        target_word = srt_data[current_word_idx]
                        
                        if current_time >= target_word["start"]:
                            # We hit the timestamp! Build an HTML string with inline CSS
                            html_text = ""
                            for idx, w_data in enumerate(srt_data):
                                if idx == current_word_idx:
                                    # Highlight current word using a span with a background color
                                    highlight_style = "background-color: red;"
                                    html_text += f"<span style='{highlight_style}'><b>{w_data['word']}</b></span> "
                                else:
                                    html_text += f"{w_data['word']} "
                                    
                            # Send the freshly highlighted HTML to the UI
                            self.paragraph_changed.emit(html_text.strip())
                            current_word_idx += 1
                
                if not self.is_paused and not is_playing_audio():
                    break
                    
                if self.is_skipped or not self.is_running:
                    pygame.mixer.music.stop()
                    break
                    
                pygame.time.Clock().tick(30) # Increased tick rate for smoother UI updates
                
            cleanup_audio(filepath)

# ==========================================
# 3. THE UI THREAD (Canvas stays exactly the same!)
# ==========================================
class AudiobookUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Audiobook & Notes Environment")
        self.resize(1000, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_panel = QVBoxLayout()
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True)
        # Increase the font size so the highlighting is easy to see
        self.reader_box.setStyleSheet("font-size: 18px;") 
        
        self.play_button = QPushButton("Play / Pause")
        left_panel.addWidget(self.reader_box)
        left_panel.addWidget(self.play_button)

        right_panel = QVBoxLayout()
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        right_panel.addWidget(self.notes_box)

        main_layout.addLayout(left_panel)
        main_layout.addLayout(right_panel)

        # Test paragraphs
        test_paragraphs = [
            "This is the first real audio test inside our PyQt6 environment.", 
            "The background thread is currently downloading this audio.", 
            "If you can hear this, the QThread and Pygame are successfully integrated!"
        ]
        self.engine_thread = AudioEngineThread(test_paragraphs)
        self.engine_thread.paragraph_changed.connect(self.update_reader_box)
        self.play_button.clicked.connect(self.toggle_pause)
        self.engine_thread.start()

    def update_reader_box(self, text):
        self.reader_box.setHtml(f"<h3>Current Paragraph:</h3><p>{text}</p>")

    def toggle_pause(self):
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_paused = not self.engine_thread.is_paused

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())