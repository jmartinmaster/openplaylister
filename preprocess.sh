#!/bin/bash
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


mbids=`cat $1 | jq '.[].track_metadata.mbid_mapping.recording_mbid' | sed -e 's/"//g'`

# reverse the list (default sort order is reverse chrono)
mbids=`echo $mbids | awk '{ for (i=NF; i>1; i--) printf("%s ",$i); print $1; }'`

len=$((`echo -e ${mbids} | wc -w`))

test_len=$(expr $((len)) / 10)
valid_len=$((test_len))
train_len=$(expr $((len)) - $((test_len)) - $((valid_len)))

# Clean up from previous runs to prevent appending data or fairseq FileExistsError
rm -f train.txt test.txt valid.txt
rm -rf data-bin/brainz

i=0

for mbid in ${mbids}
do
    if [[ $((i)) -lt $((train_len)) ]]; then 
        echo -ne "${mbid} " >> train.txt
        if [[ $(($i%20)) -eq 0 ]]; then 
            echo  >> train.txt
        fi
    fi    

    if [[ $((i)) -ge $((train_len))  && $i -lt $(expr $((train_len)) + $((test_len))) ]]; then
        echo -ne "${mbid} " >> test.txt
        if [[ $(($i%20)) -eq 0 ]]; then 
            echo >> test.txt
        fi
    fi

    if [[ $((i)) -ge $(expr $((train_len))+$((test_len))) &&  $((i)) -lt $((len)) ]]; then
        echo -ne "${mbid} " >> valid.txt
        if [[ $(($i%20)) -eq 0 ]]; then 
            echo  >> valid.txt
        fi
    fi
    
    i=$((i+1))
done

# Ensure files exist even if they are empty so sed doesn't fail
touch train.txt test.txt valid.txt

sed -i 's/null //g' train.txt
sed -i 's/null //g' test.txt
sed -i 's/null //g' valid.txt

fairseq-preprocess \
    --only-source \
    --trainpref train.txt \
    --validpref valid.txt \
    --testpref test.txt \
    --destdir data-bin/brainz \
    --workers 20
