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

# gui/workers.py

import os
import sys
import glob
import json
import subprocess
import time
import signal
import urllib.request
import urllib.parse
from PyQt6.QtCore import QThread, pyqtSignal
from gui.metadata_helper import extract_metadata_from_path
import mutagen

class MusicScannerWorker(QThread):
    progress = pyqtSignal(int, int, str)  # current, total, current_file_path
    song_found = pyqtSignal(dict)         # dict with mbid, path, artist, title
    finished_scanning = pyqtSignal(dict)  # final mapping dict
    error_occurred = pyqtSignal(str)      # reports non-fatal or process error log messages

    def __init__(self, music_dir):
        super().__init__()
        self.music_dir = music_dir
        self.process = None

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def run(self):
        if not self.music_dir or not os.path.exists(self.music_dir):
            self.error_occurred.emit("Specified music directory does not exist.")
            self.finished_scanning.emit({})
            return

        # Find absolute path of the scanner script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scanner_script = os.path.join(script_dir, "scanner_cli.py")

        cmd = [sys.executable, scanner_script, self.music_dir]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Read child stdout line-by-line
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    try:
                        data = json.loads(line.strip())
                        msg_type = data.get("type")

                        if msg_type == "progress":
                            self.progress.emit(data["current"], data["total"], data["file"])
                        elif msg_type == "song":
                            self.song_found.emit({
                                "mbid": data["mbid"],
                                "path": data["path"],
                                "artist": data["artist"],
                                "title": data["title"]
                            })
                        elif msg_type == "error":
                            self.error_occurred.emit(data["message"])
                        elif msg_type == "finished":
                            pass
                    except json.JSONDecodeError:
                        # Print raw console lines if any
                        pass

            # Await process exit
            self.process.wait()
            exit_code = self.process.returncode
            stderr_out = self.process.stderr.read()

            if exit_code != 0:
                self.error_occurred.emit(
                    f"Scanner child process failed with exit code {exit_code}.\n"
                    f"Stderr: {stderr_out.strip()}"
                )

        except Exception as e:
            self.error_occurred.emit(f"Failed to start scanner child process: {str(e)}")

        # Finally, read and return the written file_index.json
        final_index = {}
        if os.path.exists("file_index.json"):
            try:
                with open("file_index.json", "r") as f:
                    final_index = json.load(f)
            except Exception:
                pass

        self.finished_scanning.emit(final_index)



class CommandWorker(QThread):
    line_read = pyqtSignal(str)
    finished_command = pyqtSignal(int)  # exit code

    def __init__(self, command, cwd=None, env_update=None):
        super().__init__()
        self.command = command
        self.cwd = cwd or os.getcwd()
        self.process = None
        self.env_update = env_update

    def run(self):
        env = os.environ.copy()
        if self.env_update:
            env.update(self.env_update)

        # Force unbuffered output so we get stdout line by line immediately
        env["PYTHONUNBUFFERED"] = "1"
        # Avoid pager issues
        env["PAGER"] = "cat"

        try:
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
                preexec_fn=os.setsid
            )

            # Read output line by line
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    self.line_read.emit(line.rstrip())

            self.process.communicate()
            exit_code = self.process.returncode
            self.finished_command.emit(exit_code)
        except Exception as e:
            self.line_read.emit(f"Error executing command: {str(e)}")
            self.finished_command.emit(-1)

    def stop(self):
        if self.process:
            try:
                # Terminate the entire process group to ensure child processes are killed
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception:
                try:
                    pgid = os.getpgid(self.process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass


class ListenBrainzDownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished_download = pyqtSignal(str)  # returns the path to the written file
    error_occurred = pyqtSignal(str)

    def __init__(self, username, save_path):
        super().__init__()
        self.username = username
        self.save_path = save_path
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        self.progress.emit(f"Starting history download for username: {self.username}...")
        
        listens = []
        max_ts = None
        count_limit = 3000
        
        headers = {
            "User-Agent": "OpenPlaylister/1.0.0 (https://github.com/jamie/openplaylister)"
        }
        
        while self._is_running and len(listens) < count_limit:
            url = f"https://api.listenbrainz.org/1/user/{self.username}/listens?count=100"
            if max_ts is not None:
                url += f"&max_ts={max_ts}"
                
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status != 200:
                        self.error_occurred.emit(f"HTTP error: {response.status}")
                        return
                    data = json.loads(response.read().decode('utf-8'))
                    
                payload = data.get("payload", {})
                page_listens = payload.get("listens", [])
                
                if not page_listens:
                    break
                    
                listens.extend(page_listens)
                self.progress.emit(f"Downloaded {len(listens)} listens...")
                
                # Get the minimum timestamp of this page to query the next (older) page
                timestamps = [item.get("listened_at") for item in page_listens if item.get("listened_at") is not None]
                if not timestamps:
                    break
                    
                min_ts = min(timestamps)
                # If the new min_ts is equal to or greater than the previous max_ts, we break to avoid loops
                if max_ts is not None and min_ts >= max_ts:
                    break
                max_ts = min_ts
                
                # Sleep a tiny bit to be polite
                time.sleep(0.5)
                
            except Exception as e:
                self.error_occurred.emit(f"Error fetching data: {str(e)}")
                return
                
        if not listens:
            self.error_occurred.emit("No listens found for the specified user.")
            return
            
        # Ensure the destination folder exists
        dest_dir = os.path.dirname(os.path.abspath(self.save_path))
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
            
        try:
            # We save the raw listens list directly (array of dicts)
            # which matches the format of ListenBrainz website JSON export
            with open(self.save_path, "w") as f:
                json.dump(listens, f, indent=2)
            self.progress.emit(f"History saved successfully to {self.save_path}")
            self.finished_download.emit(self.save_path)
        except Exception as e:
            self.error_occurred.emit(f"Failed to write file: {str(e)}")


class TagResolverWorker(QThread):
    progress = pyqtSignal(int, int, str)  # current, total, status text
    finished_resolving = pyqtSignal(int, int) # matched, failed
    error_occurred = pyqtSignal(str)

    def __init__(self, music_dir, playlist_save_path):
        super().__init__()
        self.music_dir = music_dir
        self.playlist_save_path = playlist_save_path
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        if not self.music_dir or not os.path.exists(self.music_dir):
            self.error_occurred.emit("Invalid music collection path.")
            self.finished_resolving.emit(0, 0)
            return

        # Find all MP3 and FLAC files recursively
        mp3_pattern = os.path.join(self.music_dir, "**", "*.mp3")
        flac_pattern = os.path.join(self.music_dir, "**", "*.flac")

        mp3_files = glob.glob(mp3_pattern, recursive=True)
        flac_files = glob.glob(flac_pattern, recursive=True)
        all_files = mp3_files + flac_files
        total_files = len(all_files)

        if total_files == 0:
            self.progress.emit(0, 0, "No audio files found to verify.")
            self.finished_resolving.emit(0, 0)
            return

        self.progress.emit(0, total_files, "Scanning library for missing MBID tags...")
        
        # Filter files lacking MBIDs
        to_resolve = []
        for file_path in all_files:
            if not self._is_running:
                break
            
            try:
                taginfo = mutagen.File(file_path)
                if taginfo is None:
                    continue
                
                mbid_found = False
                artist = ""
                title = ""
                
                if file_path.lower().endswith(".mp3"):
                    if "TXXX:MusicBrainz Release Track Id" in taginfo or "TXXX:MusicBrainz Track Id" in taginfo or "UFID:http://musicbrainz.org" in taginfo:
                        mbid_found = True
                    if "TPE1" in taginfo:
                        artist = taginfo["TPE1"].text[0]
                    if "TIT2" in taginfo:
                        title = taginfo["TIT2"].text[0]
                elif file_path.lower().endswith(".flac"):
                    if "musicbrainz_trackid" in taginfo or "musicbrainz_releasetrackid" in taginfo:
                        mbid_found = True
                    if "artist" in taginfo:
                        artist = taginfo["artist"][0]
                    if "title" in taginfo:
                        title = taginfo["title"][0]
                        
                # Fallback to directory structure/filename parsing if tags are missing
                if not artist or not title:
                    guessed_artist, guessed_title = extract_metadata_from_path(file_path, self.music_dir)
                    if not artist and guessed_artist:
                        artist = guessed_artist
                    if not title and guessed_title:
                        title = guessed_title

                if not mbid_found:
                    to_resolve.append((file_path, artist, title))
            except Exception:
                pass

        total_resolve = len(to_resolve)
        if total_resolve == 0:
            self.progress.emit(total_files, total_files, "All files already have MusicBrainz ID tags!")
            self.finished_resolving.emit(0, 0)
            return

        self.progress.emit(0, total_resolve, f"Found {total_resolve} files lacking MBID. Starting query with rate limits...")
        
        matched_count = 0
        failed_count = 0
        failed_list = []
        
        headers = {
            "User-Agent": "OpenPlaylister/1.0.0 (https://github.com/jamie/openplaylister)"
        }

        for idx, (file_path, artist, title) in enumerate(to_resolve):
            if not self._is_running:
                break

            self.progress.emit(idx + 1, total_resolve, f"Querying MusicBrainz for: {os.path.basename(file_path)}")

            if not artist or not title:
                failed_count += 1
                failed_list.append((file_path, artist, title, "Missing basic tags (artist/title) to search with"))
                continue

            # Query MusicBrainz API
            # Encode query fields properly
            query = f'artist:"{artist}" AND recording:"{title}"'
            url = f"https://musicbrainz.org/ws/2/recording?query={urllib.parse.quote(query)}&fmt=json"

            mbid = None
            error_msg = "Track not found in MusicBrainz"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        res_data = json.loads(response.read().decode('utf-8'))
                        recordings = res_data.get("recordings", [])
                        
                        if recordings:
                            # Select first match if score is high enough (score is in recordings)
                            best = recordings[0]
                            score = int(best.get("score", 0))
                            if score >= 80:
                                mbid = best.get("id")
                            else:
                                error_msg = f"Match confidence score too low ({score})"
            except Exception as e:
                error_msg = f"API Error: {str(e)}"

            if mbid:
                # Write MBID tag back to file
                try:
                    if file_path.lower().endswith(".mp3"):
                        # Use mutagen.id3
                        from mutagen.id3 import ID3, TXXX, ID3NoHeaderError
                        try:
                            tags = ID3(file_path)
                        except ID3NoHeaderError:
                            tags = ID3()
                        
                        tags["TXXX:MusicBrainz Release Track Id"] = TXXX(
                            encoding=3,
                            desc="MusicBrainz Release Track Id",
                            text=[mbid]
                        )
                        tags.save(file_path)
                    elif file_path.lower().endswith(".flac"):
                        from mutagen.flac import FLAC
                        audio = FLAC(file_path)
                        audio["musicbrainz_trackid"] = mbid
                        audio.save()

                    matched_count += 1
                    self.progress.emit(idx + 1, total_resolve, f"Successfully tagged: {os.path.basename(file_path)}")
                except Exception as tag_err:
                    failed_count += 1
                    failed_list.append((file_path, artist, title, f"Tag write error: {str(tag_err)}"))
            else:
                failed_count += 1
                failed_list.append((file_path, artist, title, error_msg))

            # Strictly sleep 1.5 seconds to comply with MusicBrainz rate limiting
            time.sleep(1.5)

        # Write failed list to output directory
        out_dir = os.path.dirname(os.path.abspath(self.playlist_save_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        
        failed_report_path = os.path.join(out_dir, "untagged_songs.txt")
        try:
            with open(failed_report_path, "w") as rf:
                rf.write("==================================================\n")
                rf.write("         UNTAGGED SONGS REPORT (FAILED RESOLVES)  \n")
                rf.write("==================================================\n")
                rf.write(f"Scanned: {total_resolve} | Successfully Tagged: {matched_count} | Failed: {failed_count}\n")
                rf.write("--------------------------------------------------\n\n")
                
                for f_path, f_artist, f_title, f_reason in failed_list:
                    rf.write(f"File: {f_path}\n")
                    rf.write(f"  Artist: {f_artist or 'Unknown'} | Title: {f_title or 'Unknown'}\n")
                    rf.write(f"  Reason: {f_reason}\n")
                    rf.write("--------------------------------------------------\n")
                    
            self.progress.emit(total_resolve, total_resolve, f"Auto-tagging complete! Matched {matched_count}. Report written to: {failed_report_path}")
        except Exception as file_err:
            self.error_occurred.emit(f"Failed to write untagged list: {str(file_err)}")

        self.finished_resolving.emit(matched_count, failed_count)

