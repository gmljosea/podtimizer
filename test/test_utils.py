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
import uuid

from podtimizer.utils import normalize, validate_mbid


class TestUtils(unittest.TestCase):

    def test_normalize(self):
        self.assertEqual(normalize("Dragonforce  "), "dragonforce")
        self.assertEqual(normalize("Altaria (super remix)"), "altariasuperremix")
        self.assertEqual(normalize("Armin van Buuren (feat. Sharon)"), "arminvanbuuren")
        self.assertEqual(normalize(None), None)

    def test_validate_mbid(self):
        mbid = str(uuid.uuid4())
        self.assertEqual(validate_mbid(mbid), mbid)
        self.assertEqual(validate_mbid(mbid + " "), mbid)
        self.assertEqual(validate_mbid("potato"), None)
