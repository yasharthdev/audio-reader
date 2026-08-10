import sys
import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton)

# ==========================================
# 1. THE BACKGROUND WORKER (The Engine)
# ==========================================
class AudioEngineThread(QThread):
    # The walkie-talkie signal that transmits strings to the UI
    paragraph_changed = pyqtSignal(str)

    def __init__(self, paragraphs):
        super().__init__()
        self.paragraphs = paragraphs
        self.is_running = True

    def run(self):
        """This runs on a separate CPU thread."""
        for para in self.paragraphs:
            if not self.is_running:
                break
            
            # Transmit the current paragraph back to the UI
            self.paragraph_changed.emit(para)
            
            # Dummy delay to simulate Pygame playing an audio file
            time.sleep(2) 

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
        self.play_button = QPushButton("Play / Pause (Space)")
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
        # 1. Instantiate the background worker with dummy data
        test_paragraphs = [
            "This is the first paragraph of our prototype.", 
            "The background thread is currently sleeping for 2 seconds.", 
            "If you can read this, the QThread and the UI are successfully talking!"
        ]
        self.engine_thread = AudioEngineThread(test_paragraphs)
        
        # 2. Connect the Signal to the UI function
        self.engine_thread.paragraph_changed.connect(self.update_reader_box)
        
        # 3. Start the engine!
        self.engine_thread.start()

    def update_reader_box(self, text):
        """This slot safely receives data from the background thread."""
        self.reader_box.setHtml(f"<h3>Current Paragraph:</h3><p>{text}</p>")

# ==========================================
# 3. THE APPLICATION LOOP
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())