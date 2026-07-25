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

# gui/view.py

import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QLabel, QStackedWidget, QLineEdit, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit, QFileDialog, QComboBox,
    QGridLayout, QAbstractItemView, QSizePolicy, QFormLayout,
    QSpinBox, QCheckBox, QTabWidget, QScrollArea
)
from PyQt6.QtGui import QFont, QColor

class TrainingGridWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lit_count = 0
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.rows = 50
        self.cols = 200
        
        self.order = []
        for r in range(self.rows):
            for c in range(self.cols):
                self.order.append((r, c))
        import random
        rng = random.Random(42)
        rng.shuffle(self.order)
        
        # Pre-map coordinates to their random activation index for fast O(1) lookup
        self.cell_indices = [[0]*self.cols for _ in range(self.rows)]
        for idx, (r, c) in enumerate(self.order):
            self.cell_indices[r][c] = idx
        
    def set_progress(self, value, maximum):
        if maximum > 0:
            ratio = value / maximum
        else:
            ratio = 0.0
        self.lit_count = int(max(0.0, min(1.0, ratio)) * (self.rows * self.cols))
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QBrush, QColor, QPen
        painter = QPainter(self)
        
        width = self.width()
        height = self.height()
        
        spacing = 1
        total_spacing_w = spacing * (self.cols + 1)
        total_spacing_h = spacing * (self.rows + 1)
        
        cell_width = (width - total_spacing_w) / self.cols
        cell_height = (height - total_spacing_h) / self.rows
        
        for r in range(self.rows):
            for c in range(self.cols):
                x = spacing + c * (cell_width + spacing)
                y = spacing + r * (cell_height + spacing)
                
                is_lit = self.cell_indices[r][c] < self.lit_count
                
                if is_lit:
                    color = QColor("#4f46e5")
                    border_color = QColor("#6366f1")
                else:
                    color = QColor("#1e293b")
                    border_color = QColor("#334155")
                
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(border_color, 0.5))
                painter.drawRect(int(x), int(y), int(cell_width), int(cell_height))

class MainWindow(QMainWindow):
    # Signals for Controller to listen to
    nav_changed = pyqtSignal(int)
    browse_music_clicked = pyqtSignal()
    browse_json_clicked = pyqtSignal()
    browse_playlist_clicked = pyqtSignal()
    save_settings_clicked = pyqtSignal()
    theme_changed = pyqtSignal(str)
    
    start_scan_clicked = pyqtSignal()
    stop_scan_clicked = pyqtSignal()
    autotag_clicked = pyqtSignal()
    stop_autotag_clicked = pyqtSignal()
    
    preprocess_clicked = pyqtSignal()
    train_clicked = pyqtSignal()
    stop_train_clicked = pyqtSignal()
    
    generate_clicked = pyqtSignal(str) # seed MBID
    load_playlist_clicked = pyqtSignal()
    save_playlist_clicked = pyqtSignal()
    
    burn_browse_playlist_clicked = pyqtSignal()
    run_convert_wav_clicked = pyqtSignal()
    run_burn_cd_clicked = pyqtSignal()
    run_burn_drive_clicked = pyqtSignal(str) # dev_path
    stop_burn_clicked = pyqtSignal()
    eject_drive_clicked = pyqtSignal(str)
    rescan_drives_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenPlaylister AI")
        self.setMinimumSize(950, 600)
        self.resize(1100, 750)
        self.init_ui()

    def init_ui(self):
        # Main Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Vertical layout for whole window: Top (Sidebar + Content) | Bottom (Footer)
        self.outer_layout = QVBoxLayout(self.central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)
        
        # Top widget containing the sidebar and content stack
        self.top_widget = QWidget()
        self.main_layout = QHBoxLayout(self.top_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. Sidebar Container
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(16, 24, 16, 24)
        self.sidebar_layout.setSpacing(8)
        
        # App Title in Sidebar
        self.app_title = QLabel("OpenPlaylister")
        self.app_title.setObjectName("title")
        self.app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(self.app_title)
        
        self.app_subtitle = QLabel("AI Playlist Generator")
        self.app_subtitle.setObjectName("subtitle")
        self.app_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(self.app_subtitle)
        
        self.sidebar_layout.addSpacing(24)
        
        # Navigation Buttons Group
        self.nav_buttons = []
        nav_items = [
            ("📊 Dashboard", 0),
            ("🎵 Music Scanner", 1),
            ("🧠 AI Model Training", 2),
            ("🪄 Playlist Generator", 3),
            ("💿 Burn CD", 4),
            ("📝 Edit Playlist", 5),
            ("⚙️ Settings", 6),
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked, idx=index: self.handle_nav(idx))
            self.sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            
        # Select first nav by default
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)
            
        self.sidebar_layout.addStretch()
        
        # Sidebar Status panel
        self.sidebar_status_frame = QFrame()
        self.sidebar_status_frame.setObjectName("card")
        self.status_layout = QVBoxLayout(self.sidebar_status_frame)
        self.status_layout.setContentsMargins(12, 12, 12, 12)
        
        self.status_title = QLabel("System Status")
        self.status_title.setStyleSheet("font-weight: bold; color: #94a3b8;")
        self.status_layout.addWidget(self.status_title)
        
        # System status labels
        self.lbl_status_fairseq = QLabel("fairseq: Checking...")
        self.lbl_status_index = QLabel("Music Index: Checking...")
        self.lbl_status_model = QLabel("AI Model: Checking...")
        
        self.status_layout.addWidget(self.lbl_status_fairseq)
        self.status_layout.addWidget(self.lbl_status_index)
        self.status_layout.addWidget(self.lbl_status_model)
        
        self.sidebar_layout.addWidget(self.sidebar_status_frame)
        
        self.main_layout.addWidget(self.sidebar)
        
        # 2. Main Stack
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("main_container")
        self.main_layout.addWidget(self.content_stack)
        
        self.outer_layout.addWidget(self.top_widget)
        
        # 3. Footer Container (GPLv3 & PyQt6 License Info)
        self.footer = QFrame()
        self.footer.setObjectName("footer")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(16, 6, 16, 6)
        self.footer_layout.setSpacing(12)
        
        self.footer_text = QLabel(
            "This software uses PyQt6 (licensed under GNU GPL v3 by Riverbank Computing). "
            "OpenPlaylister AI is licensed under the <a href='https://www.gnu.org/licenses/gpl-3.0.html' style='color: #6366f1; text-decoration: none;'>GNU GPL v3</a>. "
            "Portions copyright Paul Sajna under the <a href='https://opensource.org/licenses/MIT' style='color: #6366f1; text-decoration: none;'>MIT License</a>."
        )
        self.footer_text.setObjectName("footer_text")
        self.footer_text.setOpenExternalLinks(True)
        self.footer_layout.addWidget(self.footer_text)
        
        self.footer_layout.addStretch()
        
        self.btn_view_license = QPushButton("View License Text")
        self.btn_view_license.setObjectName("footer_btn")
        self.btn_view_license.clicked.connect(self.show_license_dialog)
        self.footer_layout.addWidget(self.btn_view_license)
        
        self.outer_layout.addWidget(self.footer)
        
        # Create Stack pages
        self.create_dashboard_page()
        self.create_scanner_page()
        self.create_training_page()
        self.create_generator_page()
        self.create_burn_cd_page()
        self.create_playlist_edit_page()
        self.create_settings_page()

    def handle_nav(self, index):
        self.content_stack.setCurrentIndex(index)
        self.nav_changed.emit(index)

    def add_page_to_stack(self, page):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.content_stack.addWidget(scroll)

    # ----------------------------------------------------
    # Page Creation Helpers
    # ----------------------------------------------------
    
    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # Title Section
        title_lbl = QLabel("Dashboard")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        # Cards Grid
        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        
        # Card 1: Music Library
        self.card_library = QFrame()
        self.card_library.setObjectName("card")
        card_lib_layout = QVBoxLayout(self.card_library)
        card_lib_layout.addWidget(QLabel("<b>Music Library Index</b>"))
        self.lbl_dash_lib_status = QLabel("Checking library index...")
        self.lbl_dash_lib_tag = QLabel("INACTIVE")
        self.lbl_dash_lib_tag.setObjectName("status_tag_inactive")
        self.lbl_dash_lib_tag.setFixedWidth(80)
        self.lbl_dash_lib_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lib_layout.addWidget(self.lbl_dash_lib_status)
        card_lib_layout.addWidget(self.lbl_dash_lib_tag)
        grid_layout.addWidget(self.card_library, 0, 0)
        
        # Card 2: Environment
        self.card_env = QFrame()
        self.card_env.setObjectName("card")
        card_env_layout = QVBoxLayout(self.card_env)
        card_env_layout.addWidget(QLabel("<b>System Dependencies</b>"))
        self.lbl_dash_env_status = QLabel("Checking fairseq...")
        self.lbl_dash_env_tag = QLabel("INACTIVE")
        self.lbl_dash_env_tag.setObjectName("status_tag_inactive")
        self.lbl_dash_env_tag.setFixedWidth(80)
        self.lbl_dash_env_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_env_layout.addWidget(self.lbl_dash_env_status)
        card_env_layout.addWidget(self.lbl_dash_env_tag)
        grid_layout.addWidget(self.card_env, 0, 1)
        
        # Card 3: ListenBrainz
        self.card_lb = QFrame()
        self.card_lb.setObjectName("card")
        card_lb_layout = QVBoxLayout(self.card_lb)
        card_lb_layout.addWidget(QLabel("<b>ListenBrainz Export</b>"))
        self.lbl_dash_lb_status = QLabel("Preprocess status unknown...")
        self.lbl_dash_lb_tag = QLabel("INACTIVE")
        self.lbl_dash_lb_tag.setObjectName("status_tag_inactive")
        self.lbl_dash_lb_tag.setFixedWidth(80)
        self.lbl_dash_lb_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lb_layout.addWidget(self.lbl_dash_lb_status)
        card_lb_layout.addWidget(self.lbl_dash_lb_tag)
        grid_layout.addWidget(self.card_lb, 1, 0)
        
        # Card 4: AI Model
        self.card_model = QFrame()
        self.card_model.setObjectName("card")
        card_model_layout = QVBoxLayout(self.card_model)
        card_model_layout.addWidget(QLabel("<b>Transformer AI Model</b>"))
        self.lbl_dash_model_status = QLabel("No trained checkpoint found...")
        self.lbl_dash_model_tag = QLabel("INACTIVE")
        self.lbl_dash_model_tag.setObjectName("status_tag_inactive")
        self.lbl_dash_model_tag.setFixedWidth(80)
        self.lbl_dash_model_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_model_layout.addWidget(self.lbl_dash_model_status)
        card_model_layout.addWidget(self.lbl_dash_model_tag)
        grid_layout.addWidget(self.card_model, 1, 1)
        
        layout.addLayout(grid_layout)
        
        # User Instructions
        info_frame = QFrame()
        info_frame.setObjectName("card")
        info_layout = QVBoxLayout(info_frame)
        info_layout.addWidget(QLabel("<h3>Getting Started Quick Guide</h3>"))
        info_text = QLabel(
            "1. <b>Configure paths</b> under Settings page (Music library directory, ListenBrainz JSON, and playlist save destination).<br>"
            "2. Go to <b>Music Scanner</b> and scan your library to record MusicBrainz ID tags and track durations.<br>"
            "3. Export history from <b>ListenBrainz</b> (or click download history in settings), click <b>Preprocess</b>, then <b>Train Model</b> in the training tab.<br>"
            "4. Go to <b>Playlist Generator</b>: Choose a Target Mode (Standard AI, CD Safe, Cassette Safe, or static Full/Half Library), set the count, and click <b>Generate Playlist</b>. Ported files are saved to `standard/`, `CDs/`, and `cassettes/` subfolders.<br>"
            "5. Go to <b>Edit Playlist</b> to load generated playlists, rearrange tracks via <b>drag and drop</b>, delete tracks, and save changes."
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_frame)
        
        layout.addStretch()
        self.add_page_to_stack(page)

    def create_scanner_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        title_lbl = QLabel("Music Library Scanner")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("Recursively scans the configured Music Collection folder for MP3/FLAC files containing MusicBrainz IDs (mbid).")
        desc_lbl.setObjectName("subtitle")
        layout.addWidget(desc_lbl)
        
        # Scanner Control Card
        control_card = QFrame()
        control_card.setObjectName("card")
        cc_layout = QVBoxLayout(control_card)
        
        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Start Library Scan")
        self.btn_scan.setObjectName("primary_btn")
        self.btn_scan.clicked.connect(self.start_scan_clicked.emit)
        btn_layout.addWidget(self.btn_scan)
        
        self.btn_stop_scan = QPushButton("Stop Scan")
        self.btn_stop_scan.setObjectName("danger_btn")
        self.btn_stop_scan.setEnabled(False)
        self.btn_stop_scan.clicked.connect(self.stop_scan_clicked.emit)
        btn_layout.addWidget(self.btn_stop_scan)
        
        self.btn_autotag = QPushButton("Verify & Auto-Tag Library")
        self.btn_autotag.clicked.connect(self.autotag_clicked.emit)
        btn_layout.addWidget(self.btn_autotag)
        
        self.btn_stop_autotag = QPushButton("Stop Tagging")
        self.btn_stop_autotag.setObjectName("danger_btn")
        self.btn_stop_autotag.setEnabled(False)
        self.btn_stop_autotag.clicked.connect(self.stop_autotag_clicked.emit)
        btn_layout.addWidget(self.btn_stop_autotag)
        
        cc_layout.addLayout(btn_layout)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setValue(0)
        cc_layout.addWidget(self.scan_progress)
        
        # Aligned layout for status on left and elapsed/remaining time on right
        time_status_layout = QHBoxLayout()
        self.lbl_scan_status = QLabel("Idle - Scan not started.")
        time_status_layout.addWidget(self.lbl_scan_status)
        
        time_status_layout.addStretch()
        
        self.lbl_scan_time = QLabel("")
        self.lbl_scan_time.setObjectName("subtitle")
        time_status_layout.addWidget(self.lbl_scan_time)
        
        cc_layout.addLayout(time_status_layout)
        layout.addWidget(control_card)
        
        # Scanned Song List View
        table_label = QLabel("<b>Scanned Indexed Tracks</b>")
        layout.addWidget(table_label)
        
        # Search filter
        self.txt_scan_search = QLineEdit()
        self.txt_scan_search.setPlaceholderText("🔍 Filter scanned songs by title, artist, or filename...")
        layout.addWidget(self.txt_scan_search)
        
        self.table_songs = QTableWidget()
        self.table_songs.setColumnCount(4)
        self.table_songs.setHorizontalHeaderLabels(["Title", "Artist", "MusicBrainz ID", "Path"])
        self.table_songs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_songs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.table_songs.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table_songs.setColumnWidth(2, 250)
        self.table_songs.setColumnWidth(3, 200)
        
        layout.addWidget(self.table_songs)
        
        self.add_page_to_stack(page)

    def create_training_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        title_lbl = QLabel("AI Model Preprocessing & Training")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("Preprocess the ListenBrainz JSON export, split files, and train a Transformer model.")
        desc_lbl.setObjectName("subtitle")
        layout.addWidget(desc_lbl)
        
        # Action layout
        btn_card = QFrame()
        btn_card.setObjectName("card")
        bc_layout = QHBoxLayout(btn_card)
        
        self.btn_preprocess = QPushButton("⚙️ Preprocess History")
        self.btn_preprocess.setObjectName("primary_btn")
        self.btn_preprocess.clicked.connect(self.preprocess_clicked.emit)
        bc_layout.addWidget(self.btn_preprocess)
        
        self.btn_train = QPushButton("🚀 Train Model")
        self.btn_train.setObjectName("primary_btn")
        self.btn_train.clicked.connect(self.train_clicked.emit)
        bc_layout.addWidget(self.btn_train)
        
        self.btn_stop_train = QPushButton("🛑 Stop Training")
        self.btn_stop_train.setObjectName("danger_btn")
        self.btn_stop_train.setEnabled(False)
        self.btn_stop_train.clicked.connect(self.stop_train_clicked.emit)
        bc_layout.addWidget(self.btn_stop_train)
        
        layout.addWidget(btn_card)
        
        # Progress Card for Preprocessing / Training
        self.train_progress_card = QFrame()
        self.train_progress_card.setObjectName("card")
        self.train_progress_card.setVisible(False)
        tpc_layout = QVBoxLayout(self.train_progress_card)
        
        t_status_layout = QHBoxLayout()
        self.lbl_train_status = QLabel("Idle")
        t_status_layout.addWidget(self.lbl_train_status)
        
        t_status_layout.addStretch()
        
        self.lbl_train_time = QLabel("")
        self.lbl_train_time.setObjectName("subtitle")
        t_status_layout.addWidget(self.lbl_train_time)
        
        tpc_layout.addLayout(t_status_layout)
        
        self.train_progress = QProgressBar()
        self.train_progress.setValue(0)
        self.train_progress.valueChanged.connect(self.on_train_progress_changed)
        tpc_layout.addWidget(self.train_progress)
        
        # Neural grid progress widget
        self.grid_progress = TrainingGridWidget()
        self.grid_progress.setVisible(False)
        tpc_layout.addWidget(self.grid_progress)
        
        layout.addWidget(self.train_progress_card)
        
        # Training Console Logs
        self.console_lbl = QLabel("<b>Execution Console Logs</b>")
        layout.addWidget(self.console_lbl)
        
        self.console_logs = QPlainTextEdit()
        self.console_logs.setReadOnly(True)
        self.console_logs.setPlaceholderText("Console logs will stream here during execution...")
        layout.addWidget(self.console_logs)
        
        # Retrain from scratch checkbox
        self.chk_retrain = QCheckBox("Retrain from scratch (clears checkpoints)")
        self.chk_retrain.setStyleSheet("margin-top: 6px; margin-bottom: 6px;")
        layout.addWidget(self.chk_retrain)
        
        # Action buttons
        log_btn_layout = QHBoxLayout()
        self.btn_clear_logs = QPushButton("Clear Console Logs")
        self.btn_clear_logs.clicked.connect(self.console_logs.clear)
        self.btn_clear_logs.setFixedWidth(150)
        log_btn_layout.addWidget(self.btn_clear_logs)
        
        self.btn_toggle_logs = QPushButton("Hide Console Log")
        self.btn_toggle_logs.clicked.connect(self.on_toggle_console_log)
        self.btn_toggle_logs.setFixedWidth(150)
        log_btn_layout.addWidget(self.btn_toggle_logs)
        log_btn_layout.addStretch()
        layout.addLayout(log_btn_layout)
        
        self.add_page_to_stack(page)

    def create_generator_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        title_lbl = QLabel("Playlist Generator")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("Choose a seed track, run AI inference, and write the custom playlist.")
        desc_lbl.setObjectName("subtitle")
        layout.addWidget(desc_lbl)
        
        # Split Generator: Left (Seed Selection) | Right (Inference Run)
        splits_layout = QHBoxLayout()
        splits_layout.setSpacing(16)
        
        # Left Panel - Seed Selector
        left_frame = QFrame()
        left_frame.setObjectName("card")
        left_layout = QVBoxLayout(left_frame)
        left_layout.addWidget(QLabel("<b>1. Select Seed Track</b>"))
        
        self.txt_seed_search = QLineEdit()
        self.txt_seed_search.setPlaceholderText("Search songs for seed track...")
        left_layout.addWidget(self.txt_seed_search)
        
        self.table_seed_songs = QTableWidget()
        self.table_seed_songs.setColumnCount(4)
        self.table_seed_songs.setHorizontalHeaderLabels(["Title", "Artist", "Album", "MusicBrainz ID"])
        self.table_seed_songs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_seed_songs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_seed_songs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        s_header = self.table_seed_songs.horizontalHeader()
        s_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        s_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        s_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        s_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table_seed_songs.setColumnWidth(3, 180)
        
        left_layout.addWidget(self.table_seed_songs)

        # Action Buttons to append selected items directly to playlist builder
        queue_btns_layout = QHBoxLayout()
        self.btn_add_album = QPushButton("+ Add Album")
        self.btn_add_artist = QPushButton("+ Add Artist")
        self.btn_add_track = QPushButton("+ Add Track")
        queue_btns_layout.addWidget(self.btn_add_album)
        queue_btns_layout.addWidget(self.btn_add_artist)
        queue_btns_layout.addWidget(self.btn_add_track)
        left_layout.addLayout(queue_btns_layout)

        splits_layout.addWidget(left_frame, 3)
        
        # Right Panel - Step 2 (Generator & Builder) and Step 3 (Save Playlist)
        right_frame = QFrame()
        right_frame.setObjectName("card")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setSpacing(12)
        
        right_layout.addWidget(QLabel("<b>2. Generate & Populate Playlist</b>"))
        
        # Selected Seed Display
        self.lbl_selected_seed = QLabel("No Seed Track Selected")
        self.lbl_selected_seed.setWordWrap(True)
        self.lbl_selected_seed.setStyleSheet("font-size: 13px; font-weight: bold; padding: 8px; background-color: rgba(99, 102, 241, 0.1); border-radius: 6px;")
        right_layout.addWidget(self.lbl_selected_seed)
        
        # Mode execution options
        opts_layout = QFormLayout()
        opts_layout.setSpacing(6)
        
        self.combo_gen_mode = QComboBox()
        self.combo_gen_mode.addItems([
            "Standard AI Playlist",
            "Single Artist",
            "Recreate Album",
            "CD Safe (80 Minutes)",
            "Cassette C60 (30 Mins / Side)",
            "Cassette C90 (45 Mins / Side)",
            "Full Library",
            "Half Library"
        ])
        opts_layout.addRow(QLabel("Target Mode:"), self.combo_gen_mode)
        
        self.spin_playlist_count = QSpinBox()
        self.spin_playlist_count.setRange(1, 20)
        self.spin_playlist_count.setValue(1)
        opts_layout.addRow(QLabel("Playlists to Create:"), self.spin_playlist_count)
        
        right_layout.addLayout(opts_layout)

        self.chk_randomize = QCheckBox("Randomize recommendations (unique playlists)")
        self.chk_randomize.setStyleSheet("margin-top: 2px; margin-bottom: 2px;")
        right_layout.addWidget(self.chk_randomize)

        # Generate / Populate Action Button
        self.btn_generate = QPushButton("⚡ Generate Playlist Tracks")
        self.btn_generate.setEnabled(False)
        right_layout.addWidget(self.btn_generate)

        # Album Completeness & Disc Capacity Meter Card
        capacity_card = QFrame()
        capacity_card.setStyleSheet("background-color: rgba(15, 23, 42, 0.6); border: 1px solid #334155; border-radius: 6px; padding: 8px;")
        cap_layout = QVBoxLayout(capacity_card)
        cap_layout.setSpacing(4)

        self.lbl_album_info = QLabel("Album Availability: Select a track to check album completeness.")
        self.lbl_album_info.setWordWrap(True)
        self.lbl_album_info.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        cap_layout.addWidget(self.lbl_album_info)

        self.lbl_disc_capacity = QLabel("CD Capacity: 0m 0s / 80:00 (80m 0s remaining - 0% full)")
        self.lbl_disc_capacity.setStyleSheet("font-size: 12px; font-weight: bold; color: #818cf8;")
        cap_layout.addWidget(self.lbl_disc_capacity)

        self.progress_disc_capacity = QProgressBar()
        self.progress_disc_capacity.setRange(0, 4800) # 80 min CD limit in seconds
        self.progress_disc_capacity.setValue(0)
        self.progress_disc_capacity.setFormat("%v / %m secs")
        self.progress_disc_capacity.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 4px;
                text-align: center;
                height: 18px;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 3px;
            }
        """)
        cap_layout.addWidget(self.progress_disc_capacity)
        right_layout.addWidget(capacity_card)

        # Playlist Tracks Table
        right_layout.addWidget(QLabel("<b>Playlist Tracks Table</b>"))
        self.table_playlist_queue = QTableWidget()
        self.table_playlist_queue.setColumnCount(5)
        self.table_playlist_queue.setHorizontalHeaderLabels(["#", "Title", "Artist", "Album", "Duration"])
        self.table_playlist_queue.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_playlist_queue.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_playlist_queue.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_playlist_queue.setMaximumHeight(150)
        
        q_header = self.table_playlist_queue.horizontalHeader()
        q_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        q_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        q_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        q_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        q_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        right_layout.addWidget(self.table_playlist_queue)

        # Table management buttons
        tbl_btn_layout = QHBoxLayout()
        self.btn_remove_queued = QPushButton("❌ Remove Track")
        self.btn_clear_queue = QPushButton("🗑️ Clear List")
        tbl_btn_layout.addWidget(self.btn_remove_queued)
        tbl_btn_layout.addWidget(self.btn_clear_queue)
        right_layout.addLayout(tbl_btn_layout)

        right_layout.addSpacing(8)
        
        # Step 3 - Save Playlist Section
        right_layout.addWidget(QLabel("<b>3. Save Playlist</b>"))
        self.btn_generate_queued = QPushButton("💾 Save Playlist")
        self.btn_generate_queued.setObjectName("primary_btn")
        right_layout.addWidget(self.btn_generate_queued)

        self.lbl_generation_status = QLabel("Select a seed song and click 'Generate Playlist Tracks' or add items to populate the list.")
        self.lbl_generation_status.setWordWrap(True)
        right_layout.addWidget(self.lbl_generation_status)
        
        # Output Log
        right_layout.addWidget(QLabel("<b>Console Log</b>"))
        self.gen_console = QPlainTextEdit()
        self.gen_console.setReadOnly(True)
        self.gen_console.setMaximumHeight(90)
        right_layout.addWidget(self.gen_console)
        
        splits_layout.addWidget(right_frame, 3)
        
        layout.addLayout(splits_layout)
        self.add_page_to_stack(page)

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        
        title_lbl = QLabel("Application Settings")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        # Settings Card
        settings_card = QFrame()
        settings_card.setObjectName("card")
        sc_layout = QVBoxLayout(settings_card)
        sc_layout.setContentsMargins(24, 24, 24, 24)
        sc_layout.setSpacing(16)
        
        form_layout = QGridLayout()
        form_layout.setSpacing(12)
        
        # Row 1: Music Collection Source
        form_layout.addWidget(QLabel("Music Collection Directory:"), 0, 0)
        self.txt_music_dir = QLineEdit()
        form_layout.addWidget(self.txt_music_dir, 0, 1)
        self.btn_browse_music = QPushButton("Browse...")
        self.btn_browse_music.clicked.connect(self.browse_music_clicked.emit)
        form_layout.addWidget(self.btn_browse_music, 0, 2)
        
        # Row 2: ListenBrainz Export JSON
        form_layout.addWidget(QLabel("ListenBrainz History JSON:"), 1, 0)
        self.txt_json_path = QLineEdit()
        form_layout.addWidget(self.txt_json_path, 1, 1)
        self.btn_browse_json = QPushButton("Browse...")
        self.btn_browse_json.clicked.connect(self.browse_json_clicked.emit)
        form_layout.addWidget(self.btn_browse_json, 1, 2)
        
        # Row 3: Playlist Save Location
        form_layout.addWidget(QLabel("Playlist Output Root Folder:"), 2, 0)
        self.txt_playlist_path = QLineEdit()
        form_layout.addWidget(self.txt_playlist_path, 2, 1)
        self.btn_browse_playlist = QPushButton("Browse...")
        self.btn_browse_playlist.clicked.connect(self.browse_playlist_clicked.emit)
        form_layout.addWidget(self.btn_browse_playlist, 2, 2)
        
        # Row 4: Theme Selector
        form_layout.addWidget(QLabel("Application Theme:"), 3, 0)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        self.combo_theme.currentTextChanged.connect(self.theme_changed.emit)
        form_layout.addWidget(self.combo_theme, 3, 1, 1, 2)
        
        # Row 5: Distributed GPUs (World Size)
        form_layout.addWidget(QLabel("Distributed GPUs (World Size):"), 4, 0)
        self.combo_gpus = QComboBox()
        
        # Populate based on actual available GPUs
        available_gpus = 0
        try:
            import torch
            if torch.cuda.is_available():
                available_gpus = torch.cuda.device_count()
        except Exception:
            pass
            
        if available_gpus > 0:
            gpu_options = [str(i) for i in range(1, available_gpus + 1)]
            self.combo_gpus.addItems(gpu_options)
            self.combo_gpus.setEnabled(True)
        else:
            self.combo_gpus.addItems(["1"])
            self.combo_gpus.setEnabled(False)
            self.combo_gpus.setToolTip("No CUDA-capable GPUs detected. Defaulting to single-device / CPU.")
        form_layout.addWidget(self.combo_gpus, 4, 1, 1, 2)
        
        # Row 6: Dataset CPU Workers
        form_layout.addWidget(QLabel("Dataset CPU Workers:"), 5, 0)
        self.combo_workers = QComboBox()
        self.combo_workers.addItems(["1", "2", "4", "8", "12", "16", "20", "24"])
        form_layout.addWidget(self.combo_workers, 5, 1, 1, 2)
        
        # Row 7: AI Training Cycle Level
        form_layout.addWidget(QLabel("AI Training Cycle Level:"), 6, 0)
        self.combo_train_level = QComboBox()
        self.combo_train_level.addItems([
            "Minimal (5,000 cycles)",
            "Light (15,000 cycles)",
            "Standard (30,000 cycles)",
            "Thorough (50,000 cycles)",
            "Deep (100,000 cycles)"
        ])
        form_layout.addWidget(self.combo_train_level, 6, 1, 1, 2)
        
        sc_layout.addLayout(form_layout)
        
        # Save Action Button
        self.btn_save_settings = QPushButton("Save Config Settings")
        self.btn_save_settings.setObjectName("primary_btn")
        self.btn_save_settings.clicked.connect(self.save_settings_clicked.emit)
        sc_layout.addWidget(self.btn_save_settings)
        
        layout.addWidget(settings_card)
        layout.addStretch()
        self.add_page_to_stack(page)

    def on_toggle_console_log(self):
        show_console = not self.console_logs.isVisible()
        
        self.console_logs.setVisible(show_console)
        self.console_lbl.setVisible(show_console)
        
        # Standard progress bar shows when console is shown, hides when console is hidden
        self.train_progress.setVisible(show_console)
        # Dynamic grid progress shows when console is hidden, hides when console is shown
        self.grid_progress.setVisible(not show_console)
        
        if show_console:
            self.btn_toggle_logs.setText("Hide Console Log")
        else:
            self.btn_toggle_logs.setText("Show Console Log")

    def on_train_progress_changed(self, value):
        self.grid_progress.set_progress(value, self.train_progress.maximum())

    def create_playlist_edit_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        title_lbl = QLabel("Edit Playlist")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("View and modify the tracks in your generated playlist. Move tracks using the buttons or by dragging them directly, or delete them.")
        desc_lbl.setObjectName("subtitle")
        layout.addWidget(desc_lbl)
        
        self.lbl_playlist_editing_status = QLabel("No Playlist Loaded. Click 'Load/Refresh' to choose a file.")
        self.lbl_playlist_editing_status.setStyleSheet("font-style: italic; color: #9ca3af;")
        layout.addWidget(self.lbl_playlist_editing_status)
        
        # Table of playlist songs
        self.table_playlist = QTableWidget()
        self.table_playlist.setColumnCount(4)
        self.table_playlist.setHorizontalHeaderLabels(["Title", "Artist", "Duration", "File Path"])
        self.table_playlist.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_playlist.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_playlist.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Enable Drag and Drop reordering
        self.table_playlist.setDragEnabled(True)
        self.table_playlist.setAcceptDrops(True)
        self.table_playlist.setDragDropOverwriteMode(False)
        self.table_playlist.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table_playlist.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        header = self.table_playlist.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.table_playlist)
        
        # Action controls layout
        btn_layout = QHBoxLayout()
        self.btn_load_playlist = QPushButton("🔄 Load/Refresh Playlist")
        self.btn_load_playlist.clicked.connect(self.load_playlist_clicked.emit)
        btn_layout.addWidget(self.btn_load_playlist)
        
        self.btn_move_up = QPushButton("⬆️ Move Up")
        self.btn_move_up.clicked.connect(self.move_playlist_song_up)
        btn_layout.addWidget(self.btn_move_up)
        
        self.btn_move_down = QPushButton("⬇️ Move Down")
        self.btn_move_down.clicked.connect(self.move_playlist_song_down)
        btn_layout.addWidget(self.btn_move_down)
        
        self.btn_delete_song = QPushButton("❌ Delete Song")
        self.btn_delete_song.clicked.connect(self.delete_playlist_song)
        btn_layout.addWidget(self.btn_delete_song)
        
        self.btn_save_playlist = QPushButton("💾 Save Changes")
        self.btn_save_playlist.setObjectName("primary_btn")
        self.btn_save_playlist.clicked.connect(self.save_playlist_clicked.emit)
        btn_layout.addWidget(self.btn_save_playlist)
        
        layout.addLayout(btn_layout)
        
        self.add_page_to_stack(page)

    def create_burn_cd_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        
        # Title
        title_lbl = QLabel("CD Burning & WAV Conversion")
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)
        
        # Horizontal Split: Left (Tracks List) | Right (Settings & verification)
        splits_layout = QHBoxLayout()
        splits_layout.setSpacing(20)
        
        # Left Panel (Playlist Tracks Table)
        left_frame = QFrame()
        left_frame.setObjectName("card")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(16, 16, 16, 16)
        
        pl_row = QHBoxLayout()
        pl_row.addWidget(QLabel("<b>Selected Playlist:</b>"))
        self.txt_burn_playlist_path = QLineEdit()
        self.txt_burn_playlist_path.setReadOnly(True)
        pl_row.addWidget(self.txt_burn_playlist_path)
        self.btn_burn_browse_playlist = QPushButton("Browse...")
        self.btn_burn_browse_playlist.clicked.connect(self.burn_browse_playlist_clicked.emit)
        pl_row.addWidget(self.btn_burn_browse_playlist)
        left_layout.addLayout(pl_row)
        
        # Tracks Table
        self.table_burn_tracks = QTableWidget()
        self.table_burn_tracks.setColumnCount(5)
        self.table_burn_tracks.setHorizontalHeaderLabels(["#", "Title", "Artist", "Duration", "Status"])
        self.table_burn_tracks.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_burn_tracks.horizontalHeader().setStretchLastSection(True)
        self.table_burn_tracks.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_burn_tracks.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        left_layout.addWidget(self.table_burn_tracks)
        
        splits_layout.addWidget(left_frame, 3)
        
        # Right Panel (Settings & Verification)
        right_frame = QFrame()
        right_frame.setObjectName("card")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)
        
        right_layout.addWidget(QLabel("<b>Secondary verification:</b>"))
        
        self.lbl_burn_summary = QLabel("Total Tracks: 0\nTotal Duration: 0 mins\nStatus: Empty Playlist")
        self.lbl_burn_summary.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.4;")
        right_layout.addWidget(self.lbl_burn_summary)
        
        # CD Capacity Progress bar/meter
        self.burn_capacity_progress = QProgressBar()
        self.burn_capacity_progress.setRange(0, 4800) # 80 min default
        self.burn_capacity_progress.setValue(0)
        self.burn_capacity_progress.setFormat("%v / %m secs")
        self.burn_capacity_progress.setStyleSheet("""
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
        right_layout.addWidget(self.burn_capacity_progress)
        
        self.lbl_burn_status = QLabel("Ready")
        self.lbl_burn_status.setObjectName("status_ready")
        self.lbl_burn_status.setStyleSheet("font-weight: bold; color: #10b981; font-size: 14px;")
        right_layout.addWidget(self.lbl_burn_status)
        
        # Burn configuration form (3 high x 2 wide grid layout)
        grid_opts = QGridLayout()
        grid_opts.setSpacing(10)
        grid_opts.setContentsMargins(0, 4, 0, 8)
        
        # 1. Target CD Capacity
        self.combo_cd_capacity = QComboBox()
        self.combo_cd_capacity.addItem("80 Min (700MB)")
        self.combo_cd_capacity.setItemData(0, "80 Min (700MB) / 4800 seconds max capacity", Qt.ItemDataRole.ToolTipRole)
        self.combo_cd_capacity.addItem("74 Min (650MB)")
        self.combo_cd_capacity.setItemData(1, "74 Min (650MB) / 4440 seconds max capacity", Qt.ItemDataRole.ToolTipRole)
        
        cap_layout = QHBoxLayout()
        cap_layout.addWidget(QLabel("Target Capacity:"))
        cap_layout.addWidget(self.combo_cd_capacity, 1)
        grid_opts.addLayout(cap_layout, 0, 0)
        
        # 2. Disc Format Mode
        self.combo_disc_format = QComboBox()
        self.combo_disc_format.addItem("Audio CD (CD-DA + CD-Text)")
        self.combo_disc_format.setItemData(0, "Audio CD (CD-DA + CD-Text for standalone CD players & car stereos)", Qt.ItemDataRole.ToolTipRole)
        self.combo_disc_format.addItem("Data CD / ISO (ISO9660)")
        self.combo_disc_format.setItemData(1, "Data CD / ISO (ISO9660 + Tagged WAV Files for Rhythmbox & PC players)", Qt.ItemDataRole.ToolTipRole)
        self.combo_disc_format.setToolTip("Audio CD: for standard CD players/car stereos.\nData CD: for Rhythmbox, VLC & computer file readers.")
        
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Disc Format:"))
        fmt_layout.addWidget(self.combo_disc_format, 1)
        grid_opts.addLayout(fmt_layout, 0, 1)
        
        # 3. Burn Speed
        self.combo_burn_speed = QComboBox()
        self.combo_burn_speed.addItems(["Auto", "4x", "8x", "16x", "24x", "32x", "48x"])
        spd_layout = QHBoxLayout()
        spd_layout.addWidget(QLabel("Burn Speed:"))
        spd_layout.addWidget(self.combo_burn_speed, 1)
        grid_opts.addLayout(spd_layout, 1, 0)
        
        # 4. Normalize Audio
        self.chk_burn_normalize = QCheckBox("Normalize Audio Volumes")
        self.chk_burn_normalize.setChecked(True)
        grid_opts.addWidget(self.chk_burn_normalize, 1, 1)
        
        # 5. Simulation Mode
        self.chk_burn_simulate = QCheckBox("Simulation Mode (Test Burn)")
        grid_opts.addWidget(self.chk_burn_simulate, 2, 0)
        
        # 6. Allow Overburn
        self.chk_burn_overburn = QCheckBox("Allow Overburn (over capacity)")
        grid_opts.addWidget(self.chk_burn_overburn, 2, 1)
        
        right_layout.addLayout(grid_opts)
        
        # Batch Mode Checkbox (below grid)
        self.chk_burn_all_drives = QCheckBox("Burn playlist to all drives (Batch Mode)")
        self.chk_burn_all_drives.setToolTip("When checked, clicking Burn CD burns to ALL connected drives in parallel. When unchecked, burning targets the active tab only.")
        right_layout.addWidget(self.chk_burn_all_drives)
        
        # Drive Section Header with Rescan Button
        drives_hdr = QHBoxLayout()
        drives_hdr.addWidget(QLabel("<b>Target Burn Drive Tabs:</b>"))
        drives_hdr.addStretch()
        self.btn_rescan_drives = QPushButton("🔄 Rescan / Find Drives")
        self.btn_rescan_drives.setToolTip("Scan system for USB or IDE/SATA optical drives")
        self.btn_rescan_drives.clicked.connect(self.rescan_drives_clicked.emit)
        drives_hdr.addWidget(self.btn_rescan_drives)
        right_layout.addLayout(drives_hdr)
        
        # QTabWidget for Optical CD Drives
        self.tab_drives = QTabWidget()
        right_layout.addWidget(self.tab_drives)
        
        splits_layout.addWidget(right_frame, 2)
        layout.addLayout(splits_layout)
        
        # Execution Console
        layout.addWidget(QLabel("<b>Conversion & Burning Log Output</b>"))
        self.burn_console = QPlainTextEdit()
        self.burn_console.setReadOnly(True)
        self.burn_console.setMaximumHeight(130)
        self.burn_console.setPlaceholderText("Status messages and tool output will stream here...")
        layout.addWidget(self.burn_console)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.btn_convert_wav = QPushButton("⚡ Convert Playlist to WAV")
        self.btn_convert_wav.setObjectName("primary_btn")
        self.btn_convert_wav.clicked.connect(self.run_convert_wav_clicked.emit)
        btn_layout.addWidget(self.btn_convert_wav)
        
        self.btn_burn_cd = QPushButton("💿 Burn CD")
        self.btn_burn_cd.setObjectName("primary_btn")
        self.btn_burn_cd.setEnabled(False)
        self.btn_burn_cd.clicked.connect(self.run_burn_cd_clicked.emit)
        btn_layout.addWidget(self.btn_burn_cd)
        
        self.btn_stop_burn = QPushButton("🛑 Stop")
        self.btn_stop_burn.setObjectName("danger_btn")
        self.btn_stop_burn.setEnabled(False)
        self.btn_stop_burn.clicked.connect(self.stop_burn_clicked.emit)
        btn_layout.addWidget(self.btn_stop_burn)
        
        layout.addLayout(btn_layout)
        self.add_page_to_stack(page)

    def update_drive_list(self, drives):
        self.tab_drives.clear()
        self.detected_drives = list(drives) if drives else []
        self.drive_consoles = {}
        self.drive_status_labels = {}
        
        if not drives:
            no_drives_page = QWidget()
            nd_layout = QVBoxLayout(no_drives_page)
            lbl = QLabel("No optical drives detected.\nPlug in your USB CD drive and click '🔄 Rescan / Find Drives'.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-style: italic; padding: 20px;")
            nd_layout.addWidget(lbl)
            self.tab_drives.addTab(no_drives_page, "No Drives Found")
            return

        for dev_path in drives:
            dev_tag = os.path.basename(dev_path)
            tab_page = QWidget()
            tab_layout = QVBoxLayout(tab_page)
            tab_layout.setContentsMargins(12, 12, 12, 12)
            tab_layout.setSpacing(8)
            
            hdr_row = QHBoxLayout()
            dev_info = QLabel(f"<b>Device:</b> <code>{dev_path}</code>")
            hdr_row.addWidget(dev_info)
            
            status_lbl = QLabel("Status: Idle")
            status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
            self.drive_status_labels[dev_path] = status_lbl
            hdr_row.addWidget(status_lbl)
            hdr_row.addStretch()
            
            eject_btn = QPushButton("Pop Tray")
            eject_btn.setFixedSize(80, 24)
            eject_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    color: #f1f5f9;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #475569;
                }
            """)
            eject_btn.clicked.connect(lambda checked, path=dev_path: self.eject_drive_clicked.emit(path))
            hdr_row.addWidget(eject_btn)
            tab_layout.addLayout(hdr_row)
            
            # Individual Drive Burn Action Row
            act_row = QHBoxLayout()
            btn_burn_this = QPushButton(f"💿 Burn to {dev_tag}")
            btn_burn_this.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    border-radius: 4px;
                    padding: 4px 12px;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            btn_burn_this.clicked.connect(lambda checked, path=dev_path: self.run_burn_drive_clicked.emit(path))
            act_row.addWidget(btn_burn_this)
            act_row.addStretch()
            tab_layout.addLayout(act_row)
            
            # Drive-specific log console
            drive_console = QPlainTextEdit()
            drive_console.setReadOnly(True)
            drive_console.setPlaceholderText(f"Burn logging for {dev_path} will stream here...")
            drive_console.setMaximumHeight(160)
            tab_layout.addWidget(drive_console)
            self.drive_consoles[dev_path] = drive_console
            
            self.tab_drives.addTab(tab_page, f"📀 {dev_tag}")

    def get_target_drives(self):
        if not getattr(self, "detected_drives", []):
            return []
            
        if self.chk_burn_all_drives.isChecked():
            return list(self.detected_drives)
        else:
            idx = self.tab_drives.currentIndex()
            if 0 <= idx < len(self.detected_drives):
                return [self.detected_drives[idx]]
            return [self.detected_drives[0]]

    def get_checked_drives(self):
        return self.get_target_drives()

    def move_playlist_song_up(self):
        row = self.table_playlist.currentRow()
        if row > 0:
            self.swap_playlist_rows(row, row - 1)
            self.table_playlist.setCurrentCell(row - 1, 0)
            
    def move_playlist_song_down(self):
        row = self.table_playlist.currentRow()
        if row >= 0 and row < self.table_playlist.rowCount() - 1:
            self.swap_playlist_rows(row, row + 1)
            self.table_playlist.setCurrentCell(row + 1, 0)
            
    def swap_playlist_rows(self, r1, r2):
        for col in range(self.table_playlist.columnCount()):
            item1 = self.table_playlist.takeItem(r1, col)
            item2 = self.table_playlist.takeItem(r2, col)
            self.table_playlist.setItem(r1, col, item2)
            self.table_playlist.setItem(r2, col, item1)
            
    def delete_playlist_song(self):
        row = self.table_playlist.currentRow()
        if row >= 0:
            self.table_playlist.removeRow(row)

    # ----------------------------------------------------
    # Dialogs and UI Getters/Setters
    # ----------------------------------------------------
    def select_directory(self, title, initial_dir=""):
        path = QFileDialog.getExistingDirectory(self, title, initial_dir)
        return path

    def select_file(self, title, filter_str, initial_dir=""):
        path, _ = QFileDialog.getOpenFileName(self, title, initial_dir, filter_str)
        return path

    def save_file_dialog(self, title, filter_str, initial_file=""):
        path, _ = QFileDialog.getSaveFileName(self, title, initial_file, filter_str)
        return path

    def get_settings_inputs(self):
        level_map = {
            "Minimal (5,000 cycles)": 5000,
            "Light (15,000 cycles)": 15000,
            "Standard (30,000 cycles)": 30000,
            "Thorough (50,000 cycles)": 50000,
            "Deep (100,000 cycles)": 100000
        }
        selected_level = self.combo_train_level.currentText()
        train_level_val = level_map.get(selected_level, 30000)
        
        return {
            "music_dir": self.txt_music_dir.text().strip(),
            "listenbrainz_json": self.txt_json_path.text().strip(),
            "playlist_save_path": self.txt_playlist_path.text().strip(),
            "theme": self.combo_theme.currentText(),
            "num_workers": self.combo_workers.currentText(),
            "num_gpus": self.combo_gpus.currentText(),
            "train_level": train_level_val
        }

    def set_settings_inputs(self, config_dict):
        self.txt_music_dir.setText(config_dict.get("music_dir", ""))
        self.txt_json_path.setText(config_dict.get("listenbrainz_json", ""))
        self.txt_playlist_path.setText(config_dict.get("playlist_save_path", ""))
        self.combo_theme.setCurrentText(config_dict.get("theme", "dark"))
        self.combo_workers.setCurrentText(str(config_dict.get("num_workers", "1")))
        
        # Select target GPU count or clamp to available maximum
        saved_gpus = str(config_dict.get("num_gpus", "1"))
        index = self.combo_gpus.findText(saved_gpus)
        if index >= 0:
            self.combo_gpus.setCurrentIndex(index)
        else:
            self.combo_gpus.setCurrentIndex(self.combo_gpus.count() - 1)
            
        val_map = {
            5000: "Minimal (5,000 cycles)",
            15000: "Light (15,000 cycles)",
            30000: "Standard (30,000 cycles)",
            50000: "Thorough (50,000 cycles)",
            100000: "Deep (100,000 cycles)"
        }
        saved_level = config_dict.get("train_level", 30000)
        self.combo_train_level.setCurrentText(val_map.get(saved_level, "Standard (30,000 cycles)"))

    def update_sidebar_status(self, fairseq_ok, index_ok, model_ok, index_count):
        # fairseq
        if fairseq_ok:
            self.lbl_status_fairseq.setText("fairseq: Available")
            self.lbl_status_fairseq.setStyleSheet("color: #34d399;")
        else:
            self.lbl_status_fairseq.setText("fairseq: MISSING")
            self.lbl_status_fairseq.setStyleSheet("color: #f87171;")

        # index
        if index_ok:
            self.lbl_status_index.setText(f"Indexed Songs: {index_count}")
            self.lbl_status_index.setStyleSheet("color: #34d399;")
        else:
            self.lbl_status_index.setText("Indexed Songs: 0")
            self.lbl_status_index.setStyleSheet("color: #f87171;")

        # model
        if model_ok:
            self.lbl_status_model.setText("AI Model: Trained")
            self.lbl_status_model.setStyleSheet("color: #34d399;")
        else:
            self.lbl_status_model.setText("AI Model: Not Trained")
            self.lbl_status_model.setStyleSheet("color: #f87171;")

    def update_dashboard(self, status):
        # Card 1: Music Library
        if status["music_index_ok"]:
            self.lbl_dash_lib_status.setText(f"Indexed Songs found: <b>{status['index_count']}</b>")
            self.lbl_dash_lib_tag.setText("ACTIVE")
            self.lbl_dash_lib_tag.setObjectName("status_tag_active")
        else:
            self.lbl_dash_lib_status.setText("No local music library indexed. Scan library to build index.")
            self.lbl_dash_lib_tag.setText("INACTIVE")
            self.lbl_dash_lib_tag.setObjectName("status_tag_inactive")

        # Card 2: Environment
        if status["fairseq_ok"]:
            self.lbl_dash_env_status.setText("Command-line dependency <b>fairseq</b> is available in PATH.")
            self.lbl_dash_env_tag.setText("ACTIVE")
            self.lbl_dash_env_tag.setObjectName("status_tag_active")
        else:
            self.lbl_dash_env_status.setText("<b>fairseq-train</b>/<b>fairseq-preprocess</b> not found in PATH.")
            self.lbl_dash_env_tag.setText("INACTIVE")
            self.lbl_dash_env_tag.setObjectName("status_tag_inactive")

        # Card 3: ListenBrainz
        if status["preprocess_ok"]:
            self.lbl_dash_lb_status.setText("ListenBrainz export preprocessed and binaries generated.")
            self.lbl_dash_lb_tag.setText("ACTIVE")
            self.lbl_dash_lb_tag.setObjectName("status_tag_active")
        else:
            self.lbl_dash_lb_status.setText("ListenBrainz JSON needs to be preprocessed to train model.")
            self.lbl_dash_lb_tag.setText("INACTIVE")
            self.lbl_dash_lb_tag.setObjectName("status_tag_inactive")

        # Card 4: Model Checkpoints
        if status["model_trained_ok"]:
            self.lbl_dash_model_status.setText("Model trained. Ready for sequence generation.")
            self.lbl_dash_model_tag.setText("ACTIVE")
            self.lbl_dash_model_tag.setObjectName("status_tag_active")
        else:
            self.lbl_dash_model_status.setText("No checkpoints/checkpoint_last.pt found. Run training.")
            self.lbl_dash_model_tag.setText("INACTIVE")
            self.lbl_dash_model_tag.setObjectName("status_tag_inactive")

        # Refresh styling for tag labels so color classes map correctly
        self.lbl_dash_lib_tag.style().unpolish(self.lbl_dash_lib_tag)
        self.lbl_dash_lib_tag.style().polish(self.lbl_dash_lib_tag)
        self.lbl_dash_env_tag.style().unpolish(self.lbl_dash_env_tag)
        self.lbl_dash_env_tag.style().polish(self.lbl_dash_env_tag)
        self.lbl_dash_lb_tag.style().unpolish(self.lbl_dash_lb_tag)
        self.lbl_dash_lb_tag.style().polish(self.lbl_dash_lb_tag)
        self.lbl_dash_model_tag.style().unpolish(self.lbl_dash_model_tag)
        self.lbl_dash_model_tag.style().polish(self.lbl_dash_model_tag)

    def show_license_dialog(self):
        from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout, QDialogButtonBox, QTabWidget
        dialog = QDialog(self)
        dialog.setWindowTitle("Software Licenses")
        dialog.resize(700, 550)
        
        layout = QVBoxLayout(dialog)
        
        tab_widget = QTabWidget()
        
        # Tab 1: GPLv3
        gpl_view = QTextEdit()
        gpl_view.setReadOnly(True)
        try:
            with open("LICENSE", "r", encoding="utf-8") as f:
                gpl_text = f.read()
            gpl_view.setPlainText(gpl_text)
        except Exception as e:
            gpl_view.setPlainText(f"Could not load LICENSE file: {str(e)}\n\nPlease see https://www.gnu.org/licenses/gpl-3.0.txt")
        tab_widget.addTab(gpl_view, "GNU GPL v3")
        
        # Tab 2: MIT
        mit_view = QTextEdit()
        mit_view.setReadOnly(True)
        try:
            with open("LICENSE.MIT", "r", encoding="utf-8") as f:
                mit_text = f.read()
            mit_view.setPlainText(mit_text)
        except Exception as e:
            mit_view.setPlainText(f"Could not load LICENSE.MIT file: {str(e)}")
        tab_widget.addTab(mit_view, "MIT License")
        
        layout.addWidget(tab_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        
        dialog.exec()

