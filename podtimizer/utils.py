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
import sys
import uuid


def empty(val):
    return '' if val is None else val


def normalize(name):
    """
    Lowercases, removes non-alphanumeric characters and removes 'featured artists' of the form
    (feat. x).
    It returns None if the argument is None, or if the argument only has whitespace.
    """
    if name is None or len(name.strip()) == 0:
        return None

    name = name.strip().lower()
    name = re.sub(r"\s+\(feat. [^)]*\)", "", name, flags=re.IGNORECASE | re.UNICODE)
    name = re.sub(r"\W+", "", name, flags=re.IGNORECASE | re.UNICODE)

    return name


def validate_mbid(mbid):
    """
    Returns an mbid if the argument is a valid mbid, None otherwise.
    Any prepended or appended whitespace is removed.
    """
    try:
        return str(uuid.UUID(mbid.strip()))
    except ValueError:
        return None


def err_print(*args):
    print(*args, file=sys.stderr)
