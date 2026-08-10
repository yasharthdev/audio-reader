import sys
import os
import glob
import re
import pygame
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QFileDialog)

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
            
            # --- 1. PRE-PROCESS & TOKENIZE ONCE PER PARAGRAPH ---
            # Normalize spaced hyphens so they match the TTS engine's tokenization
            clean_para = re.sub(r'\s*-\s*', '-', para)
            all_tokens = re.findall(r"[\w'-]+|[.,!?;]", clean_para)
            
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
                    current_time = pygame.mixer.music.get_pos()
                    
                    if current_word_idx < len(srt_data):
                        target_word = srt_data[current_word_idx]
                        
                        if current_time >= target_word["start"]:
                            html_text = ""
                            word_counter = 0
                            
                            # Build the highlighted text using our pre-calculated tokens
                            for token in all_tokens:
                                is_word = re.match(r"[\w'-]+", token)
                                
                                if is_word and word_counter == current_word_idx:
                                    html_text += f"<span style='background-color: green;'>{token}</span> "
                                    word_counter += 1
                                else:
                                    html_text += f"{token} "
                                    if is_word:
                                        word_counter += 1
                                    
                            self.paragraph_changed.emit(html_text.strip())
                            current_word_idx += 1
                
                if not self.is_paused and not is_playing_audio():
                    break
                    
                if self.is_skipped or not self.is_running:
                    pygame.mixer.music.stop()
                    break
                    
                pygame.time.Clock().tick(30)
                
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

        # Left Panel
        left_panel = QVBoxLayout()
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True)
        self.reader_box.setStyleSheet("font-size: 18px;") 
        
        # New Horizontal Layout for Buttons
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Book (.txt)")
        self.play_button = QPushButton("Play / Pause")
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.play_button)
        
        left_panel.addWidget(self.reader_box)
        left_panel.addLayout(button_layout)

        # Right Panel
        right_panel = QVBoxLayout()
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        right_panel.addWidget(self.notes_box)

        main_layout.addLayout(left_panel)
        main_layout.addLayout(right_panel)

        # Connect the Buttons
        self.load_button.clicked.connect(self.load_book_dialog)
        self.play_button.clicked.connect(self.toggle_pause)
        
        # Set initial boot message
        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt file.</p>")

    def load_book_dialog(self):
        """Opens the macOS Finder to select a text file."""
        # Open the native file picker
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Text File", 
            "", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                # Read the file
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Split the text into paragraphs (splitting by double newline)
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                
                if not paragraphs:
                    self.reader_box.setHtml("<h3>Error:</h3><p>The selected file is empty.</p>")
                    return

                # If an audiobook is already playing, safely kill it
                if hasattr(self, 'engine_thread') and self.engine_thread.isRunning():
                    self.engine_thread.is_running = False
                    self.engine_thread.wait() 

                # Boot up the new audiobook thread!
                self.engine_thread = AudioEngineThread(paragraphs)
                self.engine_thread.paragraph_changed.connect(self.update_reader_box)
                self.engine_thread.start()
                
            except Exception as e:
                self.reader_box.setHtml(f"<h3>Error:</h3><p>Could not load file: {e}</p>")

    def update_reader_box(self, text):
        self.reader_box.setHtml(f"<h3>Current Paragraph:</h3><p>{text}</p>")

    def toggle_pause(self):
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_paused = not self.engine_thread.is_paused

    def closeEvent(self, event):
        """Fires automatically when the user closes the window."""
        # 1. Safely shut down the background engine
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_running = False
            self.engine_thread.quit()
            self.engine_thread.wait()
            
        # 2. Sweep the project folder and delete any zombie temp files
        for file in glob.glob("temp_*.mp3") + glob.glob("temp_*.srt"):
            try:
                os.remove(file)
            except OSError:
                pass
                
        # 3. Allow the window to close
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())