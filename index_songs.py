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


import mutagen
import glob
import json
import sys

id_to_file = {}
base_path=""
if len(sys.argv) == 2:
    base_path = sys.argv[1]
else:
    print("Pass the path to your music collection to this script")
    sys.exit(-22)
for file in glob.glob(base_path + "/*.mp3", recursive=True):
    try:
        taginfo = mutagen.File(file)
        if taginfo is not None:
                mbid = taginfo["TXXX:MusicBrainz Release Track Id"].text[0]
                print(mbid)
                if mbid is not None:
                    id_to_file[mbid] = file
    except:
        continue

for file in glob.glob("*.flac", recursive=True):
    try:
        taginfo = mutagen.File(file)
        if taginfo is not None:
                mbid = taginfo["musicbrainz_trackid"][0]
                print(mbid)
                if mbid is not None:
                    id_to_file[mbid] = file
    except:
        continue

with open("file_index.json", "w") as f:
    f.write(json.dumps(id_to_file))
