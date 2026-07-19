# OpenPlaylister AI

A free, open-source, AI-driven playlist generator that learns your listening habits and generates custom playlists from your local music files. Think of it as a streaming service recommendation algorithm running privately on your local file-based music collection.

OpenPlaylister features both a modern **PyQt6 Desktop Graphical Interface** and a **Command-Line Interface (CLI)** powered by PyTorch and the `fairseq` sequence modeling toolkit.

---

## Features

- **Interactive PyQt6 GUI**: A unified dashboard to monitor your environment, scan your music library, download listening history, preprocess data, train models, and seed/generate playlists.
- **Local Music Library Scanner**: Automatically reads MusicBrainz ID (MBID) tags and extracts track durations from local audio files.
- **Physical Media Playlists (CD & Cassette Constraints)**: Generate time-bounded CD-Safe (80 mins) and Cassette-Safe (C60 side-restricted / C90 side-restricted) playlists.
- **Multi-playlist Output Folders**: Automatically saves batch files under dedicated directories (`CDs/`, `cassettes/`, `standard/`).
- **Full & Half Library Compilation**: Quickly generate randomized playlists from the entire collection (or half of it) without needing neural model evaluations.
- **Unique Playlist Randomization**: Optional nucleus sampling parameters (`--sampling-topp 0.9 --temperature 1.2`) to get highly diverse playlist recommenders on every run.
- **Interactive Playlist Editor**: Dedicated navigation tab to load `.m3u` files, delete songs, and reorder tracks using native **drag-and-drop** (`InternalMove`).
- **Parallel/Distributed Training Settings**: Configure world sizes (GPU counts) and CPU dataloader threads directly from settings.
- **ListenBrainz Integration**: Download your listening history directly from the ListenBrainz API or import an exported JSON file.
- **Simulated Test History**: Quick-start option to generate fake, randomized history using local tracks (or random UUIDs) to train the model without needing external accounts.
- **Fairseq Sequence Training**: Preprocesses history and trains a sequence-to-sequence Transformer model locally on your own machine.
- **Flexible Playlists**: Generates playlist sequences seeded with any local track and saves them as standard `.m3u` files compatible with any media player.

---

## Getting Started

### Prerequisites

OpenPlaylister requires:
- **Python 3.9+**
- **fairseq-preprocess** and **fairseq-train** CLI tools (installed via python requirements)
- **jq** (for CLI preprocessing)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jmartinmaster/openplaylister.git
   cd openplaylister
   ```

2. **Set up a Virtual Environment**:
   It is recommended to use `uv` or `venv` to isolate dependencies. For example, using `uv`:
   ```bash
   uv venv .venv-linux
   source .venv-linux/bin/activate
   uv pip install -r requirements.txt
   ```
   *(Alternatively, using standard `pip`)*:
   ```bash
   python3 -m venv .venv-linux
   source .venv-linux/bin/activate
   pip install -r requirements.txt
   ```

---

## How to Use

### 1. Graphical Interface (Recommended)

To launch the desktop client, run:
```bash
python3 run_gui.py
```

Within the GUI:
1. **Settings**: Configure your Music Directory, Playlist Save Path, theme, GPU distributed training counts, and import/download a ListenBrainz JSON history file.
2. **Scanner**: Click **Start Scan** to index your local audio files, extract track durations, and build a local map of MusicBrainz IDs (MBIDs).
3. **AI Training**:
   - If you don't have a ListenBrainz account, click **Preprocess History** and choose **Generate Fake History** to create a test dataset.
   - Click **Preprocess History** to convert your listening history into fairseq binary datasets.
   - Set retraining preferences or hide logs, then click **Train Model** to run the Transformer training pipeline.
4. **Generator**: Select a Target Mode (Standard, CD Safe, Cassette Safe, or static Full/Half Library), specify count and randomization options, choose a seed song from the table, and click **Generate Playlist**. Batch files are saved inside segregated subdirectories (`CDs/`, `cassettes/`, `standard/`) under the configured save folder.
5. **Edit Playlist**: Click **Load/Refresh Playlist** to load any `.m3u` file, rearrange tracks using native **drag-and-drop** reordering, delete songs, and save your edits.

---

### 2. Command-Line Interface (CLI)

If you prefer running commands directly in the shell:

1. **Index your music collection**:
   Ensure your music tracks have MusicBrainz tag IDs embedded (e.g. written via [MusicBrainz Picard](https://picard.musicbrainz.org/)). Run:
   ```bash
   python3 index_songs.py
   ```

2. **Preprocess history**:
   Export your history from [ListenBrainz settings](https://listenbrainz.org/settings/export/) as a JSON file, then run:
   ```bash
   ./preprocess.sh /path/to/listenbrainz_history.json
   ```

3. **Train the AI Model**:
   ```bash
   ./train.sh
   ```

4. **Generate a Playlist**:
   Choose a MusicBrainz recording ID to seed the sequence, and run:
   ```bash
   export MBID="your-musicbrainz-recording-uuid-here"
   echo ${MBID} | ./generate.sh | python3 write_playlist.py /path/to/playlist.m3u
   ```

---

## License

This project is licensed under the GPLv3 License (with MIT-licensed components).
- For the full license terms of the main project, see [LICENSE](LICENSE).
- For MIT portions, see [LICENSE.MIT](LICENSE.MIT).
