#!/usr/bin/env python3
# OpenPlaylister AI - Spotify History Resolver
# Copyright (c) 2026 Antigravity / OpenPlaylister Contributors
# Licensed under the GPLv3 License.

import os
import sys
import json
import re

def normalize_str(s):
    if not s:
        return ""
    # Lowercase, strip, keep only lowercase alphanumeric
    return re.sub(r'[^a-z0-9]', '', s.lower().strip())

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 spotify_to_listenbrainz.py <spotify_json_path> <output_json_path>")
        sys.exit(1)

    spotify_path = sys.argv[1]
    output_path = sys.argv[2]

    # Load gui_index.json
    gui_index_path = "gui_index.json"
    if not os.path.exists(gui_index_path):
        print(f"Error: {gui_index_path} not found. Please scan your music library first.")
        sys.exit(1)

    try:
        with open(gui_index_path, "r") as f:
            gui_songs = json.load(f)
    except Exception as e:
        print(f"Error reading {gui_index_path}: {str(e)}")
        sys.exit(1)

    # Build lookup map: (normalized_artist, normalized_title) -> mbid
    song_map = {}
    for song in gui_songs:
        artist = normalize_str(song.get("artist", ""))
        title = normalize_str(song.get("title", ""))
        mbid = song.get("mbid", "")
        if artist and title and mbid:
            song_map[(artist, title)] = mbid

    # Load Spotify JSON
    try:
        with open(spotify_path, "r") as f:
            spotify_data = json.load(f)
    except Exception as e:
        print(f"Error reading Spotify history file: {str(e)}")
        sys.exit(1)

    if not isinstance(spotify_data, list):
        print("Error: Spotify history JSON must contain a top-level list of listen items.")
        sys.exit(1)

    translated_list = []
    matched_count = 0
    total_count = 0

    for item in spotify_data:
        total_count += 1
        # Detect format: Standard (artistName, trackName) or Extended (master_metadata_...)
        artist = item.get("artistName") or item.get("master_metadata_album_artist_name")
        title = item.get("trackName") or item.get("master_metadata_track_name")

        if not artist or not title:
            continue

        norm_artist = normalize_str(artist)
        norm_title = normalize_str(title)

        mbid = song_map.get((norm_artist, norm_title))
        if mbid:
            matched_count += 1
            # Compile ListenBrainz pseudo JSON mapping format
            translated_list.append({
                "track_metadata": {
                    "mbid_mapping": {
                        "recording_mbid": mbid
                    }
                }
            })

    # Write output JSON
    try:
        with open(output_path, "w") as f:
            json.dump(translated_list, f, indent=4)
        print(f"Successfully converted Spotify history! Matched {matched_count} / {total_count} streams to library MBIDs. Saved to: {output_path}")
    except Exception as e:
        print(f"Error writing translated file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
