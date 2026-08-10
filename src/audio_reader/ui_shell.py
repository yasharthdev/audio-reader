import sys
import os
import glob
import re
import asyncio
import queue
import threading
import pygame
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QFileDialog, QComboBox)
from PyQt6.QtCore import QThread, pyqtSignal

pygame.mixer.init()

# ==========================================
# 1. CORE ENGINE FUNCTIONS
# ==========================================
def download_audio(text: str, file_path: str, voice: str, speed: str) -> None:
    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=speed, boundary="WordBoundary")
        sub_maker = edge_tts.SubMaker()
        audio_data = b""

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunk = chunk.get("data")
                if isinstance(audio_chunk, bytes):
                    audio_data += audio_chunk
            elif chunk["type"] in ["WordBoundary", "SentenceBoundary"]:
                sub_maker.feed(chunk)

        with open(file_path, "wb") as f:
            f.write(audio_data)
            
        srt_path = file_path.replace(".mp3", ".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(sub_maker.get_srt())

    import edge_tts
    asyncio.run(_generate())

def time_to_ms(time_str: str) -> int:
    parts = time_str.strip().split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    sec_parts = parts[2].split(',')
    seconds = int(sec_parts[0])
    milliseconds = int(sec_parts[1])
    return (hours * 3600000) + (minutes * 60000) + (seconds * 1000) + milliseconds

def parse_srt(filepath: str) -> list[dict]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return []

    words_data = []
    for i, line in enumerate(lines):
        if '-->' in line and i + 1 < len(lines):
            times = line.split('-->')
            start_ms = time_to_ms(times[0])
            end_ms = time_to_ms(times[1])
            text_block = lines[i + 1].strip()
            
            words = text_block.split()
            if len(words) > 1:
                total_duration = end_ms - start_ms
                time_per_word = total_duration / len(words)
                for w_idx, w in enumerate(words):
                    word_start = start_ms + int(w_idx * time_per_word)
                    words_data.append({"word": w, "start": word_start})
            else:
                words_data.append({"word": text_block, "start": start_ms})
                
    return words_data

def play_audio(filepath: str):
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()

def is_playing_audio() -> bool:
    return pygame.mixer.music.get_busy()

def cleanup_audio(filepath: str):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        srt_path = filepath.replace(".mp3", ".srt")
        if os.path.exists(srt_path):
            os.remove(srt_path)
    except OSError:
        pass


# ==========================================
# 2. THE PRODUCER-CONSUMER THREAD
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
        
        self.audio_queue = queue.Queue(maxsize=3)

    def run(self):
        if not self.paragraphs or not self.is_running:
            return

        # --- THE PRODUCER: Dedicated Downloader Worker ---
        def downloader_worker():
            for i, para in enumerate(self.paragraphs):
                if not self.is_running:
                    break
                
                mp3_path = f"temp_{i}.mp3"
                download_audio(para, mp3_path, self.voice, self.speed)
                srt_path = mp3_path.replace(".mp3", ".srt")
                
                self.audio_queue.put((mp3_path, srt_path, para))

        producer = threading.Thread(target=downloader_worker, daemon=True)
        producer.start()

        # --- THE CONSUMER: Audio Player & UI Sync ---
        for _ in range(len(self.paragraphs)):
            if not self.is_running:
                break
                
            self.is_paused = False
            
            mp3_path, srt_path, para = self.audio_queue.get()
            
            # THE PRO FIX: Find start/end character indices of words in the ORIGINAL text.
            # [^\W_]+  -> Matches any sequence of letters/numbers
            # (?:[-'’][^\W_]+)* -> Matches internal hyphens, straight quotes, and smart quotes!
            word_matches = list(re.finditer(r"[^\W_]+(?:[-'’][^\W_]+)*", para))
            
            self.paragraph_changed.emit(para.replace('\n', '<br>'))
            play_audio(mp3_path)
            
            was_paused = False
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
                
                # --- SYNC LOOP ---
                if not self.is_paused and is_playing_audio():
                    current_time = pygame.mixer.music.get_pos()
                    
                    if current_word_idx < len(srt_data):
                        target_word = srt_data[current_word_idx]
                        
                        if current_time >= target_word["start"]:
                            
                            # Ensure we don't go out of bounds if TTS generates extra audio tokens
                            if current_word_idx < len(word_matches):
                                match = word_matches[current_word_idx]
                                start_idx = match.start()
                                end_idx = match.end()
                                
                                # Slice the original string to insert the highlight tags!
                                html_text = (
                                    para[:start_idx] + 
                                    "<span style='background-color: green;'>" + 
                                    para[start_idx:end_idx] + 
                                    "</span>" + 
                                    para[end_idx:]
                                )
                                
                                # Use <br> so PyQt respects actual paragraph breaks if they exist
                                self.paragraph_changed.emit(html_text.replace('\n', '<br>'))
                                
                            current_word_idx += 1
                
                if not self.is_paused and not is_playing_audio():
                    break
                    
                if not self.is_running:
                    pygame.mixer.music.stop()
                    break
                    
                pygame.time.Clock().tick(30)
                
            cleanup_audio(mp3_path)
            self.audio_queue.task_done()


# ==========================================
# 3. THE UI CANVAS
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
        self.reader_box.setStyleSheet("font-size: 18px;") 
        
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Book (.txt)")
        
        # PRO UPDATE: Speed dropdown exactly as requested
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["+0%", "+50%", "+100%", "+150%", "+200%", "+250%", "+300%"])
        self.speed_combo.setCurrentText("+0%") 
        
        self.play_button = QPushButton("Play / Pause")
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.speed_combo)
        button_layout.addWidget(self.play_button)
        
        left_panel.addWidget(self.reader_box)
        left_panel.addLayout(button_layout)

        right_panel = QVBoxLayout()
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        right_panel.addWidget(self.notes_box)

        main_layout.addLayout(left_panel)
        main_layout.addLayout(right_panel)

        self.load_button.clicked.connect(self.load_book_dialog)
        self.play_button.clicked.connect(self.toggle_pause)
        
        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt file.</p>")

    def load_book_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                
                if not paragraphs:
                    self.reader_box.setHtml("<h3>Error:</h3><p>The selected file is empty.</p>")
                    return

                if hasattr(self, 'engine_thread') and self.engine_thread.isRunning():
                    self.engine_thread.is_running = False
                    self.engine_thread.wait() 

                selected_speed = self.speed_combo.currentText()

                self.engine_thread = AudioEngineThread(paragraphs, speed=selected_speed)
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
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_running = False
            self.engine_thread.quit()
            self.engine_thread.wait()
            
        for file in glob.glob("temp_*.mp3") + glob.glob("temp_*.srt"):
            try:
                os.remove(file)
            except OSError:
                pass
                
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())