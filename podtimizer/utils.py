# podtimizer, Last.fm-based playlist generator
# Copyright (C) 2014 José Alberto Goncalves Da Silva (gmljosea)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

import re
import uuid


def normalize(name, remove_feat=True):
    """
    Lowercases and removes non-alphanumeric characters.
    Optionally it removes everything after a 'feat.'.
    """
    name = name.strip().lower()

    if name is None or name == '':
        return None

    name = re.sub(r"\s+\(feat. [^)]*\)", "", name, flags=re.IGNORECASE | re.UNICODE)
    name = re.sub(r"\W+", "", name, flags=re.IGNORECASE | re.UNICODE)

    return name


def validate_mbid(mbid):
    """
    Returns an mbid if argument contains one, None otherwise.
    """
    try:
        return str(uuid.UUID(mbid.strip()))
    except ValueError:
        return None
