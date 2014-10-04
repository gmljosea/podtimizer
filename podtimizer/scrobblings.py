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

from collections import deque
from datetime import datetime
import logging
import os
import requests
import sqlite3

from pytz import utc

from podtimizer.utils import normalize, err_print


SCROBBLING_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS Scrobbling (
        artist TEXT NULL,
        artistMBID TEXT NULL,
        album TEXT NULL,
        albumMBID TEXT NULL,
        track TEXT NULL,
        trackMBID TEXT NULL,
        date INTEGER NOT NULL,
        CONSTRAINT pk_track UNIQUE (artist, artistMBID, album, albumMBID, track, trackMBID, date),
        CONSTRAINT enough_metadata CHECK (track IS NOT NULL OR trackMBID IS NOT NULL)
    );"""
LAST_DATE_SQL = "SELECT date FROM Scrobbling ORDER BY date DESC LIMIT 1;"
INSERT_SCROBBLING_SQL = "INSERT INTO SCROBBLING VALUES (?,?,?,?,?,?,?)"
ALL_SCROBBLINGS_SQL = "SELECT * FROM SCROBBLING"


def empty_to_none(string):
    return string if len(string) > 0 else None


class Scrobbling():
    def __init__(self, artist, artist_mbid, album, album_mbid, track, track_mbid, date):

        self.artist = artist
        self.artist_norm = normalize(artist)
        self.artist_mbid = artist_mbid

        self.album = album
        self.album_norm = normalize(album)
        self.album_mbid = album_mbid

        self.track = track
        self.track_norm = normalize(track)
        self.track_mbid = track_mbid

        self.date = datetime.fromtimestamp(date, utc)

    def row(self):
        return (
            self.artist, self.artist_mbid,
            self.album, self.album_mbid,
            self.track, self.track_mbid,
            self.date.timestamp()
        )

    def __str__(self):
        return str(self.row())


class ScrobblingCollection():

    def __init__(self, username, db_format):
        self.username = username
        self.db_name = db_format.format(username)
        os.makedirs(os.path.split(self.db_name)[0], exist_ok=True)
        self.db = sqlite3.connect(self.db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.db.execute(SCROBBLING_SCHEMA_SQL)
        self.all = deque()

        for row in self.db.execute(ALL_SCROBBLINGS_SQL):
            self.all.append(Scrobbling(*tuple(row)))

    def get_most_recent_date(self):
        r = self.db.execute(LAST_DATE_SQL).fetchone()
        return r[0] if r is not None else 0

    def sync(self):
        err_print("Starting scrobblings sync for user", self.username)
        last_date = self.get_most_recent_date()

        for scrobbling in Lastfm.get_recent_tracks(starting_from=last_date, username=self.username):
            try:
                self.db.execute(INSERT_SCROBBLING_SQL, scrobbling.row())
                logging.debug("Added scrobbling {}".format(scrobbling))
                self.all.append(scrobbling)
            except sqlite3.IntegrityError:
                logging.debug("Skipping duplicate scrobbling {}".format(scrobbling))
            self.db.commit()
        err_print("Finished sync")

    def __del__(self):
        self.db.close()


class Lastfm():

    API_KEY = "e4f145a5cd3f3781bf6dbd17d2019e3e"
    API_URL = "http://ws.audioscrobbler.com/2.0/"
    TIMEOUT = 10

    class APIException(Exception):
        pass

    @classmethod
    def get_recent_tracks(cls, username, starting_from=0):

        api_params = {
            "method": "user.getrecenttracks",
            "user": username,
            "from": starting_from,
            "page": 2000000000,
            "limit": 200,
            "format": "json"
        }

        while True:
            try:
                data = cls.call_api(api_params)
            except Lastfm.APIException:
                logging.error("Failed API call.")
                logging.error("Aborting sync, will work with whatever we have.")
                break

            if "recenttracks" not in data:
                logging.error("Unexpected response format from Last.fm")
                logging.debug("Last.fm returned {}".format(data))
                logging.error("Aborting sync, will work with whatever we have.")
                break

            if "@attr" not in data["recenttracks"]:
                break

            tracks_left = data["recenttracks"]["@attr"]["total"]
            err_print(tracks_left, "scrobblings left to sync")

            if not isinstance(data["recenttracks"]["track"], list):
                data["recenttracks"]["track"] = [data["recenttracks"]["track"]]

            for track_data in reversed(data["recenttracks"]["track"]):

                if "@attr" in track_data and "nowplaying" in track_data["@attr"]:
                    # We've already reached a 'now playing' track, skip it and end the
                    # whole call.
                    break

                artist = empty_to_none(track_data.get("artist", {}).get("#text", ""))
                artist_mbid = empty_to_none(track_data.get("artist", {}).get("mbid", ""))
                album = empty_to_none(track_data.get("album", {}).get("#text", ""))
                album_mbid = empty_to_none(track_data.get("album", {}).get("mbid", ""))
                track = empty_to_none(track_data.get("name", ""))
                track_mbid = empty_to_none(track_data.get("mbid", ""))
                date = int(track_data.get("date", {}).get("uts", 0))

                if date == 0 or (track is None and track_mbid is None):
                    logging.debug("Skipping scrobbling with insufficient metadata.")
                    continue

                api_params["from"] = date

                yield Scrobbling(
                    artist=artist, artist_mbid=artist_mbid,
                    album=album, album_mbid=album_mbid,
                    track=track, track_mbid=track_mbid,
                    date=date
                )

    @classmethod
    def call_api(cls, params, max_attempts=10):
        params["api_key"] = cls.API_KEY
        for i in range(max_attempts):
            if i > 1:
                logging.error("Retrying...")
            try:
                r = requests.get(cls.API_URL, params=params, timeout=(cls.TIMEOUT, cls.TIMEOUT))
                if r.status_code != requests.codes.ok:
                    logging.error("API HTTP error {} - {}".format(r.status_code, r.reason))
                    continue
                json = r.json()
                if "error" in json:
                    logging.error("API error {} - {}".format(json["error"], json["messages"]))
                else:
                    return json
            except requests.exceptions.Timeout:
                logging.error("API call timed out.")
        raise Lastfm.APIException()
