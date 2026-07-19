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

# gui/styles.py

DARK_THEME = """
QMainWindow {
    background-color: #0f172a;
}

/* Base Widget Styling */
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
}

/* Sidebar and Containers */
QFrame#sidebar {
    background-color: #1e293b;
    border-right: 1px solid #334155;
}

QFrame#main_container {
    background-color: #0f172a;
}

QFrame#card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
}

/* Buttons */
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}

QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

QPushButton#primary_btn {
    background-color: #4f46e5;
    border-color: #6366f1;
    color: #ffffff;
}

QPushButton#primary_btn:hover {
    background-color: #4338ca;
}

QPushButton#primary_btn:pressed {
    background-color: #3730a3;
}

QPushButton#danger_btn {
    background-color: #ef4444;
    border-color: #f87171;
    color: #ffffff;
}

QPushButton#danger_btn:hover {
    background-color: #dc2626;
}

QPushButton#danger_btn:pressed {
    background-color: #b91c1c;
}

/* Nav / Sidebar buttons */
QPushButton#nav_btn {
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 10px 16px;
    border-radius: 8px;
    color: #94a3b8;
}

QPushButton#nav_btn:hover {
    background-color: #334155;
    color: #f8fafc;
}

QPushButton#nav_btn:checked {
    background-color: #4f46e5;
    color: #ffffff;
    font-weight: 600;
}

/* Text & Inputs */
QLineEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
}

QLineEdit:focus {
    border: 1px solid #6366f1;
}

QTextEdit, QPlainTextEdit {
    background-color: #0b0f19;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 8px;
    color: #38bdf8;
    font-family: "Fira Code", "Courier New", monospace;
}

QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f8fafc;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 1px;
    border-left-color: #334155;
    border-left-style: solid;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
}

/* Lists and Tables */
QListWidget, QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px;
}

QListWidget::item, QTableWidget::item {
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:hover, QTableWidget::item:hover {
    background-color: #334155;
}

QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #4f46e5;
    color: #ffffff;
}

/* Header for Table */
QHeaderView::section {
    background-color: #334155;
    color: #f8fafc;
    padding: 6px;
    border: none;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #334155;
    background-color: #1e293b;
    border-radius: 8px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
    border-radius: 7px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background-color: #0f172a;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #475569;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #64748b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #0f172a;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #475569;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #64748b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Headings */
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#subtitle {
    font-size: 14px;
    color: #94a3b8;
}

QLabel#status_tag_active {
    background-color: #065f46;
    color: #34d399;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11px;
}

QLabel#status_tag_inactive {
    background-color: #7f1d1d;
    color: #f87171;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11px;
}

/* Footer Styling */
QFrame#footer {
    background-color: #1e293b;
    border-top: 1px solid #334155;
}

QLabel#footer_text {
    color: #94a3b8;
    font-size: 11px;
}

QPushButton#footer_btn {
    font-size: 11px;
    padding: 4px 8px;
    background-color: #334155;
    border-color: #475569;
}

QPushButton#footer_btn:hover {
    background-color: #475569;
}

/* Tabs Styling */
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1e293b;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #4f46e5;
    color: #ffffff;
    border-color: #4f46e5;
}
QTabBar::tab:hover:!selected {
    background-color: #334155;
    color: #f8fafc;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #f8fafc;
}

/* Base Widget Styling */
QWidget {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
}

/* Sidebar and Containers */
QFrame#sidebar {
    background-color: #f1f5f9;
    border-right: 1px solid #cbd5e1;
}

QFrame#main_container {
    background-color: #f8fafc;
}

QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

/* Buttons */
QPushButton {
    background-color: #e2e8f0;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #cbd5e1;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#primary_btn {
    background-color: #4f46e5;
    border-color: #4338ca;
    color: #ffffff;
}

QPushButton#primary_btn:hover {
    background-color: #4338ca;
}

QPushButton#primary_btn:pressed {
    background-color: #3730a3;
}

QPushButton#danger_btn {
    background-color: #ef4444;
    border-color: #dc2626;
    color: #ffffff;
}

QPushButton#danger_btn:hover {
    background-color: #dc2626;
}

QPushButton#danger_btn:pressed {
    background-color: #b91c1c;
}

/* Nav / Sidebar buttons */
QPushButton#nav_btn {
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 10px 16px;
    border-radius: 8px;
    color: #64748b;
}

QPushButton#nav_btn:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}

QPushButton#nav_btn:checked {
    background-color: #4f46e5;
    color: #ffffff;
    font-weight: 600;
}

/* Text & Inputs */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    color: #0f172a;
}

QLineEdit:focus {
    border: 1px solid #4f46e5;
}

QTextEdit, QPlainTextEdit {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px;
    color: #1e3a8a;
    font-family: "Fira Code", "Courier New", monospace;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 12px;
    color: #0f172a;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 1px;
    border-left-color: #cbd5e1;
    border-left-style: solid;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
}

/* Lists and Tables */
QListWidget, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 4px;
}

QListWidget::item, QTableWidget::item {
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:hover, QTableWidget::item:hover {
    background-color: #f1f5f9;
}

QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #4f46e5;
    color: #ffffff;
}

/* Header for Table */
QHeaderView::section {
    background-color: #e2e8f0;
    color: #0f172a;
    padding: 6px;
    border: none;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #cbd5e1;
    background-color: #e2e8f0;
    border-radius: 8px;
    text-align: center;
    color: #0f172a;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
    border-radius: 7px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background-color: #f8fafc;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #f8fafc;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Headings */
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #0f172a;
}

QLabel#subtitle {
    font-size: 14px;
    color: #64748b;
}

QLabel#status_tag_active {
    background-color: #d1fae5;
    color: #065f46;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11px;
}

QLabel#status_tag_inactive {
    background-color: #fee2e2;
    color: #7f1d1d;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11px;
}

/* Footer Styling */
QFrame#footer {
    background-color: #f1f5f9;
    border-top: 1px solid #cbd5e1;
}

QLabel#footer_text {
    color: #64748b;
    font-size: 11px;
}

QPushButton#footer_btn {
    font-size: 11px;
    padding: 4px 8px;
    background-color: #e2e8f0;
    border-color: #cbd5e1;
}

QPushButton#footer_btn:hover {
    background-color: #cbd5e1;
}

/* Tabs Styling */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #f1f5f9;
    color: #64748b;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #4f46e5;
    color: #ffffff;
    border-color: #4f46e5;
}
QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
    color: #0f172a;
}
"""

