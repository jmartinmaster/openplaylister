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

seed=`od -A n -l -N 4 /dev/urandom | tr -d ' '`
fairseq-interactive --path checkpoints/brainz/checkpoint_last.pt data-bin/brainz --task language_modeling --skip-invalid-size-inputs-valid-test --seed $seed --prefix-size 10 --sampling --nbest 1 --beam 1 --min-len 100 --gen-subset train "$@"

