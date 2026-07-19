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

# gui/scanner_cli.py

import os
import sys
import glob
import json
import mutagen

# Ensure we can import other gui modules when running as a standalone script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from gui.metadata_helper import extract_metadata_from_path

def print_json(data):
    """Utility to print JSON line with flush to ensure parent processes receive it immediately."""
    print(json.dumps(data), flush=True)

def scan_music(music_dir):
    if not music_dir or not os.path.exists(music_dir):
        print_json({"type": "error", "message": f"Specified directory does not exist: '{music_dir}'"})
        sys.exit(1)

    # Resolve MP3 and FLAC files recursively
    mp3_pattern = os.path.join(music_dir, "**", "*.mp3")
    flac_pattern = os.path.join(music_dir, "**", "*.flac")

    mp3_files = glob.glob(mp3_pattern, recursive=True)
    flac_files = glob.glob(flac_pattern, recursive=True)
    all_files = mp3_files + flac_files
    total_files = len(all_files)

    if total_files == 0:
        print_json({"type": "progress", "current": 0, "total": 0, "file": "No files found"})
        print_json({"type": "error", "message": "No MP3 or FLAC files found in the specified directory."})
        
        # Ensure we write empty indices to prevent startup issues
        with open("file_index.json", "w") as f:
            f.write("{}")
        with open("gui_index.json", "w") as f:
            f.write("[]")
        sys.exit(0)

    id_to_file = {}
    gui_songs = []

    for i, file_path in enumerate(all_files):
        # Print progress log line
        print_json({
            "type": "progress",
            "current": i + 1,
            "total": total_files,
            "file": file_path
        })

        try:
            taginfo = mutagen.File(file_path)
            if taginfo is None:
                continue

            mbid = None
            artist = ""
            title = ""

            # Check files by extension
            if file_path.lower().endswith(".mp3"):
                # Try common MusicBrainz track ID ID3 tags
                if "TXXX:MusicBrainz Release Track Id" in taginfo:
                    mbid = taginfo["TXXX:MusicBrainz Release Track Id"].text[0]
                elif "TXXX:MusicBrainz Track Id" in taginfo:
                    mbid = taginfo["TXXX:MusicBrainz Track Id"].text[0]
                elif "UFID:http://musicbrainz.org" in taginfo:
                    mbid = taginfo["UFID:http://musicbrainz.org"].data.decode('utf-8', errors='ignore')

                # Parse artist and title tags
                if "TPE1" in taginfo:
                    artist = taginfo["TPE1"].text[0]
                if "TIT2" in taginfo:
                    title = taginfo["TIT2"].text[0]

            elif file_path.lower().endswith(".flac"):
                if "musicbrainz_trackid" in taginfo:
                    mbid = taginfo["musicbrainz_trackid"][0]
                elif "musicbrainz_releasetrackid" in taginfo:
                    mbid = taginfo["musicbrainz_releasetrackid"][0]

                if "artist" in taginfo:
                    artist = taginfo["artist"][0]
                if "title" in taginfo:
                    title = taginfo["title"][0]

            # Fallback to directory structure/filename parsing if tags are missing
            if not artist or not title:
                guessed_artist, guessed_title = extract_metadata_from_path(file_path, music_dir)
                if not artist and guessed_artist:
                    artist = guessed_artist
                if not title and guessed_title:
                    title = guessed_title

            if mbid:
                mbid = mbid.strip()
                id_to_file[mbid] = file_path
                
                # Extract duration
                duration = 240.0
                if taginfo and taginfo.info and hasattr(taginfo.info, "length"):
                    duration = taginfo.info.length
                    
                song_data = {
                    "mbid": mbid,
                    "path": file_path,
                    "artist": artist if artist else "Unknown Artist",
                    "title": title if title else os.path.basename(file_path),
                    "duration": duration
                }
                gui_songs.append(song_data)
                
                # Stream the newly found song to parent
                print_json({
                    "type": "song",
                    "mbid": song_data["mbid"],
                    "path": song_data["path"],
                    "artist": song_data["artist"],
                    "title": song_data["title"]
                })
        except Exception as e:
            # Emit non-fatal warning but continue scanning the library
            print_json({
                "type": "error",
                "message": f"Failed to scan '{os.path.basename(file_path)}': {str(e)}"
            })

    # Save outputs to index files on success
    try:
        with open("file_index.json", "w") as f:
            json.dump(id_to_file, f, indent=2)
        with open("gui_index.json", "w") as f:
            json.dump(gui_songs, f, indent=2)
    except Exception as e:
        print_json({"type": "error", "message": f"Failed to save index files: {str(e)}"})
        sys.exit(1)

    print_json({"type": "finished", "count": len(id_to_file)})

def main():
    if len(sys.argv) < 2:
        print_json({"type": "error", "message": "Scanner requires music directory path as an argument."})
        sys.exit(1)
        
    music_dir = sys.argv[1]
    scan_music(music_dir)

if __name__ == "__main__":
    main()
