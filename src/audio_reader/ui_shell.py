import sys
import os
import glob
import re
import asyncio
import queue
import threading
import pygame
import json
from audio_reader.epub_parser import get_epub_paragraphs, get_epub_data
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QFileDialog, QComboBox, QSplitter, QTabWidget, QListWidget,
                             QInputDialog, QListWidgetItem, QMessageBox, QMenu, QToolButton,
                             QDialog, QFormLayout, QSpinBox, QDialogButtonBox, QSizePolicy,
                             QTreeWidget, QTreeWidgetItem)

class ContentsDialog(QDialog):
    def __init__(self, chapter_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Table of Contents")
        self.resize(400, 500)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: rgba(100, 100, 100, 30);
                border-radius: 3px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(100, 100, 255, 50);
                border-radius: 3px;
            }
        """)
        self.layout.addWidget(self.tree)
        
        self.populate_tree(self.tree, chapter_map)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.expandAll()
        
        self.selected_index = None

    def populate_tree(self, parent_widget, items):
        for item in items:
            tree_item = QTreeWidgetItem(parent_widget)
            tree_item.setText(0, item['title'])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item['start_index'])
            if item.get('children'):
                self.populate_tree(tree_item, item['children'])
                
    def on_item_clicked(self, item, column):
        self.selected_index = item.data(0, Qt.ItemDataRole.UserRole)
        self.accept()
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSettings
from PyQt6.QtGui import QKeySequence, QShortcut, QFont, QAction, QColor, QTextCursor, QTextCharFormat

if sys.platform == 'win32':
    SYS_FONTS = ["Segoe UI", "Georgia", "Consolas", "Arial"]
    DEFAULT_FONT = "Segoe UI"
elif sys.platform == 'darwin': # macOS
    SYS_FONTS = ["Avenir", "Helvetica Neue", "Georgia", "Menlo"]
    DEFAULT_FONT = "Avenir"
else: # Linux fallback
    SYS_FONTS = ["Ubuntu", "DejaVu Sans", "Liberation Mono"]
    DEFAULT_FONT = "Ubuntu"

pygame.mixer.init()

LIGHT_THEME = """
QMainWindow, QWidget { background-color: #F8F9FA; color: #2B2D42; }
QLabel { color: #2B2D42; background: transparent; }
QToolBar { background-color: #FFFFFF; border-bottom: 1px solid #E5E7EB; }
QTextEdit, QListWidget { background-color: #FFFFFF; color: #2B2D42; padding: 24px 32px; border: none; }
QPushButton, QToolButton { background-color: #1E293B; color: #FFFFFF; border-radius: 8px; padding: 0px 16px; height: 32px; font-size: 13px; font-weight: 500; border: none; }
QPushButton:hover, QToolButton:hover { background-color: #334155; }
QComboBox { background-color: #FFFFFF; color: #1E293B; border: 1px solid #CBD5E1; border-radius: 8px; padding: 0px 16px; height: 32px; font-size: 13px; font-weight: 500; }
QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1E293B; selection-background-color: #E2E8F0; selection-color: #0F172A; padding: 6px 12px; min-width: 150px; }
QMenu { background-color: #FFFFFF; color: #1E293B; border: 1px solid #E2E8F0; selection-background-color: #F1F5F9; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0px; }
QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

DARK_THEME = """
QMainWindow, QWidget { background-color: #1E1E1E; color: #E0E0E0; }
QLabel { color: #E0E0E0; background: transparent; }
QToolBar { background-color: #252526; border-bottom: 1px solid #333333; }
QTextEdit, QListWidget { background-color: #1E1E1E; color: #E0E0E0; padding: 24px 32px; border: none; }
QPushButton, QToolButton { background-color: #333333; color: #FFFFFF; border-radius: 8px; padding: 0px 16px; height: 32px; font-size: 13px; font-weight: 500; border: none; }
QPushButton:hover, QToolButton:hover { background-color: #444444; }
QComboBox { background-color: #2D2D30; color: #F3F4F6; border: 1px solid #3E3E42; border-radius: 8px; padding: 0px 16px; height: 32px; font-size: 13px; font-weight: 500; }
QComboBox QAbstractItemView { background-color: #252526; color: #F3F4F6; selection-background-color: #374151; selection-color: #FFFFFF; padding: 6px 12px; min-width: 150px; }
QMenu { background-color: #252526; color: #F3F4F6; border: 1px solid #3E3E42; selection-background-color: #374151; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0px; }
QScrollBar::handle:vertical { background: #4B5563; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.settings = settings
        
        self.layout = QFormLayout(self)
        
        # Font Family
        self.font_combo = QComboBox()
        self.font_combo.addItems(SYS_FONTS)
        self.font_combo.setCurrentText(settings.value("font_family", DEFAULT_FONT, type=str))
        self.font_combo.setMinimumWidth(150)
        self.layout.addRow("Font Family:", self.font_combo)
        
        # Highlight Theme
        self.highlight_combo = QComboBox()
        self.highlight_combo.addItems(["Red", "Blue", "Green", "Purple", "Gold"])
        self.highlight_combo.setCurrentText(settings.value("highlight_theme", "Red", type=str))
        self.highlight_combo.setMinimumWidth(150)
        self.layout.addRow("Highlight Theme:", self.highlight_combo)
        
        # App Theme
        self.app_theme_combo = QComboBox()
        self.app_theme_combo.addItems(["Light", "Dark"])
        self.app_theme_combo.setCurrentText(settings.value("ui_mode", "Light", type=str))
        self.app_theme_combo.setMinimumWidth(150)
        self.layout.addRow("UI Mode:", self.app_theme_combo)
        
        # Font Size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(settings.value("font_size", 16, type=int))
        self.layout.addRow("Font Size:", self.font_size_spin)
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

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

        Path(file_path).write_bytes(audio_data)
            
        srt_path = file_path.replace(".mp3", ".srt")
        Path(srt_path).write_text(sub_maker.get_srt(), encoding="utf-8")

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
        content = Path(filepath).read_text(encoding='utf-8')
        lines = [line.strip() for line in content.splitlines() if line.strip()]
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

    word_highlighted = pyqtSignal(int, int, int)

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
                                
                                self.word_highlighted.emit(current_index, start_idx, end_idx)
                                
                            current_word_idx += 1
                
                if not self.is_paused and not is_playing_audio():
                    break
                    
                if not self.is_running:
                    pygame.mixer.music.stop()
                    break
                    
                pygame.time.Clock().tick(30)
                
            cleanup_audio(mp3_path)
            self.audio_queue.task_done()


class BookLoaderThread(QThread):
    finished_loading = pyqtSignal(list, list)
    error_loading = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if self.file_path.lower().endswith('.epub'):
                paragraphs, chapter_map = get_epub_data(self.file_path)
                self.finished_loading.emit(paragraphs, chapter_map)
            else:
                content = Path(self.file_path).read_text(encoding='utf-8')
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                self.finished_loading.emit(paragraphs, [])
        except Exception as e:
            self.error_loading.emit(str(e))

# ==========================================
# 3. THE UI CANVAS
# ==========================================
class AudiobookUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Audiobook & Notes Environment")
        self.resize(1000, 600)

        self.book_paragraphs = []
        self.chapter_map = []
        self.current_paragraph_index = 0
        self.current_file_path = None
        
        self.settings = QSettings("YasharthDev", "AudioReader")

        # --- NEW: QSplitter for draggable/collapsible panels ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        # --- Left Panel (Reader & Controls) ---
        self.left_widget = QWidget()
        left_panel = QVBoxLayout(self.left_widget)
        
        self.reader_box = QTextEdit()
        self.reader_box.setReadOnly(True)
        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt or .epub file.</p>")
        
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Book")
        
        self.voice_combo = QComboBox()
        raw_voices = [
            "en-US-BrianNeural", "en-US-AriaNeural", "en-US-SteffanNeural", "en-US-EmmaNeural",
            "en-US-AndrewNeural", "en-GB-SoniaNeural", "en-GB-ThomasNeural",
            "en-AU-NatashaNeural", "en-AU-WilliamNeural"
        ]
        for voice in raw_voices:
            display_name = voice.split('-')[-1].replace('Neural', '')
            self.voice_combo.addItem(display_name, voice)
        
        self.speed_combo = QComboBox()
        # Clean UI multipliers
        self.speed_combo.addItems([
            "1x", "1.25x", "1.5x", "1.75x", "2x", "2.25x", "2.5x", "3x"
        ])
        saved_speed = self.settings.value("playback_speed", "1x", type=str)
        self.speed_combo.setCurrentText(saved_speed)
        
        self.history_btn = QToolButton()
        self.history_btn.setText("History")
        self.history_menu = QMenu(self)
        self.history_btn.setMenu(self.history_menu)
        self.history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        
        self.prev_button = QPushButton("<< Prev")
        self.play_button = QPushButton("Play / Pause")
        self.next_button = QPushButton("Next >>")
        
        # NEW: Button to collapse the right panel
        self.toggle_panel_btn = QPushButton("Toggle Sidebar") 
        self.contents_btn = QPushButton("Contents")
        self.contents_btn.clicked.connect(self.show_contents_dialog)
        self.contents_btn.setEnabled(False)
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.history_btn)
        button_layout.addWidget(self.voice_combo) 
        button_layout.addWidget(self.speed_combo)
        button_layout.addWidget(self.settings_btn)
        
        button_layout.addStretch()
        
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.next_button)
        
        button_layout.addStretch()
        
        button_layout.addWidget(self.toggle_panel_btn)
        button_layout.addWidget(self.contents_btn)
        
        # --- Enforce Size Policies ---
        toolbar_widgets = [self.load_button, self.history_btn, self.voice_combo, 
                           self.speed_combo, self.settings_btn, self.prev_button, 
                           self.play_button, self.next_button, self.toggle_panel_btn, 
                           self.contents_btn]
        for w in toolbar_widgets:
            w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        
        left_panel.addWidget(self.reader_box)
        left_panel.addLayout(button_layout)

        # --- Right Panel (Tabs: Notes & Bookmarks) ---
        self.right_widget = QWidget()
        self.right_widget.setMinimumWidth(340)
        right_panel = QVBoxLayout(self.right_widget)
        
        self.right_tabs = QTabWidget()
        
        # --- Tab 1: Notes ---
        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout(self.notes_tab)
        
        self.notes_box = QTextEdit()
        self.notes_box.setPlaceholderText("Start typing your timestamped notes here...")
        notes_layout.addWidget(self.notes_box)
        
        notes_btn_layout = QHBoxLayout()
        notes_btn_layout.setSpacing(12)
        self.clear_notes_btn = QPushButton("Clear All Notes")
        self.export_notes_btn = QPushButton("Export (.md)")
        
        self.clear_notes_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.export_notes_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.clear_notes_btn.setMinimumWidth(140)
        self.export_notes_btn.setMinimumWidth(140)
        
        notes_btn_layout.addStretch()
        notes_btn_layout.addWidget(self.clear_notes_btn)
        notes_btn_layout.addWidget(self.export_notes_btn)
        notes_btn_layout.addStretch()
        
        notes_layout.addLayout(notes_btn_layout)
        
        self.right_tabs.addTab(self.notes_tab, "Notes")
        
        # --- Tab 2: Bookmarks ---
        self.bookmarks_tab = QWidget()
        bookmarks_layout = QVBoxLayout(self.bookmarks_tab)
        
        self.bookmarks_list = QListWidget()
        bookmarks_layout.addWidget(self.bookmarks_list)
        
        self.add_bookmark_btn = QPushButton("Bookmark Current Paragraph")
        self.delete_bookmark_btn = QPushButton("Delete Selected Bookmark") 
        
        bookmarks_layout.addWidget(self.add_bookmark_btn)
        bookmarks_layout.addWidget(self.delete_bookmark_btn)
        
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
        self.speed_combo.currentIndexChanged.connect(self.on_speed_changed)

        # --- Bookmark Connections ---
        self.add_bookmark_btn.clicked.connect(self.create_explicit_bookmark)
        self.bookmarks_list.itemDoubleClicked.connect(self.jump_to_bookmark)

        # --- Highlight Shortcut (Updated to Ctrl+Shift+H to avoid macOS conflicts) ---
        self.highlight_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), self)
        self.highlight_shortcut.activated.connect(self.capture_highlight)

        # --- Note & Export Connections ---
        self.clear_notes_btn.clicked.connect(self.notes_box.clear)
        self.export_notes_btn.clicked.connect(self.export_to_obsidian)
        self.delete_bookmark_btn.clicked.connect(self.delete_bookmark)

        self.reader_box.setHtml("<h3>Welcome</h3><p>Click 'Load Book' to select a .txt file.</p>")
        
        saved_font_size = self.settings.value("font_size", 16, type=int)
        saved_font_family = self.settings.value("font_family", "Avenir", type=str)
        base_font = QFont(saved_font_family)
        base_font.setPointSize(saved_font_size)
        self.reader_box.setFont(base_font)
        
        notes_size = max(int(saved_font_size * 0.75), 9)
        notes_font = QFont(base_font.family(), notes_size)
        self.notes_box.setFont(notes_font)
        self.bookmarks_list.setFont(notes_font)
        
        self.refresh_history_menu()
        
        # Apply initial UI mode
        saved_mode = self.settings.value("ui_mode", "Light", type=str)
        self.apply_ui_mode(saved_mode)
        self.apply_font_settings()

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue("font_family", dialog.font_combo.currentText())
            self.settings.setValue("highlight_theme", dialog.highlight_combo.currentText())
            self.settings.setValue("ui_mode", dialog.app_theme_combo.currentText())
            self.settings.setValue("font_size", dialog.font_size_spin.value())
            
            self.apply_ui_mode(dialog.app_theme_combo.currentText())
            self.apply_font_settings()

    def apply_font_settings(self):
        font_name = self.settings.value("font_family", DEFAULT_FONT, type=str)
        target_size = self.settings.value("font_size", 16, type=int)
        
        current_size = self.reader_box.font().pointSize()
        # Set family while maintaining zoom for a moment
        self.reader_box.setFont(QFont(font_name, current_size))
        
        # Adjust via zoomIn/zoomOut to preserve QTextDocument scaling optimization
        diff = target_size - current_size
        if diff > 0:
            self.reader_box.zoomIn(diff)
        elif diff < 0:
            self.reader_box.zoomOut(-diff)
            
        notes_size = max(int(target_size * 0.75), 9)
        new_notes_font = QFont(font_name, notes_size)
        self.notes_box.setFont(new_notes_font)
        self.bookmarks_list.setFont(new_notes_font)

    def apply_ui_mode(self, mode_name):
        app = QApplication.instance()
        if mode_name == "Light":
            app.setStyleSheet(LIGHT_THEME)
        else:
            app.setStyleSheet(DARK_THEME)
            
        # Re-apply text highlights so they pop under the new background
        self._apply_highlights()

    def get_theme_colors(self):
        theme = self.settings.value("highlight_theme", "Red", type=str)
        if theme == "Blue": return QColor(0, 122, 255), QColor(0, 122, 255, 31), QColor("white")
        elif theme == "Green": return QColor(40, 200, 64), QColor(40, 200, 64, 31), QColor("white")
        elif theme == "Purple": return QColor(175, 82, 222), QColor(175, 82, 222, 31), QColor("white")
        elif theme == "Gold": return QColor(255, 204, 0), QColor(255, 204, 0, 31), QColor("black")
        return QColor(255, 0, 0), QColor(255, 0, 0, 31), QColor("white")

    def refresh_history_menu(self):
        self.history_menu.clear()
        recent_books = self.settings.value("recent_books", [], type=list)
        if recent_books:
            for book_path in recent_books:
                if os.path.exists(book_path):
                    filename = os.path.basename(book_path)
                    action = QAction(filename, self)
                    action.triggered.connect(lambda checked, path=book_path: self.load_book_from_path(path))
                    self.history_menu.addAction(action)
            self.history_menu.addSeparator()
            clear_action = QAction("Clear History", self)
            clear_action.triggered.connect(self.clear_history)
            self.history_menu.addAction(clear_action)
        else:
            empty_action = QAction("No Recent Books", self)
            empty_action.setEnabled(False)
            self.history_menu.addAction(empty_action)

    def clear_history(self):
        self.settings.setValue("recent_books", [])
        self.refresh_history_menu()

    def on_speed_changed(self):
        speed_val = self.speed_combo.currentText()
        self.settings.setValue("playback_speed", speed_val)
        self.play_from_index(self.current_paragraph_index)

    def increase_font(self):
        self.reader_box.zoomIn(1)
        current_size = self.reader_box.font().pointSize()
        self.settings.setValue("font_size", current_size)
        
        notes_size = max(int(current_size * 0.75), 9)
        self.notes_box.setFont(QFont(self.reader_box.font().family(), notes_size))
        self.bookmarks_list.setFont(QFont(self.reader_box.font().family(), notes_size))

    def decrease_font(self):
        self.reader_box.zoomOut(1)
        current_size = self.reader_box.font().pointSize()
        self.settings.setValue("font_size", current_size)
        
        notes_size = max(int(current_size * 0.75), 9)
        self.notes_box.setFont(QFont(self.reader_box.font().family(), notes_size))
        self.bookmarks_list.setFont(QFont(self.reader_box.font().family(), notes_size))

    def toggle_sidebar(self):
        """Shows or hides the right-hand panel."""
        is_visible = self.right_widget.isVisible()
        self.right_widget.setVisible(not is_visible)

    def get_bookmark(self, file_path):
        """Reads the JSON database and returns the auto-resume paragraph index."""
        bookmarks_file = Path("bookmarks.json")
        if not bookmarks_file.exists():
            return 0
            
        try:
            data = json.loads(bookmarks_file.read_text(encoding='utf-8'))
            
            book_data = data.get(file_path, 0)
            
            # Backwards compatibility for v1 schema
            if isinstance(book_data, int):
                return book_data
                
            # v2 schema: grab the auto-resume index
            return book_data.get("last_played", 0)
        except Exception:
            return 0

    def delete_bookmark(self):
        """Removes the selected bookmark from both the UI and the JSON database."""
        selected_items = self.bookmarks_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        target_index = item.data(Qt.ItemDataRole.UserRole)
        
        # 1. Remove from JSON file
        if self.current_file_path:
            bookmarks_file = Path("bookmarks.json")
            if bookmarks_file.exists():
                data = json.loads(bookmarks_file.read_text(encoding='utf-8'))
                
                if self.current_file_path in data:
                    # Filter out the bookmark with the matching index
                    bookmarks = data[self.current_file_path].get("bookmarks", [])
                    data[self.current_file_path]["bookmarks"] = [
                        bm for bm in bookmarks if bm["index"] != target_index
                    ]
                    
                    # Write the cleaned array back to the drive
                    bookmarks_file.write_text(json.dumps(data, indent=4), encoding='utf-8')
                        
        # 2. Remove from UI list
        self.bookmarks_list.takeItem(self.bookmarks_list.row(item))

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

    def export_to_obsidian(self):
        """Grabs all text from the notes box and saves it as a .md file. Returns True if saved."""
        notes_content = self.notes_box.toPlainText()
        if not notes_content.strip():
            return True # If it's empty, we consider it "safe" to proceed
            
        default_name = "audiobook_notes.md"
        if self.current_file_path:
            base_name = os.path.basename(self.current_file_path).split('.')[0]
            default_name = f"{base_name}_notes.md"
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export to Obsidian", 
            default_name, 
            "Markdown Files (*.md)"
        )
        
        if save_path:
            Path(save_path).write_text(notes_content, encoding='utf-8')
            return True
            
        return False # The user canceled the save dialog

    def save_bookmark(self):
        """Saves the auto-resume paragraph index to the JSON database."""
        if not self.current_file_path:
            return
            
        bookmarks_file = Path("bookmarks.json")
        data = {}
        
        if bookmarks_file.exists():
            try:
                data = json.loads(bookmarks_file.read_text(encoding='utf-8'))
            except Exception:
                pass
                
        # Upgrade schema if this book was saved using the old format, or is new
        if self.current_file_path not in data or isinstance(data.get(self.current_file_path), int):
            data[self.current_file_path] = {"last_played": 0, "bookmarks": []}
            
        # Only update the last_played tracker; leave explicit bookmarks untouched
        data[self.current_file_path]["last_played"] = self.current_paragraph_index
        
        bookmarks_file.write_text(json.dumps(data, indent=4), encoding='utf-8')

    def create_explicit_bookmark(self):
        """Prompts the user for a name and saves the current index as a hard bookmark."""
        if not self.current_file_path:
            return
            
        name, ok = QInputDialog.getText(self, "New Bookmark", "Enter a name for this bookmark:")
        
        if ok and name:
            bookmarks_file = Path("bookmarks.json")
            data = {}
            if bookmarks_file.exists():
                data = json.loads(bookmarks_file.read_text(encoding='utf-8'))
                    
            if self.current_file_path not in data or isinstance(data.get(self.current_file_path), int):
                data[self.current_file_path] = {"last_played": self.current_paragraph_index, "bookmarks": []}
                
            # Append the new bookmark to the array
            new_bookmark = {"name": name, "index": self.current_paragraph_index}
            data[self.current_file_path]["bookmarks"].append(new_bookmark)
            
            bookmarks_file.write_text(json.dumps(data, indent=4), encoding='utf-8')
                
            self.refresh_bookmarks_ui()

    def refresh_bookmarks_ui(self):
        """Clears and reloads the bookmark list widget from the JSON database."""
        self.bookmarks_list.clear()
        if not self.current_file_path:
            return
            
        bookmarks_file = Path("bookmarks.json")
        if bookmarks_file.exists():
            data = json.loads(bookmarks_file.read_text(encoding='utf-8'))
                
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
            self.load_book_from_path(file_path)

    def load_book_from_path(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return
            
        recent_books = self.settings.value("recent_books", [], type=list)
        if file_path in recent_books:
            recent_books.remove(file_path)
        recent_books.insert(0, file_path)
        recent_books = recent_books[:10]
        self.settings.setValue("recent_books", recent_books)
        self.refresh_history_menu()
        
        self.current_file_path = file_path # Save the path to the class state
        
        # Disable button and show loading text
        self.load_button.setEnabled(False)
        self.reader_box.setHtml("<h3>Loading...</h3><p>Please wait while the book is being parsed.</p>")
        
        # Start background thread
        self.loader_thread = BookLoaderThread(file_path)
        self.loader_thread.finished_loading.connect(self.on_book_loaded)
        self.loader_thread.error_loading.connect(self.on_book_load_error)
        self.loader_thread.start()

    def show_contents_dialog(self):
        if not self.chapter_map: return
        dialog = ContentsDialog(self.chapter_map, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_index is not None:
            self.play_from_index(dialog.selected_index)

    def on_book_loaded(self, paragraphs, chapter_map):
        self.load_button.setEnabled(True)
        self.book_paragraphs = paragraphs
        self.chapter_map = chapter_map
        
        if not self.book_paragraphs:
            self.reader_box.setHtml("<h3>Error:</h3><p>The selected file is empty or could not be parsed.</p>")
            return
            
        # Enable the Contents button if we have chapters
        if self.chapter_map:
            self.contents_btn.setEnabled(True)
        else:
            self.contents_btn.setEnabled(False)

        # --- NEW BOOKMARK LOGIC ---
        saved_index = self.get_bookmark(self.current_file_path)
        
        # Safety check: if the file changed and is now shorter, reset to 0
        if saved_index >= len(self.book_paragraphs):
            saved_index = 0

        # Boot up the engine at the saved index!
        self.play_from_index(saved_index)

        # Populate the Bookmarks tab
        self.refresh_bookmarks_ui()

    def on_book_load_error(self, error_msg):
        self.load_button.setEnabled(True)
        self.reader_box.setHtml(f"<h3>Error:</h3><p>Could not load file: {error_msg}</p>")

    def play_from_index(self, index):
        """Kills current thread, cleans up, and boots a new one at the target index."""
        if index < 0 or index >= len(self.book_paragraphs):
            return

        if hasattr(self, 'engine_thread') and self.engine_thread.isRunning():
            # 1. Flag the loop to stop
            self.engine_thread.is_running = False
            
            # 2. Tell the thread event loop to exit
            self.engine_thread.quit() 
            
            # 3. FORCE STOP YOUR AUDIO LIBRARY HERE
            # If you are using pygame, uncomment the line below:
            # pygame.mixer.music.stop() 
            # (If you are using a different library like VLC or playsound, use its stop command here)

            # 4. Wait for a maximum of 500 milliseconds (prevents UI throttling)
            if not self.engine_thread.wait(500):
                # 5. If it's stubbornly stuck on a massive EPUB paragraph, force kill it
                self.engine_thread.terminate()
                self.engine_thread.wait()

        # Sweep folder so skips don't leave zombie audio files
        for file in glob.glob("temp_*.mp3") + glob.glob("temp_*.srt"):
            try:
                os.remove(file)
            except OSError:
                pass

        # Grab both Speed and Voice from UI
        ui_speed = self.speed_combo.currentText()
        selected_voice = self.voice_combo.currentData() 
        
        # --- NEW: Translate UI multiplier to Edge-TTS percentage ---
        speed_map = {
            "1x": "+0%",
            "1.25x": "+25%",
            "1.5x": "+50%",
            "1.75x": "+75%",
            "2x": "+100%",
            "2.25x": "+125%",
            "2.5x": "+150%",
            "3x": "+200%"
        }
        edge_speed = speed_map.get(ui_speed, "+0%") # Fallback to +0% just in case
        
        # Boot the new thread
        self.engine_thread = AudioEngineThread(
            self.book_paragraphs, 
            start_index=index,
            voice=selected_voice,
            speed=edge_speed # Pass the translated percentage to the backend
        )
        self.engine_thread.paragraph_changed.connect(self.update_reader_box)
        self.engine_thread.word_highlighted.connect(self.update_word_highlight)
        self.engine_thread.start()

    def skip_next(self):
        self.play_from_index(self.current_paragraph_index + 1)

    def skip_prev(self):
        self.play_from_index(self.current_paragraph_index - 1)

    def update_word_highlight(self, index, start_char, end_char):
        if index != self.current_paragraph_index:
            return
            
        doc = self.reader_box.document()
        block = doc.lastBlock()
        block_pos = block.position()
        
        solid, alpha, text_color = self.get_theme_colors()
        
        word_sel = QTextEdit.ExtraSelection()
        word_sel.format.setBackground(solid)
        word_sel.format.setForeground(text_color)
        word_cursor = QTextCursor(doc)
        word_cursor.setPosition(block_pos + start_char)
        word_cursor.setPosition(block_pos + end_char, QTextCursor.MoveMode.KeepAnchor)
        word_sel.cursor = word_cursor
        
        para_sel = QTextEdit.ExtraSelection()
        para_sel.format.setBackground(alpha)
        para_cursor = QTextCursor(doc)
        text = block.text()
        leading = len(text) - len(text.lstrip())
        trailing = len(text) - len(text.rstrip())
        
        para_cursor.setPosition(block_pos + leading)
        para_cursor.setPosition(block_pos + len(text) - trailing, QTextCursor.MoveMode.KeepAnchor)
        para_sel.cursor = para_cursor
        
        self.para_selection = para_sel
        self.word_selection = word_sel
        self._apply_highlights()

    def _apply_highlights(self):
        selections = []
        if hasattr(self, 'para_selection') and self.para_selection:
            selections.append(self.para_selection)
        if hasattr(self, 'word_selection') and self.word_selection:
            selections.append(self.word_selection)
        self.reader_box.setExtraSelections(selections)

    def get_active_chapter(self, index):
        if not self.chapter_map:
            return f"Paragraph {index + 1} of {len(self.book_paragraphs)}"
        
        current_chapter = self.chapter_map[0]['title'] if self.chapter_map else f"Paragraph {index + 1}"
        for chapter in self.chapter_map:
            if chapter['start_index'] <= index:
                current_chapter = chapter['title']
            else:
                break
        return current_chapter

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
        header_text = self.get_active_chapter(index)
        self.reader_box.setHtml(f"<h3>{header_text}</h3><p>{text}</p>")
        
        # 3. Instantly snap the scrollbar back to where you left it
        if scrollbar is not None:
            scrollbar.setValue(current_scroll)

    def toggle_pause(self):
        if hasattr(self, 'engine_thread'):
            self.engine_thread.is_paused = not self.engine_thread.is_paused

    def closeEvent(self, event):
        """Intercepts shutdown to check for unsaved notes, then cleans up background threads."""
        # --- 1. Check for unsaved notes first ---
        notes_content = self.notes_box.toPlainText().strip()
        proceed_to_close = True
        
        if notes_content:
            reply = QMessageBox.question(
                self, 
                'Unsaved Notes Detected',
                'You have text in your Notes panel. Do you want to export it before exiting?',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if reply == QMessageBox.StandardButton.Save:
                # If they cancel the file browser, stop the shutdown
                if not self.export_to_obsidian():
                    proceed_to_close = False 
            elif reply == QMessageBox.StandardButton.Cancel:
                # If they cancel the warning box, stop the shutdown
                proceed_to_close = False

        # --- 2. Execute background cleanup ONLY if we are proceeding ---
        if proceed_to_close:
            # Kill the audio engine
            if hasattr(self, 'engine_thread'):
                self.engine_thread.is_running = False
                self.engine_thread.quit()
                self.engine_thread.wait()
                
            # Sweep the temporary audio files
            for file in glob.glob("temp_*.mp3") + glob.glob("temp_*.srt"):
                try:
                    os.remove(file)
                except OSError:
                    pass
                    
            event.accept()
        else:
            # Abort the shutdown, go back to the app
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookUI()
    window.show()
    sys.exit(app.exec())