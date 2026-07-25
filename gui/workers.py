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

        # Ensure executable directory (venv bin) is in PATH
        bin_dir = os.path.dirname(sys.executable)
        if bin_dir not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

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
                    guessed_artist, _guessed_album, guessed_title = extract_metadata_from_path(file_path, self.music_dir)
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


class WAVConverterWorker(QThread):
    progress = pyqtSignal(int, int, str)
    line_read = pyqtSignal(str)
    finished_conversion = pyqtSignal(list)

    def __init__(self, tracks, output_dir, normalize=False, num_workers=1):
        super().__init__()
        self.tracks = tracks # List of tuples: (track_idx, title, artist, file_path)
        self.output_dir = output_dir
        self.normalize = normalize
        self.num_workers = num_workers
        self.is_stopped = False
        self.active_processes = []

    def stop(self):
        self.is_stopped = True
        for proc in self.active_processes:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self):
        import wave
        import subprocess
        import time
        import os
        
        os.makedirs(self.output_dir, exist_ok=True)
        results = [None] * len(self.tracks)
        total = len(self.tracks)
        
        max_concurrent = max(1, self.num_workers)
        queue = list(enumerate(self.tracks))
        self.active_processes = []
        completed_count = 0
        
        while (queue or self.active_processes) and not self.is_stopped:
            # Spawn new processes if room
            while len(self.active_processes) < max_concurrent and queue:
                idx, (track_idx, title, artist, orig_path) = queue.pop(0)
                
                self.progress.emit(completed_count, total, f"Converting {title} by {artist}...")
                dest_path = os.path.join(self.output_dir, f"track_{track_idx:02d}.wav")
                
                cmd = [
                    "ffmpeg", "-y", "-i", orig_path,
                    "-map_metadata", "0",
                    "-metadata", f"title={title}",
                    "-metadata", f"artist={artist}",
                    "-metadata", f"track={track_idx}",
                    "-write_id3v2", "1"
                ]
                if self.normalize:
                    cmd.extend(["-af", "loudnorm"])
                cmd.extend([
                    "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
                    dest_path
                ])
                
                try:
                    self.line_read.emit(f"\n>>> Converting track {track_idx} [Parallel]: {title}...")
                    self.line_read.emit(f"Running: {' '.join(cmd)}")
                    
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    self.active_processes.append((idx, track_idx, title, artist, orig_path, dest_path, proc))
                except Exception as e:
                    self.line_read.emit(f"Failed to start conversion for {title}: {str(e)}")
                    results[idx] = {
                        "index": track_idx,
                        "title": title,
                        "artist": artist,
                        "original_path": orig_path,
                        "wav_path": "",
                        "size": 0,
                        "duration": 0.0,
                        "status": "Failed"
                    }
                    completed_count += 1
            
            # Check finished processes
            still_active = []
            for item in self.active_processes:
                idx, track_idx, title, artist, orig_path, dest_path, proc = item
                
                poll = proc.poll()
                if poll is not None:
                    # Finished!
                    completed_count += 1
                    self.progress.emit(completed_count, total, f"Completed {title}...")
                    
                    # Read final output lines
                    stdout_out, _ = proc.communicate()
                    if stdout_out:
                        self.line_read.emit(stdout_out.strip())
                        
                    exit_code = proc.returncode
                    if exit_code == 0 and os.path.exists(dest_path):
                        size = os.path.getsize(dest_path)
                        duration = 0.0
                        try:
                            with wave.open(dest_path, "r") as w:
                                frames = w.getnframes()
                                rate = w.getframerate()
                                duration = frames / float(rate)
                        except Exception as e:
                            self.line_read.emit(f"Warning reading WAV header: {str(e)}")
                            
                        # Embed ID3v2 metadata tags into WAV file using mutagen
                        try:
                            import mutagen.wave
                            import mutagen.id3
                            audio = mutagen.wave.WAVE(dest_path)
                            if audio.tags is None:
                                audio.add_tags()
                            audio.tags["TIT2"] = mutagen.id3.TIT2(encoding=3, text=title)
                            audio.tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text=artist)
                            audio.tags["TRCK"] = mutagen.id3.TRCK(encoding=3, text=str(track_idx))
                            audio.save()
                            self.line_read.emit(f"Embedded WAV metadata tags: '{title}' by {artist} (Track {track_idx})")
                        except Exception as tag_err:
                            self.line_read.emit(f"Warning embedding WAV ID3 tags: {str(tag_err)}")
                            
                        results[idx] = {
                            "index": track_idx,
                            "title": title,
                            "artist": artist,
                            "original_path": orig_path,
                            "wav_path": dest_path,
                            "size": size,
                            "duration": duration,
                            "status": "Converted"
                        }
                    else:
                        results[idx] = {
                            "index": track_idx,
                            "title": title,
                            "artist": artist,
                            "original_path": orig_path,
                            "wav_path": "",
                            "size": 0,
                            "duration": 0.0,
                            "status": "Failed"
                        }
                        self.line_read.emit(f"Error converting track {track_idx} ({title}): ffmpeg exited with code {exit_code}")
                else:
                    still_active.append(item)
                    
            self.active_processes = still_active
            time.sleep(0.05)
            
        # Clean up if stopped
        if self.is_stopped:
            for item in self.active_processes:
                try:
                    item[-1].terminate()
                except Exception:
                    pass
            for idx, res in enumerate(results):
                if res is None:
                    track_idx, title, artist, orig_path = self.tracks[idx]
                    results[idx] = {
                        "index": track_idx,
                        "title": title,
                        "artist": artist,
                        "original_path": orig_path,
                        "wav_path": "",
                        "size": 0,
                        "duration": 0.0,
                        "status": "Stopped"
                    }
                    
        self.finished_conversion.emit(results)


class CDBurnWorker(QThread):
    line_read = pyqtSignal(str, str)
    finished_burn = pyqtSignal(str, int)
    
    def __init__(self, device, playlist_path, temp_dir, simulate=False, normalize=True, speed="Auto", overburn=False, burn_type="audio"):
        super().__init__()
        self.device = device
        self.tag = os.path.basename(device)
        self.playlist_path = playlist_path
        self.temp_dir = temp_dir
        self.simulate = simulate
        self.normalize = normalize
        self.speed = speed
        self.overburn = overburn
        self.burn_type = burn_type
        self.is_stopped = False
        self.process = None
        
    def stop(self):
        self.is_stopped = True
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
                
    def run(self):
        import subprocess
        import shutil
        import mutagen.wave
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Read WAV files from playlist
        wav_files = []
        try:
            with open(self.playlist_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        wav_files.append(os.path.abspath(line))
        except Exception as e:
            self.line_read.emit(f"[{self.tag}] Error reading playlist: {str(e)}", self.tag)
            self.finished_burn.emit(self.device, -1)
            return

        if not wav_files:
            self.line_read.emit(f"[{self.tag}] Error: No audio tracks found in playlist.", self.tag)
            self.finished_burn.emit(self.device, -1)
            return

        if self.burn_type == "data":
            # ----------------------------------------------------
            # Data CD Mode (ISO9660 filesystem with tagged WAVs & M3U)
            # ----------------------------------------------------
            iso_stage_dir = os.path.join(self.temp_dir, "iso_stage")
            os.makedirs(iso_stage_dir, exist_ok=True)
            
            iso_playlist_lines = []
            for idx, orig_wav in enumerate(wav_files, start=1):
                track_title = f"Track {idx:02d}"
                track_artist = "Unknown Artist"
                try:
                    audio = mutagen.wave.WAVE(orig_wav)
                    if audio.tags:
                        if "TIT2" in audio.tags:
                            track_title = str(audio.tags["TIT2"])
                        if "TPE1" in audio.tags:
                            track_artist = str(audio.tags["TPE1"])
                except Exception:
                    pass
                
                safe_title = "".join(c for c in track_title if c.isalnum() or c in (" ", "_", "-")).strip()
                safe_artist = "".join(c for c in track_artist if c.isalnum() or c in (" ", "_", "-")).strip()
                dest_filename = f"{idx:02d} - {safe_artist} - {safe_title}.wav" if safe_artist and safe_title else f"track_{idx:02d}.wav"
                
                dest_wav = os.path.join(iso_stage_dir, dest_filename)
                try:
                    shutil.copy2(orig_wav, dest_wav)
                except Exception:
                    dest_wav = os.path.join(iso_stage_dir, f"track_{idx:02d}.wav")
                    shutil.copy2(orig_wav, dest_wav)
                    
                iso_playlist_lines.append(os.path.basename(dest_wav))

            # Write .m3u playlist file into ISO stage folder
            with open(os.path.join(iso_stage_dir, "playlist.m3u"), "w") as m3u_f:
                m3u_f.write("#EXTM3U\n")
                for fn in iso_playlist_lines:
                    m3u_f.write(fn + "\n")

            iso_path = os.path.join(self.temp_dir, "playlist.iso")
            self.line_read.emit(f"[{self.tag}] Building ISO9660 Data Image with tagged WAV files: {iso_path}", self.tag)
            
            gen_cmd = ["genisoimage", "-V", "PLAYLIST_CD", "-J", "-r", "-o", iso_path, iso_stage_dir]
            proc_gen = subprocess.run(gen_cmd, capture_output=True, text=True)
            if proc_gen.returncode != 0:
                self.line_read.emit(f"[{self.tag}] Error generating ISO image: {proc_gen.stderr}", self.tag)
                self.finished_burn.emit(self.device, -1)
                return
                
            iso_size_mb = os.path.getsize(iso_path) / (1024 * 1024)
            self.line_read.emit(f"[{self.tag}] ISO image created cleanly ({iso_size_mb:.2f} MB): {iso_path}", self.tag)

            cmd = ["wodim", "-v", f"dev={self.device}", "-sao", "-data"]
            if self.simulate:
                cmd.append("-dummy")
            if self.overburn:
                cmd.append("-overburn")
            if self.speed and self.speed != "Auto":
                speed_val = self.speed.lower().replace("x", "")
                cmd.append(f"speed={speed_val}")
            cmd.append(iso_path)

        else:
            # ----------------------------------------------------
            # Audio CD Mode (Red Book CD-DA + CD-Text INF files)
            # ----------------------------------------------------
            burn_wav_paths = []
            
            for idx, orig_wav in enumerate(wav_files, start=1):
                wav_name = f"track_{idx:02d}.wav"
                inf_name = f"track_{idx:02d}.inf"
                target_wav = os.path.join(self.temp_dir, wav_name)
                target_inf = os.path.join(self.temp_dir, inf_name)
                
                if os.path.abspath(orig_wav) != os.path.abspath(target_wav):
                    try:
                        shutil.copy2(orig_wav, target_wav)
                    except Exception:
                        target_wav = orig_wav
                
                burn_wav_paths.append(target_wav)
                
                # Read embedded tags from WAV file using mutagen if available
                track_title = f"Track {idx:02d}"
                track_artist = "Unknown Artist"
                try:
                    audio = mutagen.wave.WAVE(target_wav)
                    if audio.tags:
                        if "TIT2" in audio.tags:
                            track_title = str(audio.tags["TIT2"])
                        if "TPE1" in audio.tags:
                            track_artist = str(audio.tags["TPE1"])
                except Exception:
                    pass
                    
                title_escaped = track_title.replace("'", "\\'")
                artist_escaped = track_artist.replace("'", "\\'")
                
                inf_content = (
                    f"# INF file generated by OpenPlaylister for CD-Text\n"
                    f"Tracknumber={idx}\n"
                    f"Trackstart=0\n"
                    f"Tracklength=0\n"
                    f"Tracktitle='{title_escaped}'\n"
                    f"Performer='{artist_escaped}'\n"
                    f"Composer='{artist_escaped}'\n"
                )
                try:
                    with open(target_inf, "w") as f_inf:
                        f_inf.write(inf_content)
                except Exception as inf_e:
                    self.line_read.emit(f"[{self.tag}] Warning writing CD-Text INF file: {str(inf_e)}", self.tag)

            # Build wodim command with CD-Text support
            cmd = ["wodim", "-v", f"dev={self.device}", "-sao", "-useinfo", "-text", "-audio", "-pad"]
            if self.simulate:
                cmd.append("-dummy")
            if self.overburn:
                cmd.append("-overburn")
                
            if self.speed and self.speed != "Auto":
                speed_val = self.speed.lower().replace("x", "")
                cmd.append(f"speed={speed_val}")
                
            cmd.extend(burn_wav_paths)
        
        self.line_read.emit(f"[{self.tag}] Starting burn command ({self.burn_type.upper()} Mode): {' '.join(cmd)}", self.tag)
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=self.temp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    self.line_read.emit(f"[{self.tag}] {line.strip()}", self.tag)
                    
            self.process.wait()
            exit_code = self.process.returncode
        except Exception as e:
            self.line_read.emit(f"[{self.tag}] Execution Exception: {str(e)}", self.tag)
            exit_code = -1
            
        self.finished_burn.emit(self.device, exit_code)


class PrereqRunnerWorker(QThread):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    finished_prereqs = pyqtSignal(bool, str)

    def __init__(self, music_dir="standard"):
        super().__init__()
        self.music_dir = music_dir

    def run(self):
        env = os.environ.copy()
        bin_dir = os.path.dirname(sys.executable)
        if bin_dir not in env.get("PATH", "").split(os.pathsep):
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

        # 1. Check Music Index
        self.status_signal.emit("Checking music library index...")
        gui_index_exists = os.path.exists("gui_index.json") and os.path.getsize("gui_index.json") > 2
        file_index_exists = os.path.exists("file_index.json") and os.path.getsize("file_index.json") > 2
        
        if not gui_index_exists and not file_index_exists:
            self.log_signal.emit(">>> [PREREQUISITE] Music index missing. Running song scanner...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            scanner_script = os.path.join(script_dir, "scanner_cli.py")
            scan_path = self.music_dir if os.path.exists(self.music_dir) else "."
            proc = subprocess.run([sys.executable, scanner_script, scan_path], env=env, capture_output=True, text=True)
            if proc.returncode != 0:
                self.log_signal.emit(f">>> Warning during indexing: {proc.stderr}")

        # 2. Check Listening History File
        self.status_signal.emit("Checking listening history dataset...")
        history_file = None
        for cand in ["fake_history.json", "listenbrainz.json", "user_history.json"]:
            if os.path.exists(cand) and os.path.getsize(cand) > 10:
                history_file = cand
                break

        if not history_file:
            self.log_signal.emit(">>> [PREREQUISITE] Listening history missing. Generating fake history dataset...")
            try:
                gen_code = "import random, json, uuid; tracks = [{'track_metadata': {'mbid_mapping': {'recording_mbid': str(uuid.uuid4())}}} for _ in range(300)]; open('fake_history.json', 'w').write(json.dumps(tracks))"
                subprocess.run([sys.executable, "-c", gen_code], env=env, check=True)
                history_file = "fake_history.json"
            except Exception as e:
                self.log_signal.emit(f">>> Failed generating fake history: {str(e)}")

        # 3. Check Preprocessed Data (data-bin/brainz/dict.txt)
        dict_path = os.path.join("data-bin", "brainz", "dict.txt")
        if not os.path.exists(dict_path) or not history_file:
            self.log_signal.emit(">>> [PREREQUISITE] Preprocessed binaries missing. Running preprocess.sh...")
            self.status_signal.emit("Preprocessing listening history...")
            target_hist = history_file or "fake_history.json"
            proc = subprocess.run(["./preprocess.sh", target_hist], env=env, capture_output=True, text=True)
            if proc.returncode != 0:
                self.log_signal.emit(f">>> Preprocessing failed: {proc.stderr}")
                self.finished_prereqs.emit(False, "Preprocessing failed.")
                return

        # 4. Check Checkpoint & Vocab Compatibility
        ckpt_path = os.path.join("checkpoints", "brainz", "checkpoint_last.pt")
        needs_training = False

        if not os.path.exists(dict_path):
            self.finished_prereqs.emit(False, "dict.txt missing after preprocessing.")
            return

        with open(dict_path, "r") as f:
            current_vocab = sum(1 for line in f if line.strip()) + 4

        if os.path.exists(ckpt_path):
            try:
                import torch
                state = torch.load(ckpt_path, map_location="cpu")
                if "model" in state and "decoder.embed_tokens.weight" in state["model"]:
                    ckpt_vocab = state["model"]["decoder.embed_tokens.weight"].shape[0]
                    if current_vocab != ckpt_vocab:
                        self.log_signal.emit(f">>> [PREREQUISITE] Vocabulary shape mismatch detected (checkpoint: {ckpt_vocab}, current dictionary: {current_vocab}). Wiping stale checkpoint...")
                        needs_training = True
            except Exception as e:
                self.log_signal.emit(f">>> Checkpoint inspection warning: {str(e)}")
                needs_training = True
        else:
            needs_training = True

        if needs_training:
            self.log_signal.emit(">>> [PREREQUISITE] Model checkpoint missing or shape mismatched. Running model training...")
            self.status_signal.emit("Training model to match dictionary...")
            import shutil
            checkpoints_dir = os.path.abspath("checkpoints/brainz")
            if os.path.exists(checkpoints_dir):
                try:
                    shutil.rmtree(checkpoints_dir)
                except Exception:
                    pass
            os.makedirs(checkpoints_dir, exist_ok=True)

            train_cmd = [
                "fairseq-train", "--task", "language_modeling", "data-bin/brainz/",
                "--save-dir", "checkpoints/brainz",
                "--arch", "transformer_lm", "--share-decoder-input-output-embed",
                "--dropout", "0.1", "--optimizer", "adam", "--adam-betas", "(0.9, 0.98)",
                "--weight-decay", "0.01", "--clip-norm", "0.0", "--lr", "0.0005",
                "--lr-scheduler", "inverse_sqrt", "--warmup-updates", "100", "--warmup-init-lr", "1e-07",
                "--tokens-per-sample", "2500", "--sample-break-mode", "none",
                "--max-tokens", "2048", "--max-update", "300",
                "--save-interval", "500", "--combine-valid-subsets"
            ]
            self.log_signal.emit(f">>> Executing: {' '.join(train_cmd)}")
            proc = subprocess.run(train_cmd, env=env, capture_output=True, text=True)
            if proc.returncode != 0 and not os.path.exists(ckpt_path):
                self.log_signal.emit(f">>> Model training error output:\n{proc.stderr}")
                self.finished_prereqs.emit(False, f"Training failed with exit code {proc.returncode}.")
                return

        self.log_signal.emit(">>> [PREREQUISITE] All prerequisites satisfied cleanly.")
        self.finished_prereqs.emit(True, "Prerequisites ready.")


