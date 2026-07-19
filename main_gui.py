#!/usr/bin/env python3
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

# main_gui.py

import sys
import os

def check_dependencies():
    missing = []
    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")
    try:
        import mutagen
    except ImportError:
        missing.append("mutagen")
    
    if missing:
        print(f"Error: Missing required Python dependencies: {', '.join(missing)}")
        print("Please install them in your virtual environment by running:")
        print("pip install PyQt6 mutagen")
        sys.exit(1)

# Check dependencies before loading any PyQt components
check_dependencies()

import traceback

def global_exception_handler(exctype, value, tb):
    # Log the full exception traceback
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    
    # Print to stderr for parent process wrapper to record
    print(err_msg, file=sys.stderr)
    
    # Append traceback to error.log
    try:
        with open("error.log", "a") as f:
            f.write("==================================================\n")
            f.write("             UNHANDLED APPLICATION EXCEPTION      \n")
            f.write("==================================================\n")
            f.write(err_msg)
            f.write("\n")
    except Exception:
        pass
        
    # Open visual QMessageBox alert window using PyQt6
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
        app = QApplication.instance()
        if app:
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Application Runtime Exception")
            box.setText("An unexpected runtime exception has occurred.")
            box.setInformativeText(
                f"Exception Class: {exctype.__name__}\n"
                f"Details have been recorded in 'error.log'."
            )
            box.setDetailedText(err_msg)
            box.exec()
    except Exception:
        pass

# Wire the global exception handler
sys.excepthook = global_exception_handler


from PyQt6.QtWidgets import QApplication
from gui.model import OpenPlaylisterModel
from gui.view import MainWindow
from gui.controller import OpenPlaylisterController

def main():
    # Allow Qt to scale properly on high DPI screens
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName("OpenPlaylister AI")
    app.setApplicationDisplayName("OpenPlaylister AI Playlist Generator")
    
    # Initialize MVC
    model = OpenPlaylisterModel()
    view = MainWindow()
    controller = OpenPlaylisterController(model, view)
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
