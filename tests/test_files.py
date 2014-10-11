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

import unittest
import os

from podtimizer.files import MusicFile


class TestFiles(unittest.TestCase):

    def setUp(self):
        self.real_mp3 = os.path.join("test", "data", "real_file.mp3")
        self.insufficient_mp3 = os.path.join("test", "data", "insufficient.mp3")
        self.fake_mp3 = os.path.join("test", "data", "not_a_music_file.jpeg")

    def test_musicfile(self):
        self.assertRaises(MusicFile.InsufficientMetadata, MusicFile, self.insufficient_mp3)
        self.assertRaises(MusicFile.UnknownFormat, MusicFile, self.fake_mp3)
        self.assertRaises(FileNotFoundError, MusicFile, "potato")
        mfile = MusicFile(self.real_mp3)
        self.assertIsInstance(mfile, MusicFile)
        self.assertEqual(mfile.name, ("Calenay", "Test And The Bungo", "Silence"))
        self.assertEqual(mfile.name_normalized, ("calenay", "testandthebungo", "silence"))
        self.assertEqual(mfile.filename, self.real_mp3)
        self.assertEqual(mfile.mbid, None)

    # MusicFileCollection and Playlist are too simple to be tested
    # And they involve interacting with the outside world, so mocking would probably be needed.
    # Screw that.
