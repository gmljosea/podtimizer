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

from __future__ import unicode_literals

import argparse
import codecs
import logging
import os
import re
import sys

from podtimizer.files import MusicFileCollection
from podtimizer.scrobblings import ScrobblingCollection, Lastfm
from podtimizer.algorithms import SongRank
from podtimizer.utils import err_print

__version__ = "0.2.dev"

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


def check_dir(dir):
    if not os.path.isdir(dir):
        raise argparse.ArgumentTypeError("{} doesn't exist or isn't a directory.".format(dir))
    return dir


def open_output(path):
    try:
        return codecs.open(path, mode="w", encoding="utf8")
    except OSError as e:
        raise argparse.ArgumentTypeError("Couldn't open output file: {}".format(str(e)))

def check_username(username):
    api_params = {
        "method": "user.getinfo",
        "user": username,
        "format": "json"
    }
    try:
        data = Lastfm.call_api(api_params, max_attempts=1)
    except Lastfm.APIException as e:
        err_print("Couldn't validate username:", e.response.get("message", "Unknown API exception"))
        sys.exit(2)


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
            type=check_dir,
            metavar='dir',
            required=True,
            dest='MUSIC_DIRS',
            help="directories to scan for music files"
        )
        parser.add_argument(
            #'output-file',
            nargs='?',
            metavar='output-file',
            type=open_output,
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
        parser.add_argument(
            '-v', '--verbose',
            action='count',
            default=0,
            dest="VERBOSITY",
            help="make output very verbose"
        )
        self.settings.update(vars(parser.parse_args()))

    def __getattr__(self, name):
        try:
            return self.settings[name.upper()]
        except KeyError:
            raise AttributeError("No such setting '%s'" % name)


def main():
    try:
        settings = Settings()

        if settings.verbosity > 0:
            logging.getLogger().setLevel('DEBUG')

        check_username(settings.username)

        scrobc = ScrobblingCollection(settings.username, settings.database)

        mfilec = MusicFileCollection()
        for dir in settings.music_dirs:
            mfilec.scan_directory(dir)

        if len(mfilec) == 0:
            err_print("No music files were found.")
            sys.exit(0)

        scrobc.sync()

        if len(scrobc) == 0:
            err_print("No scrobblings were found.")
            sys.exit(0)

        songrank = SongRank(mfilec, scrobc)
        playlist = songrank.generate_playlist(settings.max_size)
        playlist.to_m3u(settings.output_file)
    except KeyboardInterrupt:
        sys.exit(1)
