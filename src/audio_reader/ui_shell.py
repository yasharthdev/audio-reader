import sys
import time
import pygame
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton)
from audio_reader.player import download_audio, play_audio, is_playing_audio, cleanup_audio

# ==========================================
# 1. THE BACKGROUND WORKER (The Engine)
# ==========================================
class AudioEngineThread(QThread):
    paragraph_changed = pyqtSignal(str)

    def __init__(self, paragraphs, voice="en-US-BrianNeural", speed="+0%"):
        super().__init__()
        self.paragraphs = paragraphs
        self.voice = voice
        self.speed = speed
        
        # UI-controlled state variables (Replacing the old pynput dictionary)
        self.is_running = True
        self.is_paused = False
        self.is_skipped = False

    def run(self):
        """This runs on a separate CPU thread."""
        for i, para in enumerate(self.paragraphs):
            if not self.is_running:
                break
            
            # Reset switches for the new paragraph
            self.is_skipped = False
            self.is_paused = False
            
            # 1. Transmit the current paragraph to the UI
            self.paragraph_changed.emit(para)
            
            # 2. Download the audio & SRT files
            filepath = f"temp_{i}.mp3"
            download_audio(para, filepath, self.voice, self.speed)
            
            # 3. Play the audio
            play_audio(filepath)
            was_paused = False
            
            # 4. The Master Playback Loop
            while True:
                if self.is_paused and not was_paused:
                    pygame.mixer.music.pause()
                    was_paused = True
                    
                elif not self.is_paused and was_paused:
                    pygame.mixer.music.unpause()
                    was_paused = False
                    pygame.time.wait(50)
                    
                if not self.is_paused and not is_playing_audio():
                    break
                    
                if self.is_skipped or not self.is_running:
                    pygame.mixer.music.stop()
                    break
                    
                pygame.time.Clock().tick(10)            
                
            # Clean up both the MP3 and SRT file
            cleanup_audio(filepath)

# ==========================================
# 2. THE UI THREAD (The Canvas)
# ==========================================
class AudiobookUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Audiobook & Notes Environment")
        self.resize(1000, 600)

        # --- Layout Setup ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel
        left_panel = QVBoxLayout()
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True)
        self.play_button = QPushButton("Play / Pause")
        left_panel.addWidget(self.reader_box)
        left_panel.addWidget(self.play_button)

        # Right Panel
        right_panel = QVBoxLayout()
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        right_panel.addWidget(self.notes_box)

        main_layout.addLayout(left_panel)
        main_layout.addLayout(right_panel)

        # --- Thread Integration ---
        # 1. Grab some real paragraphs to test!
        test_paragraphs = [
            "This is the first real audio test inside our PyQt6 environment.", 
            "The background thread is currently downloading this audio.", 
            "If you can hear this, the QThread and Pygame are successfully integrated!"
        ]
        self.engine_thread = AudioEngineThread(test_paragraphs)
        
        # 2. Connect the Walkie-Talkies
        self.engine_thread.paragraph_changed.connect(self.update_reader_box)
        
        # 3. Connect the Button to the logic function below
        self.play_button.clicked.connect(self.toggle_pause)
        
        # 4. Start the engine!
        self.engine_thread.start()

    def update_reader_box(self, text):
        self.reader_box.setHtml(f"<h3>Current Paragraph:</h3><p>{text}</p>")

    def toggle_pause(self):
        """Reaches into the worker thread and flips the pause switch."""
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_paused = not self.engine_thread.is_paused

# ==========================================
# 3. THE APPLICATION LOOP
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())