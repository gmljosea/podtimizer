# podtimizer, Last.fm-based playlist generator
# Copyright (C) 2014 Jose Alberto Goncalves Da Silva (gmljosea)
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

from __future__ import print_function, unicode_literals

import logging
import os
import re
import sqlite3
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
        return ""

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


def make_database(filename, schema_sql):
    def _connect(filename, schema_sql):
        db = sqlite3.connect(
            filename,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            isolation_level=None
        )
        # Our databases are nothing more than caches so we can drop some contraints to gain speed
        db.execute("PRAGMA synchronous = 0")
        db.execute(schema_sql)
        return db

    try:
        path = os.path.split(filename)[0]
        not os.path.exists(path) and os.makedirs(path)
        # We could use exist_ok in makedirs, but 2.7 doesn't support it.
    except OSError:
        # Well, screw you, get a memory database instead
        logging.error("Couldn't create dir for database {}, using memory instead.".format(filename))
        return _connect(":memory:", schema_sql)

    try:
        return _connect(filename, schema_sql)
    except sqlite3.DatabaseError:
        logging.error("Old database {} was corrupted, recreating.".format(filename))

    try:
        os.remove(filename)
        return _connect(filename, schema_sql)
    except OSError:
        logging.error("Couldn't delete {}, using memory instead.".format(filename))
        return _connect(":memory:", schema_sql)
    except sqlite3.DatabaseError:
        logging.error("Couldn't recreate database {}, using memory instead.".format(filename))
        return _connect(":memory:", schema_sql)
