import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton)

class AudiobookUI(QMainWindow):
    def __init__(self):
        # super().__init__() initializes the underlying PyQt6 C++ code
        super().__init__()
        
        self.setWindowTitle("AI Audiobook & Notes Environment")
        self.resize(1000, 600)

        # 1. THE FOUNDATION: The Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # We use a Horizontal Box Layout to split the screen left/right
        main_layout = QHBoxLayout(central_widget)

        # 2. THE LEFT PANEL (Reading Area)
        left_panel = QVBoxLayout()
        
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True) # You can't type in the book!
        self.reader_box.setHtml("<h2>Welcome to your book</h2><p>The highlighted text will appear here...</p>")
        
        self.play_button = QPushButton("Play / Pause (Space)")
        
        left_panel.addWidget(self.reader_box)
        left_panel.addWidget(self.play_button)

        # 3. THE RIGHT PANEL (Notes Area)
        right_panel = QVBoxLayout()
        
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        
        right_panel.addWidget(self.notes_box)

        # 4. SNAP IT ALL TOGETHER
        main_layout.addLayout(left_panel)
        main_layout.addLayout(right_panel)

# The UI Application Loop
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())