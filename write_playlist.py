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

import os
import json
import sys
import uuid
import argparse
import random
from collections import OrderedDict

def get_split_path(base_path, suffix):
    dir_name = os.path.dirname(base_path)
    base_name = os.path.basename(base_path)
    name, ext = os.path.splitext(base_name)
    return os.path.join(dir_name, f"{name}_{suffix}{ext}")

def main():
    parser = argparse.ArgumentParser(description="Write generated sequence to .m3u playlist files with CD and Cassette constraints.")
    parser.add_argument("playlist_path", nargs="?", default="playlist.m3u")
    parser.add_argument("--mode", default="standard", choices=["standard", "cd", "c60", "c90", "full", "half"])
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    # Load indices
    try:
        with open("file_index.json", "r") as f:
            indexmap = json.load(f)
    except Exception:
        indexmap = {}

    try:
        with open("gui_index.json", "r") as f:
            gui_songs = json.load(f)
    except Exception:
        gui_songs = []

    # Map MBID to song metadata
    songs_by_mbid = {song["mbid"]: song for song in gui_songs}

    # Destination directory creation
    dest_dir = os.path.dirname(os.path.abspath(args.playlist_path))
    base_name = os.path.basename(args.playlist_path)
    name, ext = os.path.splitext(base_name)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    # Check for static library options
    if args.mode in ("full", "half"):
        pool = [song["path"] for song in gui_songs]
        if not pool and indexmap:
            pool = list(indexmap.values())
        random.seed(42)
        random.shuffle(pool)
        if args.mode == "half":
            pool = pool[:max(1, len(pool) // 2)]
            
        with open(args.playlist_path, "w") as f:
            for path in pool:
                f.write(path + "\n")
                
        # Also save copy in 'standard' subfolder
        std_dir = os.path.join(dest_dir, "standard")
        os.makedirs(std_dir, exist_ok=True)
        with open(os.path.join(std_dir, base_name), "w") as f:
            for path in pool:
                f.write(path + "\n")
        print(f"Library Playlist ({args.mode}) generated successfully! Saved to: {args.playlist_path}")
        return

    # Read generated MBIDs from stdin
    inp = sys.stdin.read()
    generated_mbids = []
    inp_extracted = inp[inp.find("D-0"):inp.find("P-0")]
    for word in inp_extracted.split():
        try:
            mbid = str(uuid.UUID(word))
            generated_mbids.append(mbid)
        except Exception:
            continue
    generated_mbids = list(OrderedDict.fromkeys(generated_mbids))

    # Build recommendations list of valid local songs
    recommendation_songs = []
    for mbid in generated_mbids:
        if mbid in songs_by_mbid:
            recommendation_songs.append(songs_by_mbid[mbid])

    # Shuffle remaining library songs to act as a fallback pool
    rec_paths = {song["path"] for song in recommendation_songs}
    other_songs = [song for song in gui_songs if song["path"] not in rec_paths]
    random.seed(42)  # deterministic fallback
    random.shuffle(other_songs)

    # Full pool: recommendations first, then other library tracks
    pool = recommendation_songs + other_songs

    # Track paths that have been used to prevent repeats across all files in this batch
    used_paths = set()

    if args.mode == "standard":
        playlist_paths = []
        for song in pool:
            if song["path"] not in used_paths:
                playlist_paths.append(song["path"])
                used_paths.add(song["path"])
                
        # Limit standard playlist to a reasonable length if pool is huge (e.g. 50 songs)
        playlist_paths = playlist_paths[:50]

        # If pool was empty (no scanner run), fall back to indexmap keys
        if not playlist_paths and indexmap:
            all_keys = list(indexmap.keys())
            sample_size = min(15, len(all_keys))
            fallback_mbids = random.sample(all_keys, sample_size)
            playlist_paths = [indexmap[k] for k in fallback_mbids]

        with open(args.playlist_path, "w") as f:
            for path in playlist_paths:
                f.write(path + "\n")
                
        # Also save copy in 'standard' subfolder
        std_dir = os.path.join(dest_dir, "standard")
        os.makedirs(std_dir, exist_ok=True)
        with open(os.path.join(std_dir, base_name), "w") as f:
            for path in playlist_paths:
                f.write(path + "\n")
        print(f"Playlist generated successfully! Saved to: {args.playlist_path}")

    elif args.mode == "cd":
        # CD-Safe: 80 minutes = 4800 seconds max per CD
        limit = 4800.0
        cd_dir = os.path.join(dest_dir, "CDs")
        os.makedirs(cd_dir, exist_ok=True)
        for cd_idx in range(1, args.count + 1):
            playlist_paths = []
            current_duration = 0.0
            for song in pool:
                if song["path"] not in used_paths:
                    duration = song.get("duration", 240.0)
                    if duration <= 0.0:
                        duration = 240.0
                    if current_duration + duration <= limit:
                        playlist_paths.append(song["path"])
                        used_paths.add(song["path"])
                        current_duration += duration

            out_path = os.path.join(cd_dir, f"{name}_cd_{cd_idx}{ext}")
            with open(out_path, "w") as f:
                for path in playlist_paths:
                    f.write(path + "\n")
            print(f"CD-Safe Playlist {cd_idx} generated successfully! Saved to: {out_path} ({len(playlist_paths)} tracks, {int(current_duration/60)} mins)")

    elif args.mode in ("c60", "c90"):
        # Cassette C60 = 30 mins (1800s) / C90 = 45 mins (2700s) per side
        side_limit = 2700.0 if args.mode == "c90" else 1800.0
        mode_label = "C90" if args.mode == "c90" else "C60"
        cas_dir = os.path.join(dest_dir, "cassettes")
        os.makedirs(cas_dir, exist_ok=True)
        
        for cas_idx in range(1, args.count + 1):
            for side in ("sideA", "sideB"):
                playlist_paths = []
                current_duration = 0.0
                for song in pool:
                    if song["path"] not in used_paths:
                        duration = song.get("duration", 240.0)
                        if duration <= 0.0:
                            duration = 240.0
                        if current_duration + duration <= side_limit:
                            playlist_paths.append(song["path"])
                            used_paths.add(song["path"])
                            current_duration += duration

                out_path = os.path.join(cas_dir, f"{name}_cassette_{cas_idx}_{side}{ext}")
                with open(out_path, "w") as f:
                    for path in playlist_paths:
                        f.write(path + "\n")
                print(f"Cassette {mode_label} Playlist {cas_idx} ({side}) generated successfully! Saved to: {out_path} ({len(playlist_paths)} tracks, {int(current_duration/60)} mins)")

if __name__ == "__main__":
    main()
