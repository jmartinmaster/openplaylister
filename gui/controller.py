# OpenPlaylister AI - AI Playlist Generator
# Copyright (c) 2024 Paul Sajna
# Copyright (c) 2026 Antigravity / OpenPlaylister Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Portions of this software are derived from work originally licensed
# under the MIT License. See LICENSE.MIT for details.

# gui/controller.py

import os
import shlex
from PyQt6.QtCore import Qt, QObject
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QMessageBox, QInputDialog
from gui.styles import DARK_THEME, LIGHT_THEME
from gui.workers import MusicScannerWorker, CommandWorker, ListenBrainzDownloadWorker, TagResolverWorker

class OpenPlaylisterController(QObject):
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        
        # State tracking
        self.scan_worker = None
        self.cmd_worker = None
        self.selected_seed_mbid = None
        
        # Timer & Stopwatch tracking for active processes
        from PyQt6.QtCore import QTimer
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.on_ui_timer_tick)
        self.active_task = None  # scan, autotag, preprocess, train, download
        self.task_start_time = 0.0
        
        # Initialize UI elements from current configuration settings
        self.view.set_settings_inputs(self.model.config)
        self.apply_theme(self.model.get_config_value("theme"))
        
        # Initial status updates
        self.update_statuses()
        self.populate_tables()
        
        # Connect signals
        self.connect_signals()

    def connect_signals(self):
        # Sidebar / Tab Navigation
        self.view.nav_changed.connect(self.on_nav_changed)
        
        # Settings view signals
        self.view.browse_music_clicked.connect(self.on_browse_music)
        self.view.browse_json_clicked.connect(self.on_browse_json)
        self.view.browse_playlist_clicked.connect(self.on_browse_playlist)
        self.view.save_settings_clicked.connect(self.on_save_settings)
        self.view.theme_changed.connect(self.on_theme_changed)
        
        # Auto-save settings on focus loss (editing finished)
        self.view.txt_music_dir.editingFinished.connect(self.on_music_dir_edited)
        self.view.txt_json_path.editingFinished.connect(self.on_json_path_edited)
        self.view.txt_playlist_path.editingFinished.connect(self.on_playlist_path_edited)
        
        # Search Filter inputs
        self.view.txt_scan_search.textChanged.connect(
            lambda text: self.filter_table(self.view.table_songs, text)
        )
        self.view.txt_seed_search.textChanged.connect(
            lambda text: self.filter_table(self.view.table_seed_songs, text)
        )
        
        # Queue bindings
        self.queued_playlist_tracks = []
        self.view.btn_add_album.clicked.connect(self.on_add_album_to_queue)
        self.view.btn_add_artist.clicked.connect(self.on_add_artist_to_queue)
        self.view.btn_add_track.clicked.connect(self.on_add_track_to_queue)
        self.view.btn_remove_queued.clicked.connect(self.on_remove_queued_track)
        self.view.btn_clear_queue.clicked.connect(self.on_clear_queue)
        self.view.btn_generate_queued.clicked.connect(self.on_generate_queued_playlist)

        # Seed song selection table click
        self.view.table_seed_songs.itemSelectionChanged.connect(self.on_seed_selected)
        self.view.btn_generate.clicked.connect(self.on_generate_playlist)
        
        # Playlist editor signals
        self.view.load_playlist_clicked.connect(self.on_load_playlist)
        self.view.save_playlist_clicked.connect(self.on_save_playlist)
        self.view.combo_gen_mode.currentTextChanged.connect(self.on_gen_mode_changed)
        
        # Training / Preprocessing controls
        self.view.preprocess_clicked.connect(self.on_run_preprocess)
        self.view.train_clicked.connect(self.on_run_train)
        self.view.stop_train_clicked.connect(self.on_stop_cmd_worker)
        
        # Scanner controls
        self.register_scanner_bindings()
        self.view.autotag_clicked.connect(self.on_start_autotag)
        self.view.stop_autotag_clicked.connect(self.on_stop_autotag)

        # CD Burning signals
        self.view.burn_browse_playlist_clicked.connect(self.on_burn_browse_playlist)
        self.view.run_convert_wav_clicked.connect(self.on_run_convert_wav)
        self.view.run_burn_cd_clicked.connect(self.on_run_burn_cd)
        self.view.run_burn_drive_clicked.connect(self.on_run_burn_single_drive)
        self.view.rescan_drives_clicked.connect(self.scan_drives)
        self.view.stop_burn_clicked.connect(self.on_stop_burn)
        self.view.eject_drive_clicked.connect(self.on_eject_drive)
        self.view.combo_cd_capacity.currentTextChanged.connect(self.on_cd_capacity_changed)

        self.playlist_tracks = []
        self.converted_tracks = []
        self.burn_workers = []
        self.wav_worker = None


    # ----------------------------------------------------
    # Timer and Formatting Helpers
    # ----------------------------------------------------
    def on_ui_timer_tick(self):
        import time
        if not self.active_task:
            self.ui_timer.stop()
            return
            
        elapsed = time.time() - self.task_start_time
        formatted_elapsed = self.format_time(elapsed)
        
        if self.active_task in ("scan", "autotag"):
            # Update scan elapsed time
            current = self.view.scan_progress.value()
            total = self.view.scan_progress.maximum()
            
            if current > 0 and total > 0 and current < total:
                rate = current / elapsed
                remaining = (total - current) / rate
                formatted_remaining = self.format_time(remaining)
                self.view.lbl_scan_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: {formatted_remaining}")
            elif current >= total and total > 0:
                self.view.lbl_scan_time.setText(f"Elapsed: {formatted_elapsed} | Complete")
            else:
                self.view.lbl_scan_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: --:--")
                
        elif self.active_task in ("preprocess", "train", "download"):
            # Update training page elapsed time
            current = self.view.train_progress.value()
            total = self.view.train_progress.maximum()
            
            if self.active_task == "train" and current > 0 and total > 0 and current < total:
                start_update = getattr(self, "train_start_update", None)
                start_time = getattr(self, "train_start_update_time", None)
                
                if start_update is not None and start_time is not None and current - start_update >= 10:
                    elapsed_since_start = time.time() - start_time
                    updates_since_start = current - start_update
                    if elapsed_since_start > 0 and updates_since_start > 0:
                        rate = updates_since_start / elapsed_since_start
                        remaining = (total - current) / rate
                        formatted_remaining = self.format_time(remaining)
                        self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: {formatted_remaining}")
                    else:
                        self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: --:--")
                else:
                    self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: Estimating...")
            elif self.active_task == "download":
                self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed}")
            elif self.active_task == "preprocess":
                self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed}")
            else:
                self.view.lbl_train_time.setText(f"Elapsed: {formatted_elapsed} | Remaining: --:--")

    def format_time(self, seconds):
        if seconds < 0:
            return "00:00"
        s = int(seconds)
        hours = s // 3600
        minutes = (s % 3600) // 60
        secs = s % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    # ----------------------------------------------------
    # Navigation and Status Handling
    # ----------------------------------------------------
    def on_nav_changed(self, index):
        # Refresh statuses when visiting Dashboard
        if index == 0:
            self.update_statuses()
        elif index == 4:
            self.scan_drives()
        elif index == 5:
            self.on_load_playlist()

    def update_statuses(self):
        status = self.model.get_dashboard_status()
        self.view.update_dashboard(status)
        self.view.update_sidebar_status(
            status["fairseq_ok"],
            status["music_index_ok"],
            status["model_trained_ok"],
            status["index_count"]
        )

    def populate_tables(self):
        self.view.table_songs.setRowCount(0)
        self.view.table_seed_songs.setRowCount(0)
        
        for song in self.model.songs_list:
            # Scanner table
            row_scanner = self.view.table_songs.rowCount()
            self.view.table_songs.insertRow(row_scanner)
            self.view.table_songs.setItem(row_scanner, 0, QTableWidgetItem(song["title"]))
            self.view.table_songs.setItem(row_scanner, 1, QTableWidgetItem(song["artist"]))
            self.view.table_songs.setItem(row_scanner, 2, QTableWidgetItem(song["mbid"]))
            self.view.table_songs.setItem(row_scanner, 3, QTableWidgetItem(song["path"]))
            
            # Seed Selector table
            row_seed = self.view.table_seed_songs.rowCount()
            self.view.table_seed_songs.insertRow(row_seed)
            self.view.table_seed_songs.setItem(row_seed, 0, QTableWidgetItem(song["title"]))
            self.view.table_seed_songs.setItem(row_seed, 1, QTableWidgetItem(song["artist"]))
            self.view.table_seed_songs.setItem(row_seed, 2, QTableWidgetItem(song.get("album", "Unknown Album")))
            self.view.table_seed_songs.setItem(row_seed, 3, QTableWidgetItem(song["mbid"]))

    def filter_table(self, table_widget, search_text):
        search_text = search_text.lower()
        for row in range(table_widget.rowCount()):
            match = False
            for col in range(table_widget.columnCount()):
                item = table_widget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            table_widget.setRowHidden(row, not match)

    # ----------------------------------------------------
    # Settings and Themes
    # ----------------------------------------------------
    def on_browse_music(self):
        current_dir = self.model.get_config_value("music_dir")
        path = self.view.select_directory("Select Music Collection Folder", current_dir)
        if path:
            self.view.txt_music_dir.setText(path)
            self.model.set_config_value("music_dir", path)
            self.update_statuses()

    def on_browse_json(self):
        current_dir = os.path.dirname(self.model.get_config_value("listenbrainz_json")) or ""
        path = self.view.select_file("Select ListenBrainz History JSON File", "JSON Files (*.json)", current_dir)
        if path:
            self.view.txt_json_path.setText(path)
            self.model.set_config_value("listenbrainz_json", path)
            self.update_statuses()

    def on_browse_playlist(self):
        current_dir = self.model.get_config_value("playlist_save_path")
        if current_dir and current_dir.endswith(".m3u"):
            current_dir = os.path.dirname(current_dir)
        path = self.view.select_directory("Select Playlist Output Root Folder", current_dir)
        if path:
            self.view.txt_playlist_path.setText(path)
            self.model.set_config_value("playlist_save_path", path)
            self.update_statuses()

    def on_music_dir_edited(self):
        path = self.view.txt_music_dir.text().strip()
        self.model.set_config_value("music_dir", path)
        self.update_statuses()

    def on_json_path_edited(self):
        path = self.view.txt_json_path.text().strip()
        self.model.set_config_value("listenbrainz_json", path)
        self.update_statuses()

    def on_playlist_path_edited(self):
        path = self.view.txt_playlist_path.text().strip()
        self.model.set_config_value("playlist_save_path", path)
        self.update_statuses()

    def on_save_settings(self):
        # Keeps manual confirmation option, though auto-saving is already in place
        inputs = self.view.get_settings_inputs()
        for k, v in inputs.items():
            self.model.set_config_value(k, v)
        QMessageBox.information(self.view, "Settings Saved", "Application settings have been saved successfully.")
        self.update_statuses()

    def on_theme_changed(self, theme_name):
        self.model.set_config_value("theme", theme_name)
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name):
        app = QApplication.instance()
        if not app:
            return
        if theme_name == "light":
            app.setStyleSheet(LIGHT_THEME)
        else:
            app.setStyleSheet(DARK_THEME)

    # ----------------------------------------------------
    # Music Scanner Threading Control
    # ----------------------------------------------------
    def on_start_scan(self):
        music_dir = self.model.get_config_value("music_dir")
        if not music_dir or not os.path.exists(music_dir):
            QMessageBox.warning(self.view, "Path Error", "Please configure a valid Music Collection Directory under Settings first.")
            return
            
        self.model.clear_index()
        self.view.table_songs.setRowCount(0)
        self.view.table_seed_songs.setRowCount(0)
        
        self.view.btn_scan.setEnabled(False)
        self.view.btn_stop_scan.setEnabled(True)
        self.view.scan_progress.setValue(0)
        self.view.lbl_scan_status.setText("Scanning directory recursively...")
        
        # Start timer
        import time
        self.active_task = "scan"
        self.task_start_time = time.time()
        self.view.lbl_scan_time.setText("Elapsed: 00:00 | Remaining: --:--")
        self.ui_timer.start(1000)
        
        self.scan_worker = MusicScannerWorker(music_dir)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.song_found.connect(self.on_song_found)
        self.scan_worker.finished_scanning.connect(self.on_scan_finished)
        self.scan_worker.error_occurred.connect(self.on_scan_error)
        self.scan_worker.start()

    def on_scan_progress(self, current, total, file_path):
        self.view.scan_progress.setMaximum(total)
        self.view.scan_progress.setValue(current)
        self.view.lbl_scan_status.setText(f"Scanning file ({current}/{total}): {os.path.basename(file_path)}")

    def on_song_found(self, song):
        self.model.add_scanned_song(song)
        
        # Append to Scanner table
        row_scanner = self.view.table_songs.rowCount()
        self.view.table_songs.insertRow(row_scanner)
        self.view.table_songs.setItem(row_scanner, 0, QTableWidgetItem(song["title"]))
        self.view.table_songs.setItem(row_scanner, 1, QTableWidgetItem(song["artist"]))
        self.view.table_songs.setItem(row_scanner, 2, QTableWidgetItem(song["mbid"]))
        self.view.table_songs.setItem(row_scanner, 3, QTableWidgetItem(song["path"]))
        
        # Append to Seed Selector table
        row_seed = self.view.table_seed_songs.rowCount()
        self.view.table_seed_songs.insertRow(row_seed)
        self.view.table_seed_songs.setItem(row_seed, 0, QTableWidgetItem(song["title"]))
        self.view.table_seed_songs.setItem(row_seed, 1, QTableWidgetItem(song["artist"]))
        self.view.table_seed_songs.setItem(row_seed, 2, QTableWidgetItem(song.get("album", "Unknown Album")))
        self.view.table_seed_songs.setItem(row_seed, 3, QTableWidgetItem(song["mbid"]))

    def on_scan_finished(self, final_index):
        self.model.save_gui_index()
        self.view.btn_scan.setEnabled(True)
        self.view.btn_stop_scan.setEnabled(False)
        self.view.lbl_scan_status.setText(f"Scanning complete! Indexed {len(final_index)} songs.")
        
        # Stop timer
        self.active_task = None
        self.ui_timer.stop()
        
        self.update_statuses()
        self.scan_worker = None

    def on_scan_error(self, message):
        self.view.lbl_scan_status.setText(f"Scanner: {message}")
        self.active_task = None
        self.ui_timer.stop()

    def on_stop_scan(self):
        if self.scan_worker:
            self.scan_worker.stop()
            self.view.lbl_scan_status.setText("Scan cancellation requested...")

    # Wire scan actions (overriding signals)
    def register_scanner_bindings(self):
        # Remap view button clicks directly
        self.view.start_scan_clicked.connect(self.on_start_scan)
        self.view.stop_scan_clicked.connect(self.on_stop_scan)

    # ----------------------------------------------------
    # Subprocess / CLI Command Workers
    # ----------------------------------------------------
    def on_run_preprocess(self):
        json_path = self.model.get_config_value("listenbrainz_json")
        if not json_path or not os.path.exists(json_path):
            # Prompt user with choices
            msg = QMessageBox(self.view)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle("Missing ListenBrainz History")
            msg.setText("No ListenBrainz history JSON file has been selected.")
            msg.setInformativeText("To train the AI, you must import your ListenBrainz listening history. Would you like to select an existing file, download your history directly from the ListenBrainz API, or generate fake history at random for testing?")
            
            browse_btn = msg.addButton("Browse File...", QMessageBox.ButtonRole.ActionRole)
            download_btn = msg.addButton("Download from API...", QMessageBox.ButtonRole.ActionRole)
            fake_btn = msg.addButton("Generate Fake History", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg.addButton(QMessageBox.StandardButton.Cancel)
            
            msg.exec()
            
            clicked = msg.clickedButton()
            if clicked == browse_btn:
                self.on_browse_json()
                # Reload path
                json_path = self.model.get_config_value("listenbrainz_json")
                if not json_path or not os.path.exists(json_path):
                    return
            elif clicked == download_btn:
                self.prompt_and_download_history()
                return
            elif clicked == fake_btn:
                self.generate_fake_history()
                return
            else:
                return

        self.view.console_logs.clear()
        
        # Spotify format detection
        is_spotify = False
        target_path = json_path
        try:
            with open(json_path, "r") as f:
                import json
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    if "artistName" in first_item or "master_metadata_album_artist_name" in first_item:
                        is_spotify = True
        except Exception:
            pass

        if is_spotify:
            self.view.console_logs.appendPlainText(">>> Detected Spotify Streaming History format. Resolving tracks to local MusicBrainz IDs...")
            translated_path = os.path.abspath("spotify_translated.json")
            import sys
            import subprocess
            try:
                conv_cmd = [sys.executable, "spotify_to_listenbrainz.py", json_path, translated_path]
                res = subprocess.run(conv_cmd, capture_output=True, text=True, check=True)
                self.view.console_logs.appendPlainText(res.stdout)
                target_path = translated_path
            except Exception as e:
                self.view.console_logs.appendPlainText(f">>> Spotify translation error: {str(e)}")
                QMessageBox.critical(self.view, "Import Error", f"Failed to translate Spotify history: {str(e)}")
                return

        self.view.console_logs.appendPlainText(">>> Executing: preprocess.sh " + target_path)
        
        # Disable buttons while running
        self.set_training_buttons_enabled(False)
        
        # Start timer
        import time
        self.active_task = "preprocess"
        self.task_start_time = time.time()
        self.view.train_progress_card.setVisible(True)
        self.view.lbl_train_status.setText("Preprocessing history...")
        self.view.lbl_train_time.setText("Elapsed: 00:00")
        self.view.train_progress.setRange(0, 0)
        self.ui_timer.start(1000)

        cmd = f"./preprocess.sh {target_path}"
        self.cmd_worker = CommandWorker(cmd)
        self.cmd_worker.line_read.connect(self.on_cmd_line)
        self.cmd_worker.finished_command.connect(self.on_cmd_finished)
        self.cmd_worker.start()

    def generate_fake_history(self):
        import random
        import uuid
        import json
        
        # Save inside the folder where the playlist is saved, or current directory
        save_path = self.model.get_config_value("playlist_save_path")
        out_dir = os.path.dirname(os.path.abspath(save_path)) if save_path else os.getcwd()
        dest_file = os.path.join(out_dir, "fake_history.json")
        
        # If we have local songs, use their MBIDs. Otherwise, generate random UUIDs.
        mbids = [song["mbid"] for song in self.model.songs_list if song.get("mbid")]
        
        if not mbids:
            # Fallback to random UUIDs
            mbids = [str(uuid.uuid4()) for _ in range(50)]
            
        listens = []
        # Generate 1500 listening history items
        for _ in range(1500):
            mbid = random.choice(mbids)
            listens.append({
                "track_metadata": {
                    "mbid_mapping": {
                        "recording_mbid": mbid
                    }
                }
            })
            
        try:
            with open(dest_file, "w") as f:
                json.dump(listens, f, indent=4)
                
            self.view.console_logs.clear()
            self.view.console_logs.appendPlainText(f">>> Generated fake listening history file at: {dest_file}")
            self.model.set_config_value("listenbrainz_json", dest_file)
            self.view.set_settings_inputs(self.model.config)
            self.update_statuses()
            
            # Automatically start preprocessing
            self.on_run_preprocess()
        except Exception as e:
            QMessageBox.critical(
                self.view,
                "Generation Error",
                f"Failed to generate fake history: {str(e)}"
            )

    def on_run_train(self):
        if not self.model.check_fairseq_installed():
            QMessageBox.warning(self.view, "Dependency Error", "fairseq binary tools were not found in your system PATH.")
            return

        # Wipe checkpoints if retraining from scratch
        if self.view.chk_retrain.isChecked():
            import shutil
            checkpoints_dir = os.path.abspath("checkpoints/brainz")
            if os.path.exists(checkpoints_dir):
                try:
                    shutil.rmtree(checkpoints_dir)
                    self.view.console_logs.appendPlainText(">>> Wiped existing checkpoints for retraining from scratch.")
                except Exception as e:
                    QMessageBox.warning(self.view, "Clean Error", f"Failed to wipe checkpoints folder: {str(e)}")
                    return

        dict_path = os.path.join("data-bin", "brainz", "dict.txt")
        if not os.path.exists(dict_path):
            msg = QMessageBox(self.view)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle("Preprocessing Required")
            msg.setText("ListenBrainz history has not been preprocessed yet.")
            msg.setInformativeText("The model cannot be trained without preprocessed history data. Would you like to preprocess your history now?")
            yes_btn = msg.addButton("Preprocess Now", QMessageBox.ButtonRole.YesRole)
            cancel_btn = msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()
            
            if msg.clickedButton() == yes_btn:
                self.on_run_preprocess()
            return

        # Check for vocabulary shape mismatch with checkpoint_last.pt
        checkpoint_path = os.path.join("checkpoints", "brainz", "checkpoint_last.pt")
        if os.path.exists(checkpoint_path):
            try:
                # Count vocabulary size of dict.txt
                with open(dict_path, "r") as f:
                    current_vocab = sum(1 for line in f if line.strip()) + 4
                
                # Load checkpoint using PyTorch
                import torch
                state = torch.load(checkpoint_path, map_location="cpu")
                if "model" in state and "decoder.embed_tokens.weight" in state["model"]:
                    checkpoint_vocab = state["model"]["decoder.embed_tokens.weight"].shape[0]
                    if current_vocab != checkpoint_vocab:
                        self.view.console_logs.appendPlainText(
                            f">>> Vocabulary size mismatch detected (checkpoint: {checkpoint_vocab}, current: {current_vocab}). "
                            "Wiping old checkpoints to prevent training failure..."
                        )
                        import shutil
                        checkpoints_dir = os.path.abspath("checkpoints/brainz")
                        shutil.rmtree(checkpoints_dir)
                        os.makedirs(checkpoints_dir, exist_ok=True)
            except Exception as e:
                self.view.console_logs.appendPlainText(f">>> Warning checking checkpoint compatibility: {str(e)}")

        self.view.console_logs.clear()
        
        # Build command with parallel training arguments
        num_workers = self.model.get_config_value("num_workers") or "1"
        num_gpus = self.model.get_config_value("num_gpus") or "1"
        train_level = int(self.model.get_config_value("train_level") or 30000)
        self.current_train_level = train_level
        
        train_args = []
        if int(num_workers) > 1:
            train_args.append(f"--num-workers {num_workers}")
        if int(num_gpus) > 1:
            train_args.append(f"--distributed-world-size {num_gpus}")
            train_args.append(f"--nprocs-per-node {num_gpus}")
            
        train_args.append(f"--max-update {train_level}")
        
        train_args_str = " ".join(train_args)
        cmd = f"./train.sh {train_args_str}".strip()
        
        self.view.console_logs.appendPlainText(f">>> Executing: {cmd}")
        
        self.set_training_buttons_enabled(False)
        
        # Start timer
        import time
        self.active_task = "train"
        self.task_start_time = time.time()
        self.train_start_update = None
        self.train_start_update_time = None
        self.view.train_progress_card.setVisible(True)
        self.view.lbl_train_status.setText(f"Training AI model (Updates: 0 / {train_level})...")
        self.view.lbl_train_time.setText("Elapsed: 00:00 | Remaining: Estimating...")
        self.view.train_progress.setRange(0, train_level)
        self.view.train_progress.setValue(0)
        self.ui_timer.start(1000)

        self.cmd_worker = CommandWorker(cmd)
        self.cmd_worker.line_read.connect(self.on_cmd_line)
        self.cmd_worker.finished_command.connect(self.on_cmd_finished)
        self.cmd_worker.start()

    def on_cmd_line(self, line):
        self.view.console_logs.appendPlainText(line)
        
        # Parse training progress
        if self.active_task == "train" and "num_updates" in line:
            import re
            match = re.search(r"num_updates[^\d]*(\d+)", line)
            if match:
                current_update = int(match.group(1))
                self.view.train_progress.setValue(current_update)
                train_level = getattr(self, "current_train_level", 30000)
                self.view.lbl_train_status.setText(f"Training AI model (Updates: {current_update} / {train_level})...")
                
                import time
                if self.train_start_update is None:
                    self.train_start_update = current_update
                    self.train_start_update_time = time.time()
                elif current_update - self.train_start_update >= 10:
                    elapsed_since_start = time.time() - self.train_start_update_time
                    updates_since_start = current_update - self.train_start_update
                    if elapsed_since_start > 0 and updates_since_start > 0:
                        rate = updates_since_start / elapsed_since_start
                        remaining = (train_level - current_update) / rate
                        self.view.lbl_train_time.setText(f"Elapsed: {self.format_time(time.time() - self.task_start_time)} | Remaining: {self.format_time(remaining)}")

    def on_cmd_finished(self, exit_code):
        self.view.console_logs.appendPlainText(f"\n>>> Process finished with exit code: {exit_code}")
        self.set_training_buttons_enabled(True)
        
        # Stop timer
        self.active_task = None
        self.ui_timer.stop()
        self.view.train_progress.setRange(0, 100)
        self.view.train_progress.setValue(100)
        if exit_code == 0:
            self.view.lbl_train_status.setText("Execution complete!")
        else:
            self.view.lbl_train_status.setText(f"Execution failed with code: {exit_code}")
            
        self.update_statuses()
        self.cmd_worker = None

    def on_stop_cmd_worker(self):
        if self.cmd_worker:
            self.view.console_logs.appendPlainText("\n>>> Stopping execution...")
            self.cmd_worker.stop()

    def set_training_buttons_enabled(self, enabled):
        self.view.btn_preprocess.setEnabled(enabled)
        self.view.btn_train.setEnabled(enabled)
        self.view.btn_stop_train.setEnabled(not enabled)

    # ----------------------------------------------------
    # Playlist Generation
    # ----------------------------------------------------
    def on_seed_selected(self):
        selected_ranges = self.view.table_seed_songs.selectedRanges()
        if not selected_ranges:
            self.view.lbl_selected_seed.setText("No Seed Track Selected")
            self.view.btn_generate.setEnabled(False)
            self.selected_seed_mbid = None
            self.selected_seed_artist = None
            self.selected_seed_album = None
            self.selected_seed_title = None
            return
            
        row = selected_ranges[0].topRow()
        title = self.view.table_seed_songs.item(row, 0).text()
        artist = self.view.table_seed_songs.item(row, 1).text()
        album = self.view.table_seed_songs.item(row, 2).text()
        mbid = self.view.table_seed_songs.item(row, 3).text()
        
        self.selected_seed_mbid = mbid
        self.selected_seed_artist = artist
        self.selected_seed_album = album
        self.selected_seed_title = title
        
        # Album completeness check
        album_name_lower = album.strip().lower()
        artist_name_lower = artist.strip().lower()
        album_songs = [s for s in self.model.songs_list if s.get("album", "").strip().lower() == album_name_lower and s.get("artist", "").strip().lower() == artist_name_lower]
        if not album_songs:
            album_songs = [s for s in self.model.songs_list if s.get("album", "").strip().lower() == album_name_lower]
            
        alb_duration = sum(s.get("duration", 240.0) for s in album_songs)
        alb_m = int(alb_duration // 60)
        alb_s = int(alb_duration % 60)
        self.view.lbl_album_info.setText(
            f"Album Availability: <b>'{album}'</b> by <b>{artist}</b> — <b>{len(album_songs)}</b> tracks in library ({alb_m}m {alb_s:02d}s)"
        )
        
        gen_mode = self.view.combo_gen_mode.currentText()
        if gen_mode == "Single Artist":
            self.view.lbl_selected_seed.setText(f"Target Artist: <b>{artist}</b><br><small>Seed Track: '{title}' ({album})</small>")
        elif gen_mode == "Recreate Album":
            self.view.lbl_selected_seed.setText(f"Target Album: <b>{album}</b> by <b>{artist}</b><br><small>Seed Track: '{title}'</small>")
        else:
            self.view.lbl_selected_seed.setText(f"Seed: <b>{title}</b> by <b>{artist}</b><br><small>Album: {album} | MBID: {mbid}</small>")
        self.view.btn_generate.setEnabled(True)

    # ----------------------------------------------------
    # Multi-Item Playlist Builder Queue
    # ----------------------------------------------------
    def on_add_album_to_queue(self):
        if not getattr(self, "selected_seed_album", None):
            QMessageBox.warning(self.view, "Selection Error", "Please select a song in the seed table to specify an album.")
            return
            
        album_name = self.selected_seed_album.strip().lower()
        artist_name = (self.selected_seed_artist or "").strip().lower()
        
        album_songs = [s for s in self.model.songs_list if s.get("album", "").strip().lower() == album_name and s.get("artist", "").strip().lower() == artist_name]
        if not album_songs:
            album_songs = [s for s in self.model.songs_list if s.get("album", "").strip().lower() == album_name]
            
        import re
        def natural_sort_key(song):
            filename = os.path.basename(song["path"])
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]
        album_songs.sort(key=natural_sort_key)
        
        added_count = 0
        existing_paths = {s["path"] for s in self.queued_playlist_tracks}
        for song in album_songs:
            if song["path"] not in existing_paths:
                self.queued_playlist_tracks.append(song)
                existing_paths.add(song["path"])
                added_count += 1
                
        self.update_queue_ui()
        self.view.lbl_generation_status.setText(f"Added {added_count} tracks from album '{self.selected_seed_album}' to queue.")

    def on_add_artist_to_queue(self):
        if not getattr(self, "selected_seed_artist", None):
            QMessageBox.warning(self.view, "Selection Error", "Please select a song in the seed table to specify an artist.")
            return
            
        artist_name = self.selected_seed_artist.strip().lower()
        artist_songs = [s for s in self.model.songs_list if s.get("artist", "").strip().lower() == artist_name]
        if not artist_songs:
            artist_songs = [s for s in self.model.songs_list if artist_name in s.get("artist", "").strip().lower()]
            
        artist_songs.sort(key=lambda s: (s.get("album", "").lower(), os.path.basename(s["path"]).lower()))
        
        added_count = 0
        existing_paths = {s["path"] for s in self.queued_playlist_tracks}
        for song in artist_songs:
            if song["path"] not in existing_paths:
                self.queued_playlist_tracks.append(song)
                existing_paths.add(song["path"])
                added_count += 1
                
        self.update_queue_ui()
        self.view.lbl_generation_status.setText(f"Added {added_count} tracks by artist '{self.selected_seed_artist}' to queue.")

    def on_add_track_to_queue(self):
        if not getattr(self, "selected_seed_mbid", None):
            QMessageBox.warning(self.view, "Selection Error", "Please select a song in the seed table to add to queue.")
            return
            
        target_song = None
        for s in self.model.songs_list:
            if s["mbid"] == self.selected_seed_mbid:
                target_song = s
                break
                
        if not target_song:
            return
            
        existing_paths = {s["path"] for s in self.queued_playlist_tracks}
        if target_song["path"] not in existing_paths:
            self.queued_playlist_tracks.append(target_song)
            self.update_queue_ui()
            self.view.lbl_generation_status.setText(f"Added track '{target_song['title']}' to queue.")
        else:
            QMessageBox.information(self.view, "Already Queued", f"Track '{target_song['title']}' is already in the playlist queue.")

    def on_remove_queued_track(self):
        selected_ranges = self.view.table_playlist_queue.selectedRanges()
        if not selected_ranges:
            return
        row = selected_ranges[0].topRow()
        if 0 <= row < len(self.queued_playlist_tracks):
            removed = self.queued_playlist_tracks.pop(row)
            self.update_queue_ui()
            self.view.lbl_generation_status.setText(f"Removed '{removed['title']}' from queue.")

    def on_clear_queue(self):
        self.queued_playlist_tracks = []
        self.update_queue_ui()
        self.view.lbl_generation_status.setText("Playlist queue cleared.")

    def update_queue_ui(self):
        self.view.table_playlist_queue.setRowCount(0)
        total_duration = 0.0
        
        for idx, song in enumerate(self.queued_playlist_tracks, start=1):
            row = self.view.table_playlist_queue.rowCount()
            self.view.table_playlist_queue.insertRow(row)
            
            dur_val = song.get("duration", 240.0)
            total_duration += dur_val
            m = int(dur_val // 60)
            s = int(dur_val % 60)
            
            self.view.table_playlist_queue.setItem(row, 0, QTableWidgetItem(str(idx)))
            self.view.table_playlist_queue.setItem(row, 1, QTableWidgetItem(song["title"]))
            self.view.table_playlist_queue.setItem(row, 2, QTableWidgetItem(song["artist"]))
            self.view.table_playlist_queue.setItem(row, 3, QTableWidgetItem(song.get("album", "Unknown Album")))
            self.view.table_playlist_queue.setItem(row, 4, QTableWidgetItem(f"{m}:{s:02d}"))
            
        # Update progress bar and capacity label
        self.view.progress_disc_capacity.setValue(min(4800, int(total_duration)))
        
        tot_m = int(total_duration // 60)
        tot_s = int(total_duration % 60)
        pct = int((total_duration / 4800.0) * 100)
        rem_sec = 4800.0 - total_duration
        
        if rem_sec >= 0:
            rem_m = int(rem_sec // 60)
            rem_s = int(rem_sec % 60)
            self.view.lbl_disc_capacity.setText(
                f"CD Capacity: {tot_m}m {tot_s:02d}s / 80:00 ({pct}% full) — <b>{rem_m}m {rem_s:02d}s remaining</b>"
            )
            self.view.lbl_disc_capacity.setStyleSheet("font-size: 12px; font-weight: bold; color: #818cf8;")
        else:
            over_sec = abs(rem_sec)
            over_m = int(over_sec // 60)
            over_s = int(over_sec % 60)
            self.view.lbl_disc_capacity.setText(
                f"CD Capacity: {tot_m}m {tot_s:02d}s / 80:00 ({pct}% full) — ⚠️ <b>EXCEEDS DISC LIMIT BY {over_m}m {over_s:02d}s</b>"
            )
            self.view.lbl_disc_capacity.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")

    def on_generate_queued_playlist(self):
        if not self.queued_playlist_tracks:
            QMessageBox.warning(self.view, "Queue Empty", "The playlist queue is empty. Add tracks or albums first.")
            return
            
        save_path = self.model.get_config_value("playlist_save_path")
        if not save_path:
            QMessageBox.warning(self.view, "Path Error", "Please configure a valid Playlist Save Path under Settings.")
            return
            
        temp_queue_file = "checkpoints/queued_tracks.txt"
        os.makedirs("checkpoints", exist_ok=True)
        with open(temp_queue_file, "w") as f:
            for s in self.queued_playlist_tracks:
                f.write(s["path"] + "\n")
                
        self.view.gen_console.clear()
        self.view.gen_console.appendPlainText(f">>> Processing queued multi-item playlist ({len(self.queued_playlist_tracks)} tracks)...")
        self.view.lbl_generation_status.setText("Exporting custom queued playlist...")
        
        cmd = f"python3 write_playlist.py {shlex.quote(save_path)} --mode custom --tracks-file {shlex.quote(temp_queue_file)}"
        self.gen_worker = CommandWorker(cmd)
        self.gen_worker.line_read.connect(self.on_gen_log)
        self.gen_worker.finished_command.connect(self.on_gen_finished)
        self.gen_worker.start()

    def on_generate_playlist(self):
        mode_map = {
            "Standard AI Playlist": "standard",
            "Single Artist": "artist",
            "Recreate Album": "album",
            "CD Safe (80 Minutes)": "cd",
            "Cassette C60 (30 Mins / Side)": "c60",
            "Cassette C90 (45 Mins / Side)": "c90",
            "Full Library": "full",
            "Half Library": "half"
        }
        mode_str = mode_map.get(self.view.combo_gen_mode.currentText(), "standard")
        count = self.view.spin_playlist_count.value()

        self.view.gen_console.clear()

        if mode_str == "artist":
            if not getattr(self, "selected_seed_artist", None):
                QMessageBox.warning(self.view, "Seed Error", "Please select a seed track to specify target Artist.")
                return
            self.on_add_artist_to_queue()
            self.view.lbl_generation_status.setText(
                f"Populated tracks for artist '{self.selected_seed_artist}' into playlist table below. Click 'Save Playlist' at the bottom to export."
            )
            return

        elif mode_str == "album":
            if not getattr(self, "selected_seed_album", None):
                QMessageBox.warning(self.view, "Seed Error", "Please select a seed track to specify target Album.")
                return
            self.on_add_album_to_queue()
            self.view.lbl_generation_status.setText(
                f"Populated tracks for album '{self.selected_seed_album}' into playlist table below. Click 'Save Playlist' at the bottom to export."
            )
            return

        elif mode_str in ("full", "half"):
            import random
            pool = list(self.model.songs_list)
            random.seed(42)
            random.shuffle(pool)
            if mode_str == "half":
                pool = pool[:max(1, len(pool) // 2)]
            self.queued_playlist_tracks = pool
            self.update_queue_ui()
            self.view.lbl_generation_status.setText(
                f"Populated {len(pool)} tracks ({mode_str} library) into playlist table below. Click 'Save Playlist' at the bottom to export."
            )
            return

        # AI generation modes
        if not getattr(self, "selected_seed_mbid", None):
            QMessageBox.warning(self.view, "Seed Error", "Please select a seed track for AI generation first.")
            return

        save_path = self.model.get_config_value("playlist_save_path") or "playlist.m3u"
        self.view.btn_generate.setEnabled(False)
        self.view.gen_console.appendPlainText(f">>> Seed mbid: {self.selected_seed_mbid}")
        self.view.gen_console.appendPlainText(">>> Verifying system prerequisites and model vocabulary shape compatibility...")
        self.view.lbl_generation_status.setText("Checking AI prerequisites...")

        from gui.workers import PrereqRunnerWorker
        music_dir = self.model.get_config_value("music_directory") or "standard"
        self.prereq_worker = PrereqRunnerWorker(music_dir=music_dir)
        self.prereq_worker.log_signal.connect(self.on_gen_log)
        self.prereq_worker.status_signal.connect(self.view.lbl_generation_status.setText)
        self.prereq_worker.finished_prereqs.connect(
            lambda success, msg: self.on_prereqs_finished(success, msg, save_path, mode_str, count)
        )
        self.prereq_worker.start()

    def on_prereqs_finished(self, success, msg, save_path, mode_str, count):
        if not success:
            self.view.lbl_generation_status.setText(f"Prerequisite check failed: {msg}")
            self.view.gen_console.appendPlainText(f">>> Prerequisite Check Error: {msg}")
            self.view.btn_generate.setEnabled(True)
            return

        self.view.gen_console.appendPlainText(">>> Executing sequence inference pipeline...")
        self.view.lbl_generation_status.setText("Generating playlist customized by AI recommendations...")

        gen_args = []
        if self.view.chk_randomize.isChecked():
            gen_args.append("--sampling-topp 0.9 --temperature 1.2")
        gen_args_str = " ".join(gen_args)
        cmd = f'bash -c "echo {shlex.quote(self.selected_seed_mbid)} | ./generate.sh {gen_args_str} | python3 write_playlist.py {shlex.quote(save_path)} --mode {mode_str} --count {count}"'

        self.gen_worker = CommandWorker(cmd)
        self.gen_worker.line_read.connect(self.on_gen_log)
        self.gen_worker.finished_command.connect(self.on_gen_finished)
        self.gen_worker.start()

    def on_gen_log(self, line):
        self.view.gen_console.appendPlainText(line)

    def load_generated_playlist_to_queue(self, save_path):
        import glob
        paths_to_load = []
        if os.path.exists(save_path) and os.path.isfile(save_path):
            with open(save_path, "r") as f:
                paths_to_load = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            parent_dir = os.path.dirname(os.path.abspath(save_path))
            std_dir = os.path.join(parent_dir, "standard")
            if os.path.exists(std_dir):
                m3us = sorted(glob.glob(os.path.join(std_dir, "*.m3u")), key=os.path.getmtime, reverse=True)
                if m3us:
                    with open(m3us[0], "r") as f:
                        paths_to_load = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                        
        if paths_to_load:
            path_map = {s["path"]: s for s in self.model.songs_list}
            loaded_songs = []
            for p in paths_to_load:
                if p in path_map:
                    loaded_songs.append(path_map[p])
                else:
                    from gui.metadata_helper import extract_metadata_from_path
                    art, alb, tit = extract_metadata_from_path(p, "")
                    loaded_songs.append({
                        "mbid": "",
                        "path": p,
                        "artist": art or "Unknown Artist",
                        "album": alb or "Unknown Album",
                        "title": tit or os.path.basename(p),
                        "duration": 240.0
                    })
            self.queued_playlist_tracks = loaded_songs
            self.update_queue_ui()

    def on_gen_finished(self, exit_code):
        self.view.btn_generate.setEnabled(True)
        if exit_code == 0:
            save_path = self.model.get_config_value("playlist_save_path")
            self.load_generated_playlist_to_queue(save_path)
            self.view.lbl_generation_status.setText(
                f"AI Recommendations generated! Tracks populated into table below. Review and click 'Save Playlist' at the bottom when ready."
            )
            if self.view.content_stack.currentIndex() == 4:
                self.on_load_playlist()
        else:
            self.view.lbl_generation_status.setText(f"Playlist generation failed with code: {exit_code}")
            
        self.update_statuses()
        self.gen_worker = None

    def on_gen_mode_changed(self, text):
        if text in ("Full Library", "Half Library"):
            self.view.btn_generate.setEnabled(True)
            self.view.lbl_generation_status.setText("Library mode selected. Ready to generate.")
        elif text == "Single Artist":
            if getattr(self, "selected_seed_artist", None):
                title = getattr(self, "selected_seed_title", "")
                album = getattr(self, "selected_seed_album", "")
                self.view.lbl_selected_seed.setText(f"Target Artist: <b>{self.selected_seed_artist}</b><br><small>Seed Track: '{title}' ({album})</small>")
                self.view.btn_generate.setEnabled(True)
                self.view.lbl_generation_status.setText("Artist mode selected. Ready to generate.")
            else:
                self.view.btn_generate.setEnabled(False)
                self.view.lbl_generation_status.setText("Select a song to set target Artist.")
        elif text == "Recreate Album":
            if getattr(self, "selected_seed_album", None):
                title = getattr(self, "selected_seed_title", "")
                artist = getattr(self, "selected_seed_artist", "")
                self.view.lbl_selected_seed.setText(f"Target Album: <b>{self.selected_seed_album}</b> by <b>{artist}</b><br><small>Seed Track: '{title}'</small>")
                self.view.btn_generate.setEnabled(True)
                self.view.lbl_generation_status.setText("Album mode selected. Ready to generate.")
            else:
                self.view.btn_generate.setEnabled(False)
                self.view.lbl_generation_status.setText("Select a song to set target Album.")
        else:
            if getattr(self, "selected_seed_mbid", None):
                title = getattr(self, "selected_seed_title", "")
                artist = getattr(self, "selected_seed_artist", "")
                album = getattr(self, "selected_seed_album", "")
                mbid = getattr(self, "selected_seed_mbid", "")
                self.view.lbl_selected_seed.setText(f"Seed: <b>{title}</b> by <b>{artist}</b><br><small>Album: {album} | MBID: {mbid}</small>")
                self.view.btn_generate.setEnabled(True)
                self.view.lbl_generation_status.setText("Seed track selected. Ready to generate.")
            else:
                self.view.btn_generate.setEnabled(False)
                self.view.lbl_generation_status.setText("Select a seed song to enable playlist generation.")

    # ----------------------------------------------------
    # ListenBrainz History Download
    # ----------------------------------------------------
    def prompt_and_download_history(self):
        username, ok = QInputDialog.getText(
            self.view, 
            "Download ListenBrainz History", 
            "Please enter your ListenBrainz Username:"
        )
        if ok and username.strip():
            username = username.strip()
            
            # Save inside the folder where the playlist is saved
            save_path = self.model.get_config_value("playlist_save_path")
            out_dir = os.path.dirname(os.path.abspath(save_path)) if save_path else os.getcwd()
            dest_file = os.path.join(out_dir, "listenbrainz_history.json")
            
            # Switch view stack to AI tab so they see logs
            self.view.content_stack.setCurrentIndex(2)
            self.view.nav_buttons[2].setChecked(True)
            
            self.set_training_buttons_enabled(False)
            self.view.console_logs.clear()
            self.view.console_logs.appendPlainText(f">>> Querying ListenBrainz API for user '{username}'...")
            
            # Start timer
            import time
            self.active_task = "download"
            self.task_start_time = time.time()
            self.view.train_progress_card.setVisible(True)
            self.view.lbl_train_status.setText("Downloading history from ListenBrainz API...")
            self.view.lbl_train_time.setText("Elapsed: 00:00")
            self.view.train_progress.setRange(0, 0)
            self.ui_timer.start(1000)

            self.dl_worker = ListenBrainzDownloadWorker(username, dest_file)
            self.dl_worker.progress.connect(self.on_dl_progress)
            self.dl_worker.finished_download.connect(self.on_dl_finished)
            self.dl_worker.error_occurred.connect(self.on_dl_error)
            self.dl_worker.start()

    def on_dl_progress(self, message):
        self.view.console_logs.appendPlainText(message)

    def on_dl_finished(self, file_path):
        self.view.console_logs.appendPlainText(f"\n>>> ListenBrainz history download complete: {file_path}")
        self.model.set_config_value("listenbrainz_json", file_path)
        self.view.set_settings_inputs(self.model.config)
        self.set_training_buttons_enabled(True)
        
        # Stop timer
        self.active_task = None
        self.ui_timer.stop()
        self.view.train_progress_card.setVisible(False)

        self.update_statuses()
        self.dl_worker = None
        
        # Automatically run preprocessing on the newly downloaded file!
        self.on_run_preprocess()

    def on_dl_error(self, error_message):
        self.view.console_logs.appendPlainText(f"\n>>> Download error: {error_message}")
        QMessageBox.critical(
            self.view, 
            "Download Error", 
            f"Failed to download history from ListenBrainz: {error_message}"
        )
        self.set_training_buttons_enabled(True)
        
        # Stop timer
        self.active_task = None
        self.ui_timer.stop()
        self.view.train_progress_card.setVisible(False)

        self.dl_worker = None

    # ----------------------------------------------------
    # MusicBrainz Library Auto-Tagging
    # ----------------------------------------------------
    def on_start_autotag(self):
        music_dir = self.model.get_config_value("music_dir")
        save_path = self.model.get_config_value("playlist_save_path")
        if not music_dir or not os.path.exists(music_dir):
            QMessageBox.warning(
                self.view, 
                "Path Error", 
                "Please configure a valid Music Collection Directory under Settings first."
            )
            return

        self.view.btn_autotag.setEnabled(False)
        self.view.btn_scan.setEnabled(False)
        self.view.btn_stop_autotag.setEnabled(True)
        self.view.scan_progress.setValue(0)
        self.view.lbl_scan_status.setText("Initializing MusicBrainz query worker...")

        # Start timer
        import time
        self.active_task = "autotag"
        self.task_start_time = time.time()
        self.view.lbl_scan_time.setText("Elapsed: 00:00 | Remaining: --:--")
        self.ui_timer.start(1000)

        self.tag_worker = TagResolverWorker(music_dir, save_path)
        self.tag_worker.progress.connect(self.on_autotag_progress)
        self.tag_worker.error_occurred.connect(self.on_autotag_error)
        self.tag_worker.finished_resolving.connect(self.on_autotag_finished)
        self.tag_worker.start()

    def on_autotag_progress(self, current, total, text):
        self.view.scan_progress.setMaximum(total)
        self.view.scan_progress.setValue(current)
        self.view.lbl_scan_status.setText(text)

    def on_autotag_error(self, error_msg):
        self.view.lbl_scan_status.setText(f"Resolver error: {error_msg}")
        self.active_task = None
        self.ui_timer.stop()

    def on_autotag_finished(self, matched, failed):
        self.view.btn_autotag.setEnabled(True)
        self.view.btn_scan.setEnabled(True)
        self.view.btn_stop_autotag.setEnabled(False)
        
        # Stop timer
        self.active_task = None
        self.ui_timer.stop()
        
        summary = f"Library tag verification complete!\nResolved & tagged: {matched} tracks."
        if failed > 0:
            save_path = self.model.get_config_value("playlist_save_path")
            out_dir = os.path.dirname(os.path.abspath(save_path)) if save_path else os.getcwd()
            report_file = os.path.join(out_dir, "untagged_songs.txt")
            summary += f"\nFailed to resolve {failed} tracks. A report listing these files has been written to: {report_file}"
            
        QMessageBox.information(self.view, "Auto-Tagging Finished", summary)
        self.tag_worker = None
        
        # Trigger standard scan to refresh all views/tables
        self.on_start_scan()

    def on_stop_autotag(self):
        if self.tag_worker:
            self.tag_worker.stop()
            self.view.lbl_scan_status.setText("Auto-tagging cancellation requested...")

    # ----------------------------------------------------
    # Playlist Editor
    # ----------------------------------------------------
    def on_load_playlist(self):
        # Open file dialog to choose which playlist to edit, defaulting to the saved playlist path
        default_path = self.model.get_config_value("playlist_save_path")
        path = self.view.select_file("Select Playlist to Edit", "M3U Playlists (*.m3u)", default_path)
        if not path:
            return
            
        self.current_editing_playlist = path
        self.view.lbl_playlist_editing_status.setText(f"Editing: {os.path.basename(path)}")
        
        # Load the playlist tracks
        tracks = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            tracks.append(line)
            except Exception as e:
                QMessageBox.warning(self.view, "Load Error", f"Failed to read playlist file: {str(e)}")
                return
                
        # Populate view table
        song_map = {song["path"]: song for song in self.model.songs_list}
        
        self.view.table_playlist.setRowCount(0)
        for track_path in tracks:
            row = self.view.table_playlist.rowCount()
            self.view.table_playlist.insertRow(row)
            
            # Retrieve metadata from model
            song = song_map.get(track_path)
            if song:
                title = song["title"]
                artist = song["artist"]
                duration = self.format_time(song.get("duration", 240))
            else:
                title = os.path.basename(track_path)
                artist = "Unknown Artist"
                duration = "--:--"
                
            self.view.table_playlist.setItem(row, 0, QTableWidgetItem(title))
            self.view.table_playlist.setItem(row, 1, QTableWidgetItem(artist))
            self.view.table_playlist.setItem(row, 2, QTableWidgetItem(duration))
            self.view.table_playlist.setItem(row, 3, QTableWidgetItem(track_path))

    def on_save_playlist(self):
        if not getattr(self, "current_editing_playlist", None):
            QMessageBox.warning(self.view, "Save Error", "No playlist is currently loaded. Click 'Load/Refresh' first.")
            return
            
        path = self.current_editing_playlist
        tracks = []
        for row in range(self.view.table_playlist.rowCount()):
            item = self.view.table_playlist.item(row, 3) # Path column
            if item:
                tracks.append(item.text())
                
        try:
            with open(path, "w") as f:
                for track in tracks:
                    f.write(track + "\n")
            QMessageBox.information(self.view, "Success", f"Playlist changes saved successfully to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self.view, "Save Error", f"Failed to write changes: {str(e)}")

    # ----------------------------------------------------
    # CD Burning & WAV Conversion
    # ----------------------------------------------------
    def scan_drives(self):
        import glob
        drives = glob.glob("/dev/sr*")
        if not drives and os.path.exists("/dev/sr0"):
            drives = ["/dev/sr0"]
        self.view.update_drive_list(drives)

    def on_eject_drive(self, dev_path):
        import subprocess
        if not dev_path.startswith("/dev/sr"):
            return
        try:
            self.view.burn_console.appendPlainText(f">>> Ejecting tray for device: {dev_path}")
            subprocess.run(["eject", dev_path], check=True)
        except Exception as e:
            self.view.burn_console.appendPlainText(f">>> Eject failed: {str(e)}")

    def on_burn_browse_playlist(self):
        default_path = self.model.get_config_value("playlist_save_path")
        path = self.view.select_file("Select Playlist to Burn", "M3U Playlists (*.m3u)", default_path)
        if not path:
            return
            
        self.view.txt_burn_playlist_path.setText(path)
        self.load_burn_playlist(path)

    def load_burn_playlist(self, path):
        tracks = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            tracks.append(line)
            except Exception as e:
                QMessageBox.warning(self.view, "Load Error", f"Failed to read playlist file: {str(e)}")
                return
                
        song_map = {song["path"]: song for song in self.model.songs_list}
        
        self.playlist_tracks = []
        self.converted_tracks = []
        self.view.table_burn_tracks.setRowCount(0)
        
        total_duration = 0.0
        
        for idx, track_path in enumerate(tracks, 1):
            song = song_map.get(track_path)
            if song:
                title = song["title"]
                artist = song["artist"]
                duration_sec = song.get("duration", 240)
            else:
                title = os.path.basename(track_path)
                artist = "Unknown Artist"
                duration_sec = 240
                if os.path.exists(track_path):
                    try:
                        from mutagen import File
                        audio = File(track_path)
                        if audio and audio.info:
                            duration_sec = int(audio.info.length)
                    except Exception:
                        pass
                        
            total_duration += duration_sec
            
            row = self.view.table_burn_tracks.rowCount()
            self.view.table_burn_tracks.insertRow(row)
            self.view.table_burn_tracks.setItem(row, 0, QTableWidgetItem(str(idx)))
            self.view.table_burn_tracks.setItem(row, 1, QTableWidgetItem(title))
            self.view.table_burn_tracks.setItem(row, 2, QTableWidgetItem(artist))
            self.view.table_burn_tracks.setItem(row, 3, QTableWidgetItem(self.format_time(duration_sec)))
            self.view.table_burn_tracks.setItem(row, 4, QTableWidgetItem("Original"))
            
            self.playlist_tracks.append((idx, title, artist, track_path, duration_sec))
            
        self.update_burn_capacity_verification(total_duration)

    def on_cd_capacity_changed(self):
        total_duration = sum(t[4] for t in getattr(self, "playlist_tracks", []))
        self.update_burn_capacity_verification(total_duration)

    def update_burn_capacity_verification(self, total_duration):
        selected_text = self.view.combo_cd_capacity.currentText()
        if "74 Min" in selected_text:
            max_secs = 4440
            max_label = "74 Min (650MB)"
        else:
            max_secs = 4800
            max_label = "80 Min (700MB)"
            
        self.view.burn_capacity_progress.setRange(0, max_secs)
        self.view.burn_capacity_progress.setValue(min(int(total_duration), max_secs))
        
        minutes = int(total_duration) // 60
        seconds = int(total_duration) % 60
        
        summary_txt = (
            f"Total Tracks: {len(getattr(self, 'playlist_tracks', []))}\n"
            f"Total Duration: {minutes} mins {seconds} secs ({int(total_duration)}s)\n"
            f"CD Capacity Limit: {max_label}"
        )
        self.view.lbl_burn_summary.setText(summary_txt)
        
        if total_duration <= max_secs:
            self.view.lbl_burn_status.setText("Fits on CD")
            self.view.lbl_burn_status.setStyleSheet("font-weight: bold; color: #10b981; font-size: 14px;")
            self.view.burn_capacity_progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #334155;
                    background-color: #0f172a;
                    border-radius: 4px;
                    text-align: center;
                    color: #f8fafc;
                }
                QProgressBar::chunk {
                    background-color: #10b981;
                    border-radius: 3px;
                }
            """)
            self.view.btn_convert_wav.setEnabled(len(self.playlist_tracks) > 0)
        else:
            diff = int(total_duration) - max_secs
            self.view.lbl_burn_status.setText(f"Exceeds Capacity by {diff}s")
            self.view.lbl_burn_status.setStyleSheet("font-weight: bold; color: #ef4444; font-size: 14px;")
            self.view.burn_capacity_progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #334155;
                    background-color: #0f172a;
                    border-radius: 4px;
                    text-align: center;
                    color: #f8fafc;
                }
                QProgressBar::chunk {
                    background-color: #ef4444;
                    border-radius: 3px;
                }
            """)
            self.view.btn_convert_wav.setEnabled(False)
            self.view.btn_burn_cd.setEnabled(False)

    def on_run_convert_wav(self):
        if not getattr(self, "playlist_tracks", []):
            QMessageBox.warning(self.view, "Convert Error", "Please select a playlist with tracks first.")
            return
            
        self.view.burn_console.clear()
        self.view.burn_console.appendPlainText(">>> Starting WAV conversion for CD-DA audio CD format...")
        
        # Safely reset previous worker reference to let garbage collector clean it up
        self.wav_worker = None
        
        output_dir = os.path.abspath("temp_wav")
        import shutil
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except Exception:
                pass
        os.makedirs(output_dir, exist_ok=True)
        
        worker_tracks = [(t[0], t[1], t[2], t[3]) for t in self.playlist_tracks]
        
        self.view.btn_convert_wav.setEnabled(False)
        self.view.btn_burn_cd.setEnabled(False)
        self.view.btn_stop_burn.setEnabled(True)
        
        from gui.workers import WAVConverterWorker
        normalize = self.view.chk_burn_normalize.isChecked()
        num_workers = int(self.model.get_config_value("num_workers") or "1")
        self.wav_worker = WAVConverterWorker(worker_tracks, output_dir, normalize=normalize, num_workers=num_workers)
        self.wav_worker.progress.connect(self.on_wav_progress)
        self.wav_worker.line_read.connect(self.on_wav_line_read)
        self.wav_worker.finished_conversion.connect(self.on_wav_conversion_finished)
        self.wav_worker.start()

    def on_wav_progress(self, current, total, msg):
        self.view.lbl_burn_status.setText(f"Converting ({current}/{total}): {msg}")

    def on_wav_line_read(self, line):
        self.view.burn_console.appendPlainText(line)

    def on_wav_conversion_finished(self, results):
        self.view.btn_stop_burn.setEnabled(False)
        self.view.btn_convert_wav.setEnabled(True)
        
        self.converted_tracks = results
        
        failed_any = False
        total_duration = 0.0
        
        for idx, res in enumerate(results):
            row = idx
            status = res["status"]
            self.view.table_burn_tracks.setItem(row, 4, QTableWidgetItem(status))
            
            if status == "Converted":
                total_duration += res["duration"]
                size_mb = res["size"] / (1024 * 1024)
                self.view.table_burn_tracks.setItem(row, 3, QTableWidgetItem(f"{self.format_time(res['duration'])} ({size_mb:.1f} MB)"))
            else:
                failed_any = True
                self.view.table_burn_tracks.setItem(row, 3, QTableWidgetItem("--:--"))
                
        self.update_burn_capacity_verification(total_duration)
        
        if failed_any:
            QMessageBox.warning(self.view, "Conversion Complete", "Some tracks failed to convert to CD-DA format. Please check the logs.")
            self.view.btn_burn_cd.setEnabled(False)
        else:
            self.view.burn_console.appendPlainText(f"\n>>> All tracks successfully converted to CD-DA! Total actual WAV duration: {self.format_time(total_duration)}.")
            selected_text = self.view.combo_cd_capacity.currentText()
            max_secs = 4440 if "74 Min" in selected_text else 4800
            if total_duration <= max_secs:
                self.view.btn_burn_cd.setEnabled(True)

    def on_run_burn_single_drive(self, dev_path):
        self.on_run_burn_cd(override_drives=[dev_path])

    def on_run_burn_cd(self, override_drives=None):
        checked_drives = override_drives if override_drives is not None else self.view.get_target_drives()
        if not checked_drives:
            QMessageBox.warning(self.view, "Burn Error", "No target burn drive selected.")
            return
            
        if not getattr(self, "converted_tracks", []):
            QMessageBox.warning(self.view, "Burn Error", "Please convert your playlist to WAV files first.")
            return
            
        burn_playlist_path = os.path.abspath("burn_playlist.m3u")
        try:
            with open(burn_playlist_path, "w") as f:
                for res in self.converted_tracks:
                    if res["wav_path"]:
                        f.write(res["wav_path"] + "\n")
        except Exception as e:
            QMessageBox.critical(self.view, "Burn Error", f"Failed to generate burn playlist file: {str(e)}")
            return
            
        self.view.burn_console.clear()
        self.view.burn_console.appendPlainText(f">>> Spawning CD burn workers for drive(s): {', '.join(checked_drives)}")

        # Update per-drive status badges
        if hasattr(self.view, "drive_status_labels"):
            for dev_path in checked_drives:
                if dev_path in self.view.drive_status_labels:
                    self.view.drive_status_labels[dev_path].setText("Status: Burning...")
                    self.view.drive_status_labels[dev_path].setStyleSheet("color: #3b82f6; font-weight: bold;")
        
        self.view.btn_convert_wav.setEnabled(False)
        self.view.btn_burn_cd.setEnabled(False)
        self.view.btn_stop_burn.setEnabled(True)
        
        # Safely reset previous workers list to let garbage collector clean them up
        self.burn_workers = []
        self.active_burn_count = len(checked_drives)
        
        from gui.workers import CDBurnWorker
        simulate = self.view.chk_burn_simulate.isChecked()
        normalize = self.view.chk_burn_normalize.isChecked()
        overburn = self.view.chk_burn_overburn.isChecked()
        disc_format_text = self.view.combo_disc_format.currentText()
        burn_type = "data" if "Data CD" in disc_format_text else "audio"
        
        for idx, dev_path in enumerate(checked_drives):
            dev_tag = os.path.basename(dev_path)
            device_temp_dir = os.path.abspath(f"temp_burn_{dev_tag}")
            
            import shutil
            if os.path.exists(device_temp_dir):
                try:
                    shutil.rmtree(device_temp_dir)
                except Exception:
                    pass
            os.makedirs(device_temp_dir, exist_ok=True)
            
            speed = self.view.combo_burn_speed.currentText()
            worker = CDBurnWorker(
                device=dev_path,
                playlist_path=burn_playlist_path,
                temp_dir=device_temp_dir,
                simulate=simulate,
                normalize=normalize,
                speed=speed,
                overburn=overburn,
                burn_type=burn_type
            )
            worker.line_read.connect(self.on_burn_line_read)
            worker.finished_burn.connect(self.on_burn_finished)
            self.burn_workers.append(worker)
            worker.start()

    def on_burn_line_read(self, line, tag):
        self.view.burn_console.appendPlainText(line)
        if hasattr(self.view, "drive_consoles"):
            for dev_path, console in self.view.drive_consoles.items():
                if tag in dev_path or os.path.basename(dev_path) == tag:
                    console.appendPlainText(line)

    def on_burn_finished(self, device, exit_code):
        self.active_burn_count -= 1
        dev_tag = os.path.basename(device)
        self.view.burn_console.appendPlainText(f"\n>>> [{dev_tag}] Burning process finished with exit code: {exit_code}")
        
        if hasattr(self.view, "drive_consoles") and device in self.view.drive_consoles:
            self.view.drive_consoles[device].appendPlainText(f"\n>>> Burning finished with exit code: {exit_code}")
            
        if hasattr(self.view, "drive_status_labels") and device in self.view.drive_status_labels:
            if exit_code == 0:
                self.view.drive_status_labels[device].setText("Status: Completed")
                self.view.drive_status_labels[device].setStyleSheet("color: #10b981; font-weight: bold;")
            else:
                self.view.drive_status_labels[device].setText(f"Status: Failed ({exit_code})")
                self.view.drive_status_labels[device].setStyleSheet("color: #ef4444; font-weight: bold;")

        if self.active_burn_count <= 0:
            self.view.burn_console.appendPlainText("\n>>> All burning workers completed!")
            self.view.btn_convert_wav.setEnabled(True)
            self.view.btn_burn_cd.setEnabled(True)
            self.view.btn_stop_burn.setEnabled(False)
            
            burn_playlist_path = os.path.abspath("burn_playlist.m3u")
            if os.path.exists(burn_playlist_path):
                try:
                    os.remove(burn_playlist_path)
                except Exception:
                    pass

    def on_stop_burn(self):
        if getattr(self, "wav_worker", None):
            self.wav_worker.stop()
            self.view.burn_console.appendPlainText("\n>>> WAV conversion stop requested...")
            
        if getattr(self, "burn_workers", []):
            for worker in self.burn_workers:
                worker.stop()
            self.view.burn_console.appendPlainText("\n>>> CD burning cancellation requested...")

