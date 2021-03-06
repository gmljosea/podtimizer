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

from collections import deque
from datetime import datetime
import logging
import os
import pickle
import sys
import sqlite3

import mutagen

from podtimizer.utils import normalize, validate_mbid, err_print, make_database


MUSIC_FILE_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS MusicFile (
        filename TEXT NOT NULL UNIQUE,
        mtime FLOAT NOT NULL,
        music_file BLOB NULL
    );"""

INSERT_MUSIC_FILE_SQL = "INSERT OR REPLACE INTO MusicFile VALUES (?,?,?)"
SELECT_MUSIC_FILE_SQL = "SELECT * FROM MusicFile WHERE filename=?"


class MetadataCache():

    class TrashFile(Exception):
        pass

    def __init__(self, db_name):
        self.db = make_database(db_name, MUSIC_FILE_SCHEMA_SQL)

    def get_file(self, filename, mtime):
        for row in self.db.execute(SELECT_MUSIC_FILE_SQL, (filename, )):
            if row[2] is None:
                raise MetadataCache.TrashFile()
            if datetime.fromtimestamp(mtime) >= datetime.fromtimestamp(row[1]):
                return pickle.loads(row[2])
        return None

    def store_file(self, filename, mtime, music_file, update=True):
        mfile = pickle.dumps(music_file) if music_file is not None else None
        self.db.execute(INSERT_MUSIC_FILE_SQL, (filename, mtime, mfile))


class MusicFile():
    """
    A music file in the file system and its associated metadata

    Given a filename, its artist, album, track and MBID data is extracted and normalized.

    A Music File always has at least a track name or a track MBID.

    Normalized names are all lowercase, only contain alphanumeric characters, and have 'featured
    artist' removed.

    It exposes the following properties:
    - name: tuple of (artist, album, track). Artist and album might be None.
    - name_normalized: tuple of (artist, album, track) all normalized.
    - mbid: track MBID, if any.
    - filename: location in the filesystem.
    """

    class InsufficientMetadata(Exception):
        pass

    class UnknownFormat(Exception):
        pass

    def __init__(self, filename):
        """
        Create a MusicFile using the given filename. If it is a music file whose metadata can be
        understood by Mutagen, it will be extrated and processed.

        If the file can't be understood by Mutagen, a MusicFile.UnknownFormat exception will be
        thrown.

        If the file doesn't have at least a track name or a track MBID, a
        MusicFile.InsufficientMetadata exception will be thrown.
        """
        try:
            metadata = mutagen.File(filename, easy=True)
        except mutagen.mp3.HeaderNotFoundError:
            raise MusicFile.UnknownFormat()

        if metadata is None:
            raise MusicFile.UnknownFormat()

        self.filename = filename
        self.size = os.path.getsize(filename)

        self.artist = MusicFile.extract_tag(metadata, "artist")
        self.artist_mbid = self.check_mbid(MusicFile.extract_tag(metadata, "musicbrainz_artistid"))
        self.artist_norm = normalize(self.artist)

        self.album = MusicFile.extract_tag(metadata, "album")
        self.album_mbid = self.check_mbid(MusicFile.extract_tag(metadata, "musicbrainz_albumid"))
        self.album_norm = normalize(self.album)

        self.track = MusicFile.extract_tag(metadata, "title")
        self.track_mbid = self.check_mbid(MusicFile.extract_tag(metadata, "musicbrainz_trackid"))
        self.track_norm = normalize(self.track)

        if self.track is None and self.track_mbid is None:
            raise MusicFile.InsufficientMetadata()

        # Careful here. Mutagen right now includes a info property in all its formats, and each
        # of them includes a length field in seconds (except ASF files, whatever they are)
        self.length = metadata.info.length

    @property
    def name_normalized(self):
        return (self.artist_norm, self.album_norm, self.track_norm)

    @property
    def name(self):
        return (self.artist, self.album, self.track)

    @property
    def mbid(self):
        return self.track_mbid

    @staticmethod
    def extract_tag(meta, tag):
        return meta[tag][0] if tag in meta and len(meta[tag]) > 0 else None

    def check_mbid(self, mbid):
        return None if mbid is None else validate_mbid(mbid)

    def __str__(self):
        return "MusicFile: {}".format(self.filename)


class MusicFileCollection():
    """A collection of music files"""

    def __init__(self, cache_name):
        self.tracks_by_mbid = {}
        self.tracks_by_text = {}
        self.library = {}
        self.all_files = deque()
        self.cache = MetadataCache(cache_name)
        self.artist_mbid = {}

    def add_file(self, mfile):
        """Adds the MusicFile mfile to the collection"""
        artist, album, track = mfile.name_normalized
        self.all_files.append(mfile)
        self.tracks_by_text["{}{}{}".format(artist, album, track)] = mfile
        self.library.setdefault(artist, {}).setdefault(album, {})[track] = mfile

        if mfile.mbid is not None:
            self.tracks_by_mbid[mfile.mbid] = mfile

        if mfile.artist_mbid is not None:
            self.artist_mbid[artist] = mfile.artist_mbid


    def scan_directory(self, directory):
        """
        Recursively finds all files under directory and adds them to the collection if a MusicFile
        instance can be created for them.
        """
        err_print("Scanning", directory, "for music files.")
        for root, __, filenames in os.walk(directory):
            err_print("-- Scanning", root)
            for filename in filenames:
                full_filename = os.path.join(root, filename)
                mtime = os.stat(full_filename).st_mtime

                try:
                    cached_file = self.cache.get_file(full_filename, mtime)
                except MetadataCache.TrashFile:
                    logging.debug("Cache says {} is trash, ignoring.".format(filename))
                    continue

                if cached_file is not None:
                    logging.debug("Reading cached metadata of {}".format(filename))
                    self.add_file(cached_file)
                    continue

                try:
                    mfile = MusicFile(full_filename)
                    self.add_file(mfile)
                    self.cache.store_file(full_filename, mtime, mfile)
                except MusicFile.InsufficientMetadata:
                    logging.debug("Skipping {} due to insufficient metadata.".format(filename))
                    self.cache.store_file(full_filename, mtime, None)
                except MusicFile.UnknownFormat:
                    logging.debug("Not a music file {}-".format(filename))
                    self.cache.store_file(full_filename, mtime, None)

    def __len__(self):
        return len(self.all_files)


class Playlist():
    """A collection of music files that keeps the order in which they are added"""

    def __init__(self):
        self.mfiles = deque()

    def add_file(self, mfile):
        self.mfiles.append(mfile)

    def to_m3u(self, file):
        """
        Writes to filename a file containing the filename of each music file contained in this list,
        in order.
        """
        for mfile in self.mfiles:
            file.write(mfile.filename + "\n")
