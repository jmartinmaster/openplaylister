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
            self.view.table_seed_songs.setItem(row_seed, 2, QTableWidgetItem(song["mbid"]))

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
        current_file = self.model.get_config_value("playlist_save_path")
        path = self.view.save_file_dialog("Save Playlist File", "M3U Playlist (*.m3u)", current_file)
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
        self.view.table_seed_songs.setItem(row_seed, 2, QTableWidgetItem(song["mbid"]))

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
        self.view.console_logs.appendPlainText(">>> Executing: preprocess.sh " + json_path)
        
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

        cmd = f"./preprocess.sh {json_path}"
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

        self.view.console_logs.clear()
        
        # Build command with parallel training arguments
        num_workers = self.model.get_config_value("num_workers") or "1"
        num_gpus = self.model.get_config_value("num_gpus") or "1"
        
        train_args = []
        if int(num_workers) > 1:
            train_args.append(f"--num-workers {num_workers}")
        if int(num_gpus) > 1:
            train_args.append(f"--distributed-world-size {num_gpus}")
            train_args.append(f"--nprocs-per-node {num_gpus}")
            
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
        self.view.lbl_train_status.setText("Training AI model (Updates: 0 / 50000)...")
        self.view.lbl_train_time.setText("Elapsed: 00:00 | Remaining: Estimating...")
        self.view.train_progress.setRange(0, 50000)
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
                self.view.lbl_train_status.setText(f"Training AI model (Updates: {current_update} / 50000)...")
                
                import time
                if self.train_start_update is None:
                    self.train_start_update = current_update
                    self.train_start_update_time = time.time()
                elif current_update - self.train_start_update >= 10:
                    elapsed_since_start = time.time() - self.train_start_update_time
                    updates_since_start = current_update - self.train_start_update
                    if elapsed_since_start > 0 and updates_since_start > 0:
                        rate = updates_since_start / elapsed_since_start
                        remaining = (50000 - current_update) / rate
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
            return
            
        row = selected_ranges[0].topRow()
        title = self.view.table_seed_songs.item(row, 0).text()
        artist = self.view.table_seed_songs.item(row, 1).text()
        mbid = self.view.table_seed_songs.item(row, 2).text()
        
        self.selected_seed_mbid = mbid
        self.view.lbl_selected_seed.setText(f"Seed: <b>{title}</b> by <b>{artist}</b><br><small>MBID: {mbid}</small>")
        self.view.btn_generate.setEnabled(True)

    def on_generate_playlist(self):
        save_path = self.model.get_config_value("playlist_save_path")
        if not save_path:
            QMessageBox.warning(self.view, "Path Error", "Please configure a valid Playlist Save Path under Settings.")
            return

        mode_map = {
            "Standard AI Playlist": "standard",
            "CD Safe (80 Minutes)": "cd",
            "Cassette C60 (30 Mins / Side)": "c60",
            "Cassette C90 (45 Mins / Side)": "c90",
            "Full Library": "full",
            "Half Library": "half"
        }
        mode_str = mode_map.get(self.view.combo_gen_mode.currentText(), "standard")
        count = self.view.spin_playlist_count.value()

        self.view.gen_console.clear()
        self.view.btn_generate.setEnabled(False)

        if mode_str in ("full", "half"):
            self.view.gen_console.appendPlainText(f">>> Processing {mode_str} library playlist...")
            self.view.lbl_generation_status.setText("Compiling library tracks...")
            cmd = f"python3 write_playlist.py {save_path} --mode {mode_str}"
        else:
            if not getattr(self, "selected_seed_mbid", None):
                QMessageBox.warning(self.view, "Seed Error", "Please select a seed track for AI generation first.")
                self.view.btn_generate.setEnabled(True)
                return
            self.view.gen_console.appendPlainText(f">>> Seed mbid: {self.selected_seed_mbid}")
            self.view.gen_console.appendPlainText(">>> Executing sequence inference pipeline...")
            self.view.lbl_generation_status.setText("Generating playlist customized by AI recommendations...")
            
            gen_args = []
            if self.view.chk_randomize.isChecked():
                gen_args.append("--sampling-topp 0.9 --temperature 1.2")
            gen_args_str = " ".join(gen_args)
            cmd = f'bash -c "echo {self.selected_seed_mbid} | ./generate.sh {gen_args_str} | python3 write_playlist.py {save_path} --mode {mode_str} --count {count}"'

        self.gen_worker = CommandWorker(cmd)
        self.gen_worker.line_read.connect(self.on_gen_log)
        self.gen_worker.finished_command.connect(self.on_gen_finished)
        self.gen_worker.start()

    def on_gen_log(self, line):
        self.view.gen_console.appendPlainText(line)

    def on_gen_finished(self, exit_code):
        self.view.btn_generate.setEnabled(True)
        if exit_code == 0:
            save_path = self.model.get_config_value("playlist_save_path")
            parent_dir = os.path.dirname(os.path.abspath(save_path))
            
            mode_map = {
                "Standard AI Playlist": "standard",
                "CD Safe (80 Minutes)": "cd",
                "Cassette C60 (30 Mins / Side)": "c60",
                "Cassette C90 (45 Mins / Side)": "c90",
                "Full Library": "full",
                "Half Library": "half"
            }
            mode_str = mode_map.get(self.view.combo_gen_mode.currentText(), "standard")
            
            if mode_str == "cd":
                target_folder = os.path.join(parent_dir, "CDs")
                self.view.lbl_generation_status.setText(f"CD-Safe Playlists successfully generated in:<br><b>{target_folder}</b>")
            elif mode_str in ("c60", "c90"):
                target_folder = os.path.join(parent_dir, "cassettes")
                self.view.lbl_generation_status.setText(f"Cassette-Safe Playlists successfully generated in:<br><b>{target_folder}</b>")
            else:
                target_folder = os.path.join(parent_dir, "standard")
                self.view.lbl_generation_status.setText(f"Playlist successfully generated at:<br><b>{save_path}</b><br>and copy saved in:<br><b>{target_folder}</b>")
            
            # Automatically refresh the playlist if they are on the edit page
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
        else:
            if getattr(self, "selected_seed_mbid", None):
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

