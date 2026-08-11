import sys
import os
import glob
import re
import asyncio
import queue
import threading
import pygame
import json
from audio_reader.epub_parser import get_epub_paragraphs
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QFileDialog, QComboBox, QSplitter, QTabWidget, QListWidget,
                             QInputDialog, QListWidgetItem)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence, QShortcut

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
    # UPGRADE: Emit an INT (the index) alongside the STR (the html text)
    paragraph_changed = pyqtSignal(int, str) 

    def __init__(self, paragraphs, start_index=0, voice="en-US-BrianNeural", speed="+0%"):
        super().__init__()
        self.paragraphs = paragraphs
        self.start_index = start_index  # <--- Track where we start
        self.voice = voice
        self.speed = speed
        
        self.is_running = True
        self.is_paused = False
        
        self.audio_queue = queue.Queue(maxsize=3)

    def run(self):
        if not self.paragraphs or not self.is_running:
            return

        # --- THE PRODUCER ---
        def downloader_worker():
            for i in range(self.start_index, len(self.paragraphs)):
                if not self.is_running:
                    break
                
                mp3_path = f"temp_{i}.mp3"
                download_audio(self.paragraphs[i], mp3_path, self.voice, self.speed)
                srt_path = mp3_path.replace(".mp3", ".srt")
                
                # FIX: Add a timeout so it checks if the app is closing instead of freezing
                while self.is_running:
                    try:
                        self.audio_queue.put((mp3_path, srt_path, self.paragraphs[i], i), timeout=0.5)
                        break
                    except queue.Full:
                        continue

        producer = threading.Thread(target=downloader_worker, daemon=True)
        producer.start()

        # --- THE CONSUMER ---
        for _ in range(self.start_index, len(self.paragraphs)):
            if not self.is_running:
                break
                
            self.is_paused = False
            
            # FIX: Add a timeout so it checks if the app is closing instead of freezing
            queue_item = None
            while self.is_running:
                try:
                    queue_item = self.audio_queue.get(timeout=0.5)
                    break
                except queue.Empty:
                    continue
            
            if not queue_item:
                break
                
            mp3_path, srt_path, para, current_index = queue_item
            
            word_matches = list(re.finditer(r"[^\W_]+(?:[-'’][^\W_]+)*", para))
            
            self.paragraph_changed.emit(current_index, para.replace('\n', '<br>'))
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
                
                if not self.is_paused and is_playing_audio():
                    current_time = pygame.mixer.music.get_pos()
                    
                    if current_word_idx < len(srt_data):
                        target_word = srt_data[current_word_idx]
                        
                        if current_time >= target_word["start"]:
                            if current_word_idx < len(word_matches):
                                match = word_matches[current_word_idx]
                                start_idx = match.start()
                                end_idx = match.end()
                                
                                html_text = (
                                    para[:start_idx] + 
                                    "<span style='background-color: green;'>" + 
                                    para[start_idx:end_idx] + 
                                    "</span>" + 
                                    para[end_idx:]
                                )
                                
                                self.paragraph_changed.emit(current_index, html_text.replace('\n', '<br>'))
                                
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

        self.book_paragraphs = []
        self.current_paragraph_index = 0
        self.current_file_path = None

        # --- NEW: QSplitter for draggable/collapsible panels ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        # --- Left Panel (Reader & Controls) ---
        self.left_widget = QWidget()
        left_panel = QVBoxLayout(self.left_widget)
        
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True)
        self.reader_box.setStyleSheet("font-size: 18px;") 
        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt or .epub file.</p>")
        
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Book")
        
        self.voice_combo = QComboBox()
        self.voice_combo.addItems([
            "en-US-BrianNeural", "en-US-AriaNeural", "en-US-SteffanNeural", "en-US-EmmaNeural",
            "en-US-AndrewMultilingualNeural", "en-GB-SoniaNeural", "en-GB-ThomasNeural",
            "en-AU-NatashaNeural", "en-AU-WilliamNeural"
        ])
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["+0%", "+50%", "+100%", "+150%", "+200%", "+250%", "+300%"])
        
        self.prev_button = QPushButton("<< Prev")
        self.play_button = QPushButton("Play / Pause")
        self.next_button = QPushButton("Next >>")
        
        # NEW: Button to collapse the right panel
        self.toggle_panel_btn = QPushButton("Toggle Sidebar") 
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.voice_combo) 
        button_layout.addWidget(self.speed_combo)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.toggle_panel_btn)
        
        left_panel.addWidget(self.reader_box)
        left_panel.addLayout(button_layout)

        # --- Right Panel (Tabs: Notes & Bookmarks) ---
        self.right_widget = QWidget()
        right_panel = QVBoxLayout(self.right_widget)
        
        self.right_tabs = QTabWidget()
        
        # Tab 1: Notes
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        self.right_tabs.addTab(self.notes_box, "Notes")
        
        # Tab 2: Bookmarks
        self.bookmarks_tab = QWidget()
        bookmarks_layout = QVBoxLayout(self.bookmarks_tab)
        self.bookmarks_list = QListWidget()
        self.add_bookmark_btn = QPushButton("Bookmark Current Paragraph")
        bookmarks_layout.addWidget(self.bookmarks_list)
        bookmarks_layout.addWidget(self.add_bookmark_btn)
        self.right_tabs.addTab(self.bookmarks_tab, "Bookmarks")
        
        right_panel.addWidget(self.right_tabs)

        # Add both widgets to the splitter
        self.main_splitter.addWidget(self.left_widget)
        self.main_splitter.addWidget(self.right_widget)
        
        # Set default split size (e.g., 60% Left, 40% Right)
        self.main_splitter.setSizes([600, 400])

        # --- Signal Connections ---
        self.load_button.clicked.connect(self.load_book_dialog)
        self.play_button.clicked.connect(self.toggle_pause)
        self.next_button.clicked.connect(self.skip_next)
        self.prev_button.clicked.connect(self.skip_prev)
        self.toggle_panel_btn.clicked.connect(self.toggle_sidebar) # New connection
        
        self.voice_combo.currentIndexChanged.connect(lambda: self.play_from_index(self.current_paragraph_index))
        self.speed_combo.currentIndexChanged.connect(lambda: self.play_from_index(self.current_paragraph_index))
        
        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt file.</p>")

        # --- Bookmark Connections ---
        self.add_bookmark_btn.clicked.connect(self.create_explicit_bookmark)
        self.bookmarks_list.itemDoubleClicked.connect(self.jump_to_bookmark)

        # --- Highlight Shortcut (Updated to Ctrl+Shift+H to avoid macOS conflicts) ---
        self.highlight_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), self)
        self.highlight_shortcut.activated.connect(self.capture_highlight)

    def toggle_sidebar(self):
        """Shows or hides the right-hand panel."""
        is_visible = self.right_widget.isVisible()
        self.right_widget.setVisible(not is_visible)

    def get_bookmark(self, file_path):
        """Reads the JSON database and returns the auto-resume paragraph index."""
        bookmarks_file = "bookmarks.json"
        if not os.path.exists(bookmarks_file):
            return 0
            
        try:
            with open(bookmarks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            book_data = data.get(file_path, 0)
            
            # Backwards compatibility for v1 schema
            if isinstance(book_data, int):
                return book_data
                
            # v2 schema: grab the auto-resume index
            return book_data.get("last_played", 0)
        except Exception:
            return 0

    def capture_highlight(self):
        """Grabs highlighted text, formats as Markdown, and appends to notes."""
        # 1. Grab the cursor specifically from the reader_box
        cursor = self.reader_box.textCursor()
        
        # 2. If nothing is selected, do nothing
        if not cursor.hasSelection():
            return
            
        # 3. Get the selected text
        selected_text = cursor.selectedText()
        
        # 4. Clean up hidden paragraph markers that occasionally sneak in from QTextEdit
        selected_text = selected_text.replace('\u2029', ' ')
        
        # 5. Format as Markdown quote
        timestamp_context = f"\n**[Paragraph {self.current_paragraph_index + 1}]**"
        markdown_quote = f"> {selected_text}\n\n"
        
        # 6. Switch UI to Notes tab
        self.right_tabs.setCurrentWidget(self.notes_box)
        
        # 7. Append and focus
        self.notes_box.append(timestamp_context)
        self.notes_box.append(markdown_quote)
        self.notes_box.setFocus()

    def save_bookmark(self):
        """Saves the auto-resume paragraph index to the JSON database."""
        if not self.current_file_path:
            return
            
        bookmarks_file = "bookmarks.json"
        data = {}
        
        if os.path.exists(bookmarks_file):
            try:
                with open(bookmarks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
                
        # Upgrade schema if this book was saved using the old format, or is new
        if self.current_file_path not in data or isinstance(data.get(self.current_file_path), int):
            data[self.current_file_path] = {"last_played": 0, "bookmarks": []}
            
        # Only update the last_played tracker; leave explicit bookmarks untouched
        data[self.current_file_path]["last_played"] = self.current_paragraph_index
        
        with open(bookmarks_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def create_explicit_bookmark(self):
        """Prompts the user for a name and saves the current index as a hard bookmark."""
        if not self.current_file_path:
            return
            
        name, ok = QInputDialog.getText(self, "New Bookmark", "Enter a name for this bookmark:")
        
        if ok and name:
            bookmarks_file = "bookmarks.json"
            data = {}
            if os.path.exists(bookmarks_file):
                with open(bookmarks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
            if self.current_file_path not in data or isinstance(data.get(self.current_file_path), int):
                data[self.current_file_path] = {"last_played": self.current_paragraph_index, "bookmarks": []}
                
            # Append the new bookmark to the array
            new_bookmark = {"name": name, "index": self.current_paragraph_index}
            data[self.current_file_path]["bookmarks"].append(new_bookmark)
            
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            self.refresh_bookmarks_ui()

    def refresh_bookmarks_ui(self):
        """Clears and reloads the bookmark list widget from the JSON database."""
        self.bookmarks_list.clear()
        if not self.current_file_path:
            return
            
        bookmarks_file = "bookmarks.json"
        if os.path.exists(bookmarks_file):
            with open(bookmarks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            book_data = data.get(self.current_file_path, {})
            if isinstance(book_data, dict):
                for bm in book_data.get("bookmarks", []):
                    # Display the name, but hide the raw index inside the item's UserData
                    item = QListWidgetItem(f"{bm['name']} (Para {bm['index'] + 1})")
                    item.setData(Qt.ItemDataRole.UserRole, bm['index'])
                    self.bookmarks_list.addItem(item)

    def jump_to_bookmark(self, item):
        """Triggers when a user double-clicks a bookmark in the list."""
        index = item.data(Qt.ItemDataRole.UserRole)
        self.play_from_index(index)

    def load_book_dialog(self):
        # Upgrade the filter to accept EPUBs alongside TXT files
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Book", 
            "", 
            "Books (*.txt *.epub);;Text Files (*.txt);;EPUB Files (*.epub);;All Files (*)"
        )
        
        if file_path:
            try:
                # --- EPUB HANDLING ---
                if file_path.lower().endswith('.epub'):
                    # Call the function exactly as you named it in epub_parser.py
                    self.book_paragraphs = get_epub_paragraphs(file_path)
                        
                # --- TXT HANDLING ---
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    self.book_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                
                if not self.book_paragraphs:
                    self.reader_box.setHtml("<h3>Error:</h3><p>The selected file is empty or could not be parsed.</p>")
                    return

                # --- NEW BOOKMARK LOGIC ---
                self.current_file_path = file_path # Save the path to the class state
                saved_index = self.get_bookmark(file_path)
                
                # Safety check: if the file changed and is now shorter, reset to 0
                if saved_index >= len(self.book_paragraphs):
                    saved_index = 0

                # Boot up the engine at the saved index!
                self.play_from_index(saved_index)

                # Populate the Bookmarks tab
                self.refresh_bookmarks_ui()
                
            except Exception as e:
                self.reader_box.setHtml(f"<h3>Error:</h3><p>Could not load file: {e}</p>")

    def play_from_index(self, index):
        """Kills current thread, cleans up, and boots a new one at the target index."""
        if index < 0 or index >= len(self.book_paragraphs):
            return

        if hasattr(self, 'engine_thread') and self.engine_thread.isRunning():
            self.engine_thread.is_running = False
            self.engine_thread.wait() 

        # Sweep folder so skips don't leave zombie audio files
        for file in glob.glob("temp_*.mp3") + glob.glob("temp_*.srt"):
            try:
                os.remove(file)
            except OSError:
                pass

        # --- UPDATE: Grab both Speed and Voice ---
        selected_speed = self.speed_combo.currentText()
        selected_voice = self.voice_combo.currentText() 
        
        self.engine_thread = AudioEngineThread(
            self.book_paragraphs, 
            start_index=index,
            voice=selected_voice, # <--- Pass it to the thread here
            speed=selected_speed
        )
        self.engine_thread.paragraph_changed.connect(self.update_reader_box)
        self.engine_thread.start()

    def skip_next(self):
        self.play_from_index(self.current_paragraph_index + 1)

    def skip_prev(self):
        self.play_from_index(self.current_paragraph_index - 1)

    def update_reader_box(self, index, text):
        self.current_paragraph_index = index 
        
        # --- NEW: Save progress instantly ---
        self.save_bookmark() 
        
        # 1. Grab the scrollbar and save its current position
        scrollbar = self.reader_box.verticalScrollBar()
        
        # Safely get the value to appease strict type checkers
        current_scroll = 0
        if scrollbar is not None:
            current_scroll = scrollbar.value()
        
        # 2. Update the text (which automatically resets the scroll to 0)
        self.reader_box.setHtml(f"<h3>Paragraph {index + 1} of {len(self.book_paragraphs)}:</h3><p>{text}</p>")
        
        # 3. Instantly snap the scrollbar back to where you left it
        if scrollbar is not None:
            scrollbar.setValue(current_scroll)

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