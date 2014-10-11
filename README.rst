podtimizer
==========

podtimizer solves the problem of selecting which songs to sync to a mobile device given a music
library that is much larger than the device's capacity. Using your Last.fm scrobbling data
it attempts to pick the 'best' songs and generates a M3U playlist where the song's sizes sum at
most the given maximum size.

This means it *requires* to have a Last.fm account with plenty of scrobblings. Otherwise it won't
be of much use.

It attempts to balance the result with songs that you have recently listened to many times (short
term trending songs), and songs that you have listened to less often but consistently over time
(long term trending songs). The idea is that your favorites always stay in the list even if you
haven't listened to them recently, but also gives a chance for newer songs that haven't had time to
record many scrobblings to make the cut.

The generated playlist is intended to be imported into your favorite media player and use it to
sync your device. The M3U format is understood by most media players. This also gives you the
chance to review the selected songs and alter the list however you see fit.


Usage
-----

Basic usage is as follows:

  $ podtimizer --music-dirs dir --username name --max-size size

This will attempt to find all music files in the given dir, recursively. Then will query Last.fm
to retrieve all scrobblings associated with the given user, analyze them, and then output to
stdout the playlist in M3U format.

Retrieved scrobblings are cached in ~/.podtimizer so future runs only need to fetch the most recent
ones.

For all available options run:

  $ podtimizer --help


Caveats
-------

Last.fm only allows to retrieve at most 200 scrobblings per query, so the first run might take a
while. The next runs only retrieve scrobblings that have ocurred after the date of the last cached
scrobbling.

The music directories are always completely scanned. If your library is too large, this might take
a few minutes.


Future functionality
--------------------

Before calling this a 1.0 version, I'd like to implement the following functionality:

- A caching mechanism to speed up the music directory scanning.
- A minimal Qt-based GUI.
- Additional options to tune the balance of short-term/long-term during playlist generation.


Full options reference
----------------------


  $ podtimizer.py [-h] -m dir [dir ...] -u name -s size [--version] [-v] [output-file]


*output-file* file to write the resulting playlist (default is stdout)

-h, --help
    show this help message and exit

-m dir, --music-dirs dir
    directories to scan for music files

-u name, --username name
    last.fm username whose scrobblings will be fetched and analyzed

-s size, --max-size size
    maximum combined size in bytes (or larger units) of music files of output playlist,
    e.g. 100, 200M, 3.5G

--version
    show program's version number and exit

-v, --verbose
    make output very verbose
