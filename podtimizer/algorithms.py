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

from collections import deque, Counter
import heapq
import Levenshtein as lev

from podtimizer.files import Playlist
from podtimizer.utils import empty, err_print


# This global var is used only within the workers that match scrobblings
MATCHER = None


def match_initializer(matcher):
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    global MATCHER
    MATCHER = mfilec


def match_job(tuple):
    artist, albums = tuple
    return MATCHER.match_artists(artist, albums)


def compute_distance(str1, str2):
    return lev.distance(str1, str2) * (1.1 - lev.jaro_winkler(str1, str2))


class Matcher():

    MAX_EDIT_DISTANCE = 2.0

    def __init__(self, mfilec, scrobc):
        self.mfilec = mfilec
        self.scrobc = scrobc
        self.mfile_to_scrobbles = {}
        self.scrobble_to_mfile = {}
        self.buckets = {}
        self.bucket_library = {}
        self.artist_mbids = {}

        # stats
        self.matched_by_mbid = 0
        self.matched_by_text = 0
        self.matched_by_distance = 0
        self.unmatched = 0

        for scrob in scrobc.all:
            mfile = self.mfilec.tracks_by_mbid.get(scrob.track_mbid, None)
            if mfile is not None:
                self.mfile_to_scrobbles.setdefault(mfile, deque()).append(scrob)
                self.matched_by_mbid += 1
                self.scrobble_to_mfile[scrob] = mfile
                continue
            mfile = self.mfilec.tracks_by_text.get(scrob.combined_name, None)
            if mfile is not None:
                self.mfile_to_scrobbles.setdefault(mfile, deque()).append(scrob)
                self.matched_by_text += 1
                self.scrobble_to_mfile[scrob] = mfile
            else:
                artist, album, track = scrob.artist_norm, scrob.album_norm, scrob.track_norm
                (self.bucket_library
                    .setdefault(artist, {})
                    .setdefault(album, {})
                    .setdefault(track, deque())
                    .append(scrob)
                )
                if scrob.artist_mbid is not None:
                    self.artist_mbids[artist] = scrob.artist_mbid
                self.buckets.setdefault(scrob.combined_name, deque()).append(scrob)

        pool = Pool(initializer=match_initializer, initargs=(self, ))
        print("Using {} cores".format(cpu_count()))

        for result in pool.map(match_job, self.bucket_library.items()):
            for mfile, bucket in result:
                if mfile is not None:
                    #print("Matched", mfile, "to", list(map(lambda x: x.row(), bucket)))
                    self.mfile_to_scrobbles.setdefault(mfile, deque()).extend(bucket)
                    self.scrobble_to_mfile[scrob] = mfile
                    self.matched_by_distance += len(bucket)
                else:
                    #print("Unmatched", list(map(lambda x: x.row(), bucket)))
                    self.unmatched += len(bucket)

    def match_artists(self, s_artist, s_albums):
        result = deque()
        candidates = deque()
        s_artist_mbid = self.artist_mbids.get(s_artist, None)
        for l_artist, l_albums in self.mfilec.library.items():
            l_artist_mbid = self.mfilec.artist_mbid.get(l_artist, None)

            if l_artist_mbid is None or s_artist_mbid is None:
                distance = 0.4 * compute_distance(l_artist, s_artist)
                if distance < Matcher.MAX_EDIT_DISTANCE:
                    candidates.append((distance, l_albums))
            elif l_artist_mbid == s_artist_mbid:
                candidates.append((0, l_albums))

        for s_album, s_tracks in s_albums.items():
            result.extend(self.match_albums(candidates, s_album, s_tracks))

        return result

    def match_albums(self, c_albums, s_album, s_tracks):
        candidates = deque()
        result = deque()
        for c_distance, l_albums in c_albums:
            for l_album, l_tracks in l_albums.items():
                distance = c_distance + 0.2 * compute_distance(l_album, s_album)
                if distance < Matcher.MAX_EDIT_DISTANCE:
                    candidates.append((distance, l_tracks))

        for s_track, bucket in s_tracks.items():
            match = self.match_tracks(candidates, s_track, bucket)
            if match is not None:
                result.append(match)
        return result

    def match_tracks(self, c_tracks, s_track, bucket):
        candidate, candidate_distance = None, 0

        for c_distance, l_tracks in c_tracks:
            for l_track, mfile in l_tracks.items():
                distance = c_distance + 0.4 * compute_distance(l_track, s_track)
                if candidate is None or distance < candidate_distance:
                    candidate, candidate_distance = mfile, distance

        return (candidate, bucket) if candidate_distance < Matcher.MAX_EDIT_DISTANCE else None


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
        err_print("Matched {} using track MBID".format(self.matcher.matched_by_mbid))
        err_print("Matched {} using track text metadata".format(self.matcher.matched_by_text))
        err_print("Matched {} using track string distance".format(self.matcher.matched_by_distance))
        err_print("{} unmatched".format(self.matcher.unmatched))
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
