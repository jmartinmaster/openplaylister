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

# gui/metadata_helper.py

import os
import re

def extract_metadata_from_path(file_path, music_dir):
    """
    Extracts artist, title, and album from the folder structure and filename
    if tags are missing. Handles different organizational systems (e.g., Artist/Album/File).
    """
    try:
        rel_path = os.path.relpath(file_path, music_dir)
    except ValueError:
        rel_path = os.path.basename(file_path)
        
    parts = rel_path.split(os.sep)
    filename = parts[-1]
    filename_no_ext = os.path.splitext(filename)[0]
    
    # Strip leading track numbers and punctuation/spaces from the entire filename
    # matches e.g. "01 - ", "01. ", "01 " but NOT "7hour" (digit not followed by separator)
    def clean_track_prefix(text):
        text = text.strip()
        match = re.match(r"^(\d+)(?:\s|\.|\-|_)+", text)
        if match:
            return text[match.end():].strip()
        return text

    cleaned_filename = clean_track_prefix(filename_no_ext)
    
    artist = ""
    title = ""
    
    # Split cleaned filename on separator " - "
    file_parts = cleaned_filename.split(" - ")
    
    if len(parts) >= 3:
        # Structure matches: Artist/Album/Filename (e.g., AJR/OK ORCHESTRA/11 AJR - World's Smallest Violin.mp3)
        artist_folder = parts[-3].strip()
        
        if len(file_parts) >= 2:
            left = file_parts[0].strip()
            right = " - ".join(file_parts[1:]).strip()
            
            # Check if left side is equal to artist folder
            if left.lower() == artist_folder.lower():
                artist = left
                title = right
            else:
                artist = artist_folder
                title = cleaned_filename
        else:
            artist = artist_folder
            title = cleaned_filename
            
    elif len(parts) == 2:
        # Structure matches: Artist/Filename
        artist_folder = parts[-2].strip()
        
        if len(file_parts) >= 2:
            left = file_parts[0].strip()
            right = " - ".join(file_parts[1:]).strip()
            if left.lower() == artist_folder.lower():
                artist = left
                title = right
            else:
                artist = artist_folder
                title = cleaned_filename
        else:
            artist = artist_folder
            title = cleaned_filename
            
    else:
        # Structure: Flat folder containing all songs
        if len(file_parts) >= 2:
            artist = file_parts[0].strip()
            title = " - ".join(file_parts[1:]).strip()
        else:
            title = cleaned_filename
            
    return artist.strip(), title.strip()

