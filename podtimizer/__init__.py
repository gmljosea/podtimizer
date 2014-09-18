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
import re
import sys

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


class Settings():

    def __init__(self):
        parser = argparse.ArgumentParser(description="Generate a playlist.")
        parser.add_argument(
            '-m', '--music-dirs',
            nargs='+',
            metavar='dir',
            required=True,
            help="directories to scan for music files"
        )
        parser.add_argument(
            'output-file',
            nargs='?',
            type=open,
            default=sys.stdout,
            help="file to write the resulting playlist (default is stdout)"
        )
        parser.add_argument(
            '-u', '--username',
            metavar='name',
            required=True,
            help="last.fm username whose scrobblings will be fetched and analyzed"
        )
        parser.add_argument(
            '-s', '--max-size',
            type=parse_size,
            metavar='size',
            required=True,
            help="maximum combined size in bytes (or larger units) of music files of output"
                 " playlist, e.g. 100, 200M, 3.5G"
        )
        parser.add_argument(
            '--version',
            action='version',
            version="podtimizer %s" % __version__
        )
        self.settings = vars(parser.parse_args())

    def __getattr__(self, name):
        try:
            self.settings[name]
        except KeyError:
            raise AttributeError("No such setting '%s'" % name)

    def dump_settings(self):
        return self.settings


settings = Settings()


def main():
    print(settings.dump_settings())
