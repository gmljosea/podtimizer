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

from __future__ import unicode_literals, division

from datetime import datetime
from math import sqrt
from multiprocessing import Pool, cpu_count
import logging

import pytz

from collections import deque
import heapq
import Levenshtein as lev

from podtimizer.files import Playlist
from podtimizer.utils import empty, err_print


class Matcher():

    MAX_EDIT_DISTANCE = 2.0

    def __init__(self, mfilec, scrobc):
        self.mfilec = mfilec
        self.scrobc = scrobc
        self.mfile_to_scrobbles = {}
        self.scrobble_to_mfile = {}
        self.unmatched_scrobblings = deque()

        # stats
        self.matched_by_mbid = 0
        self.matched_by_text = 0
        self.matched_by_distance = 0
        self.unmatched = 0

        pool = Pool()
        print("Using {} cores".format(cpu_count()))

        for scrob, mfile in pool.map(self.match, scrobc.all):
            if mfile is not None:
                self.mfile_to_scrobbles.setdefault(mfile, deque())
                self.mfile_to_scrobbles[mfile].append(scrob)
                self.scrobble_to_mfile[scrob] = mfile
            else:
                self.unmatched_scrobblings.append(scrob)
                self.unmatched += 1
                self.scrobble_to_mfile[scrob] = None

    def match(self, scrob):

        # Try direct track mbid match
        track_mbid = scrob.track_mbid
        if track_mbid is not None and track_mbid in self.mfilec.tracks_by_mbid:
            self.matched_by_mbid += 1
            return (scrob, self.mfilec.tracks_by_mbid[track_mbid])

        # Try normalized Artist,Album,Track search
        result = (
            self.mfilec.tracks_by_text
            .get(scrob.artist_norm, {})
            .get(scrob.album_norm, {})
            .get(scrob.track_norm, None)
        )
        if result is not None:
            self.matched_by_text += 1
            return (scrob, result)

        # Search all files and retrieve the most likely match, if any
        candidates, count = [], 0
        for mfile in self.mfilec.all_files:
            # Skip if artist mbid exist for both but don't match
            # Album mbid is skipped because it would be very weird to have the album mbid but NOT
            # the artist mbid. I mean, that really never happens.
            # Track mbid is skipped too because if there was a match, it would have been found
            # in the first check.
            if (
                mfile.artist_mbid is not None and
                scrob.artist_mbid is not None and
                mfile.artist_mbid != scrob.artist_mbid
            ):
                continue

            mfile_artist, scrob_artist = empty(mfile.artist_norm), empty(scrob.artist_norm)
            artist_dist = lev.distance(mfile_artist, scrob_artist)
            artist_dist *= 1.1 - lev.jaro_winkler(mfile_artist, scrob_artist)

            mfile_album, scrob_album = empty(mfile.album_norm), empty(scrob.album_norm)
            album_dist = lev.distance(mfile_album, scrob_album)
            album_dist *= 1.1 - lev.jaro_winkler(mfile_album, scrob_album)

            mfile_track, scrob_track = empty(mfile.track_norm), empty(scrob.track_norm)
            track_dist = lev.distance(mfile_track, scrob_track)
            track_dist *= 1.1 - lev.jaro_winkler(mfile_track, scrob_track)

            # The jaro-winkler metric is used to make strings with very similar prefixes closer
            # in distance. The closer the prefix, the closer the metric is to 1, and in consequence
            # the levenshtein distance will be scaled down.
            # The constant is 1.1 instead of 1 because when the strings have a very long common
            # prefix, jaro-winkler becomes 1.0. This makes two songs that are actually different,
            # but only differ by something minuscule at the end of the name, have a metric of 1.0,
            # which results in scaling levenshtein by 0. The .1 ensures the result is never 0 and
            # forces levenshtein to always be relevant.

            distance = 0.4 * artist_dist + 0.2 * album_dist + 0.4 * track_dist
            # Album distance is given less weight because often one song may appear in multiple
            # albums. Say, a regular album and a EP. We want both to be considered the same song.

            # The count is included in the heap to avoid heapq trying to compare for equality
            # two MusicFile instances if both have the same distance.
            heapq.heappush(candidates, (distance, count, mfile))
            count += 1

        (distance, __, candidate) = candidates[0]
        if distance < Matcher.MAX_EDIT_DISTANCE:
            self.matched_by_distance += 1
            logging.debug("Matched {} to {}".format(scrob, candidate))

            # Last resort. In edge cases, the best candidate might actually be the correct file,
            # but might have a distance larger than maximum. Here we do additional tests over the
            # best candidate and determine wether to match to it or not.

            # Cases:
            # - The track name actually includes the band's name before the actual track name.
            #   If the normalized scrobbling artist+track name is very similar to the normalized
            #   music file artist+track name, match it.
            # -
            return (scrob, candidate)
        else:
            logging.debug("Unmatched scrobbling {}".format(scrob))
            logging.debug("Best candidate was {} with {}".format(candidate, distance))
            return (scrob, None)


class TimeAverage():

    @staticmethod
    def decay(x):
        return 1.0 / sqrt(float(x))

    @staticmethod
    def multiply(x):
        return 5*x

    def __init__(self, matcher):
        self.timeavg_dict = {}
        for (mfile, scrobs) in matcher.mfile_to_scrobbles.items():
            today = datetime.now(pytz.utc)
            avg = sum(map(lambda s: TimeAverage.decay((today - s.date).days + 1), scrobs))
            avg = avg * 100 * TimeAverage.multiply(len(scrobs))
            self.timeavg_dict[mfile] = avg


class SongRank():
    def __init__(self, mfilec, scrobc):
        err_print("Matching scrobblings to local music files...")
        self.matcher = Matcher(mfilec, scrobc)
        logging.debug("Matched {} using track MBID".format(self.matcher.matched_by_mbid))
        logging.debug("Matched {} using track text metadata".format(self.matcher.matched_by_text))
        logging.debug("Matched {} using track string distance".format(self.matcher.matched_by_distance))
        logging.debug("{} unmatched".format(self.matcher.unmatched))
        err_print("Ranking music files...")
        self.timeavg = TimeAverage(self.matcher)

        self.mfilec = mfilec
        self.scrobc = scrobc

        self.sorted_rank = []
        count = 0
        for mfile, timeavg in self.timeavg.timeavg_dict.items():
            # heapq is a min heap. timeavg's sign must be inverted so the
            # largest time average becomes the smallest.
            heapq.heappush(self.sorted_rank, (-timeavg, count, mfile))
            count += 1

        self.rank_dict = {}
        count = 1
        for (timeavg, __, mfile) in self.sorted_rank:
            self.rank_dict[mfile] = (timeavg, count)
            count += 1

    def generate_playlist(self, max_bytes):
        playlist = Playlist()
        size_count = 0
        for (__, __2, mfile) in self.sorted_rank:
            if size_count + mfile.size <= max_bytes:
                playlist.add_file(mfile)
                size_count += mfile.size
        return playlist

    def recompute(self):
        self.__init__(self.mfilec, self.scrobc)
