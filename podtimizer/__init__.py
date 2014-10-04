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

import argparse
import functools
import logging
import os
import re
import sys

from podtimizer.files import MusicFileCollection
from podtimizer.scrobblings import ScrobblingCollection
from podtimizer.algorithms import SongRank

__version__ = "0.1.dev"

SIZE_UNITS = {
    "K": 1024,
    "M": 1024 ** 2,
    "G": 1024 ** 3,
    "T": 1024 ** 4,
    "P": 1024 ** 5
}


def parse_size(size):
    tokens = re.split(r'([0-9.]+)', size)
    components = [s.strip() for s in tokens if s and not s.isspace()]

    if len(components) == 1:
        if components[0].isdigit():
            return int(components[0])
        else:
            raise argparse.ArgumentTypeError("Size specified in bytes must be an integer.")

    if len(components) != 2:
        raise argparse.ArgumentTypeError("You must specify a size unit when using decimals.")

    try:
        return int(float(components[0]) * SIZE_UNITS[components[1]])
    except KeyError:
        raise argparse.ArgumentTypeError("Invalid size unit '%s'." % components[1])


DEFAULT_SETTINGS = {
    'DATABASE': os.path.expanduser('~/.podtimizer/db/{}_scrobblings.db.sqlite3')
}


class Settings():

    def __init__(self):
        self.load_defaults()
        self.parse_args()

    def load_defaults(self):
        self.settings = DEFAULT_SETTINGS.copy()

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Generate a playlist.")
        parser.add_argument(
            '-m', '--music-dirs',
            nargs='+',
            metavar='dir',
            required=True,
            dest='MUSIC_DIRS',
            help="directories to scan for music files"
        )
        parser.add_argument(
            #'output-file',
            nargs='?',
            metavar='output-file',
            type=functools.partial(open, mode='w'),
            default=sys.stdout,
            dest='OUTPUT_FILE',
            help="file to write the resulting playlist (default is stdout)"
        )
        parser.add_argument(
            '-u', '--username',
            metavar='name',
            required=True,
            dest='USERNAME',
            help="last.fm username whose scrobblings will be fetched and analyzed"
        )
        parser.add_argument(
            '-s', '--max-size',
            type=parse_size,
            metavar='size',
            required=True,
            dest='MAX_SIZE',
            help="maximum combined size in bytes (or larger units) of music files of output"
                 " playlist, e.g. 100, 200M, 3.5G"
        )
        parser.add_argument(
            '--version',
            action='version',
            version="podtimizer %s" % __version__
        )
        self.settings.update(vars(parser.parse_args()))

    def __getattr__(self, name):
        try:
            return self.settings[name.upper()]
        except KeyError:
            raise AttributeError("No such setting '%s'" % name)


def main():
    settings = Settings()
    logging.getLogger().setLevel('INFO')

    scrobc = ScrobblingCollection(settings.username, settings.database)
    mfilec = MusicFileCollection()

    for dir in settings.music_dirs:
        mfilec.scan_directory(dir)

    scrobc.sync()

    songrank = SongRank(mfilec, scrobc)
    playlist = songrank.generate_playlist(settings.max_size)
    playlist.to_m3u(settings.output_file)
