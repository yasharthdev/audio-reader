# AI Audiobook & Notes Environment (Experimental Branch)

> **Note:** This branch is an experimental prototype built rapidly with AI assistance to test UI/UX flows and integration with text-to-speech models. It serves as a reference architecture. 

A local Python application that transforms `.txt` and `.epub` files into an interactive audiobook experience. It features persistent bookmarking, concurrent text-to-speech audio rendering, and a built-in note-taking environment that exports directly to markdown.

## Features
* **Dynamic Audio Rendering:** Utilizes `edge-tts` to stream neural voices with adjustable speed multipliers.
* **Smart State Management:** Auto-resumes from the last played paragraph and supports custom, named bookmarks via a JSON database.
* **Markdown Capture:** Highlight text in the reader and hit `Cmd+Shift+H` to instantly quote it in your notes.
* **Markdown Integration:** Export your timestamped thoughts directly to a `.md` file before closing the app.

## Prerequisites
* Python 3.10+
* [uv](https://github.com/astral-sh/uv) (Extremely fast Python package installer and resolver)

## Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yasharthdev/](https://github.com/yasharthdev/)audio-reader.git
   cd audio-reader
   ```

2. **Sync dependencies:** 
   *(uv will automatically create the virtual environment)*
   ```bash
   uv sync
   ```

3. **Launch the application:**
   ```bash
   uv run src/audio_reader/ui_shell.py
   ```
