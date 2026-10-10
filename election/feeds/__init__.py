"""election/feeds - the Election Night feed: news headlines with links, official posts, and counts of everyone else.

The plan is election/ARCHITECTURE.md (sections 2.3, 3.3, 4.3 to 4.5). The groundwork (phase 1) is here:

    outlets.py    the 145 news feeds the scouts found answering (election/scout/feeds.json), and the ones that refused
    accounts.py   official social accounts (newsrooms, election offices, candidates), each with two anchors and a date
    keywords.py   what each race is called in a headline: candidates' names, office and district words, places; and the
                  list of names that collide, with the rule used for each

The collectors (gdelt, rss, bluesky, mastodon, youtube), placing (geotag) and the measures come in phase 4. GDELT is
read only from its raw 15-minute files (data.gdeltproject.org/gdeltv2/lastupdate.txt and the zips it names): its
search API answers this machine 429 and is on source.py's never list.

Posts are counted, never shown, until John gives the site's public contact address (decision D8; see
accounts.posts_may_be_shown()).

Everything is written to night_feed_2026.sqlite (ignored by git, as every .sqlite is). Nothing about an ordinary
account is ever written there: no id, handle, text or post id. Only counts.
"""

import os
import sqlite3

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(HERE, "night_feed_2026.sqlite")
CACHE = os.path.join(HERE, "election_cache", "feeds")


def connect(path=None):
    """The feed database, created on first use. Each module adds its own tables with CREATE TABLE IF NOT EXISTS."""
    con = sqlite3.connect(path or DB)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def ro(path):
    """A read-only connection to one of the kit's databases (the ballot and record databases are never written)."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
