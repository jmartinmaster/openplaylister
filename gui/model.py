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

# gui/model.py

import os
import json
import shutil
import mutagen

class OpenPlaylisterModel:
    def __init__(self):
        self.config_file = "config.json"
        self.index_file = "file_index.json"
        self.gui_index_file = "gui_index.json"
        
        # Default configuration
        self.config = {
            "music_dir": "",
            "listenbrainz_json": "",
            "playlist_save_path": os.path.abspath("playlist.m3u"),
            "theme": "dark",
            "num_workers": "1",
            "num_gpus": "1",
            "train_level": 30000
        }
        
        self.songs_list = [] # List of dicts: {mbid, path, artist, title}
        self.load_config()
        self.load_song_index()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception:
                pass
        else:
            self.save_config()

    def save_config(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def get_config_value(self, key):
        return self.config.get(key, "")

    def set_config_value(self, key, value):
        self.config[key] = value
        self.save_config()

    def load_song_index(self):
        """Load songs from the cached gui_index_file. 
        If it doesn't exist but file_index.json does, rebuild gui_index_file on startup."""
        self.songs_list = []
        if os.path.exists(self.gui_index_file):
            try:
                with open(self.gui_index_file, "r") as f:
                    self.songs_list = json.load(f)
                
                # Dynamic upgrade: if duration or album is missing or default, resolve it
                needs_save = False
                from gui.metadata_helper import extract_metadata_from_path
                music_dir = self.get_config_value("music_dir")
                for song in self.songs_list:
                    if "duration" not in song or song["duration"] == 240.0:
                        path = song["path"]
                        if os.path.exists(path):
                            try:
                                taginfo = mutagen.File(path)
                                if taginfo and taginfo.info and hasattr(taginfo.info, "length"):
                                    song["duration"] = taginfo.info.length
                                    needs_save = True
                            except Exception:
                                pass
                    if "album" not in song or not song["album"] or song["album"] == "Unknown Album":
                        path = song["path"]
                        resolved_album = ""
                        if os.path.exists(path):
                            try:
                                taginfo = mutagen.File(path)
                                if taginfo:
                                    if path.lower().endswith(".mp3") and "TALB" in taginfo:
                                        resolved_album = taginfo["TALB"].text[0]
                                    elif path.lower().endswith(".flac") and "album" in taginfo:
                                        resolved_album = taginfo["album"][0]
                            except Exception:
                                pass
                        if not resolved_album:
                            _a, g_album, _t = extract_metadata_from_path(path, music_dir)
                            resolved_album = g_album
                        if resolved_album:
                            song["album"] = resolved_album
                            needs_save = True
                        elif "album" not in song:
                            song["album"] = "Unknown Album"
                            needs_save = True

                if needs_save:
                    self.save_gui_index()
                return
            except Exception:
                pass
                
        # Fallback to rebuild gui_index_file from file_index.json if present
        if os.path.exists(self.index_file):
            try:
                from gui.metadata_helper import extract_metadata_from_path
                music_dir = self.get_config_value("music_dir")
                with open(self.index_file, "r") as f:
                    raw_index = json.load(f)
                
                # Perform a fast scan of tags for these files to rebuild GUI cache
                for mbid, path in raw_index.items():
                    if os.path.exists(path):
                        artist = ""
                        album = ""
                        title = ""
                        duration = 240.0
                        try:
                            taginfo = mutagen.File(path)
                            if taginfo:
                                if taginfo.info and hasattr(taginfo.info, "length"):
                                    duration = taginfo.info.length
                                if path.lower().endswith(".mp3"):
                                    if "TPE1" in taginfo: artist = taginfo["TPE1"].text[0]
                                    if "TALB" in taginfo: album = taginfo["TALB"].text[0]
                                    if "TIT2" in taginfo: title = taginfo["TIT2"].text[0]
                                elif path.lower().endswith(".flac"):
                                    if "artist" in taginfo: artist = taginfo["artist"][0]
                                    if "album" in taginfo: album = taginfo["album"][0]
                                    if "title" in taginfo: title = taginfo["title"][0]
                        except Exception:
                            pass

                        if not artist or not album or not title:
                            g_artist, g_album, g_title = extract_metadata_from_path(path, music_dir)
                            if not artist and g_artist: artist = g_artist
                            if not album and g_album: album = g_album
                            if not title and g_title: title = g_title
                        
                        self.songs_list.append({
                            "mbid": mbid,
                            "path": path,
                            "artist": artist if artist else "Unknown Artist",
                            "album": album if album else "Unknown Album",
                            "title": title if title else os.path.basename(path),
                            "duration": duration
                        })
                self.save_gui_index()
            except Exception:
                pass

    def save_gui_index(self):
        try:
            with open(self.gui_index_file, "w") as f:
                json.dump(self.songs_list, f, indent=4)
        except Exception:
            pass

    def clear_index(self):
        self.songs_list = []
        if os.path.exists(self.index_file):
            try:
                os.remove(self.index_file)
            except Exception:
                pass
        if os.path.exists(self.gui_index_file):
            try:
                os.remove(self.gui_index_file)
            except Exception:
                pass

    def add_scanned_song(self, song_dict):
        # Prevent duplicates
        for song in self.songs_list:
            if song["mbid"] == song_dict["mbid"]:
                return
        self.songs_list.append(song_dict)

    def check_fairseq_installed(self):
        """Check if fairseq CLI tools are available in PATH."""
        return shutil.which("fairseq-preprocess") is not None and shutil.which("fairseq-train") is not None

    def get_dashboard_status(self):
        """Returns states of various components to display on Dashboard."""
        status = {
            "fairseq_ok": self.check_fairseq_installed(),
            "music_index_ok": os.path.exists(self.index_file) and len(self.songs_list) > 0,
            "index_count": len(self.songs_list),
            "preprocess_ok": os.path.exists("data-bin/brainz/dict.txt"),
            "model_trained_ok": os.path.exists("checkpoints/brainz/checkpoint_last.pt"),
            "playlist_exists": os.path.exists(self.get_config_value("playlist_save_path"))
        }
        return status

