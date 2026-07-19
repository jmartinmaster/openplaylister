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

# run_gui.py

import sys
import subprocess
import os
import traceback

def main():
    # Command to run the main GUI under the same Python interpreter
    cmd = [sys.executable, "main_gui.py"]
    
    # Enable unbuffered python outputs for accurate log captures
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    try:
        # Run GUI as a child process, pipe stderr so we can inspect and report crash logs
        # Let stdout flow to the terminal for regular print statements
        result = subprocess.run(
            cmd,
            stdout=None,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        if result.returncode != 0:
            handle_crash(result.stderr, result.returncode)
    except Exception as e:
        handle_crash(traceback.format_exc(), -1)

def handle_crash(error_text, exit_code):
    # Prepare crash log
    log_content = (
        "==================================================\n"
        "           OPENPLAYLISTER CRASH LOG               \n"
        "==================================================\n"
        f"Exit Code: {exit_code}\n"
        "--------------------------------------------------\n"
        f"Traceback / Error Output:\n{error_text}\n"
    )
    
    # Attempt to write to crash.log
    try:
        with open("crash.log", "w") as f:
            f.write(log_content)
    except Exception as e:
        print(f"Failed to write crash.log: {str(e)}", file=sys.stderr)
    
    # Print to stderr terminal output
    print(log_content, file=sys.stderr)
    
    # Open visual QMessageBox alert window using PyQt6
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("OpenPlaylister Crash Warning")
        box.setText("The application closed unexpectedly.")
        box.setInformativeText(
            f"OpenPlaylister GUI exited with error code {exit_code}.\n"
            "Diagnostic details have been saved to 'crash.log' in the project directory."
        )
        box.setDetailedText(error_text)
        box.exec()
    except Exception as qt_err:
        print(f"Unable to show QMessageBox crash dialog: {str(qt_err)}", file=sys.stderr)

if __name__ == "__main__":
    main()
