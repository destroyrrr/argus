# services/media_bot_commands.py
import asyncio
from core.auth import get_bot_secrets
import mysql.connector

# ---------------------------
# DB Connection
# ---------------------------
def get_db_connection():
    secrets = get_bot_secrets()
    return mysql.connector.connect(
        host=secrets["DB_HOST"],
        user=secrets["DB_USER"],
        password=secrets["DB_PASSWORD"],
        database=secrets["DB_NAME"]
    )


# ---------------------------
# Helpers
# ---------------------------
def format_block(lines):
    return "```\n" + "\n".join(lines) + "\n```"


# ---------------------------
# Commands
# ---------------------------
def movie_search(*args):
    title = " ".join(args)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, release_year, media_type, resolution
            FROM movies
            WHERE title LIKE %s
            ORDER BY release_year
        """, (f"%{title}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ `{title}` not found in your library."

        lines = []
        for title, year, media_type, resolution in rows:
            year_str = str(year) if year else "Unknown"
            res_str  = f" [{resolution}]" if resolution else ""
            lines.append(f"✅ {title} ({year_str}) {media_type}{res_str}")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"


def movie_year(year):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, release_year, media_type, resolution
            FROM movies
            WHERE release_year = %s
            ORDER BY title
        """, (year,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ No movies found from `{year}`."

        lines = []
        for title, year, media_type, resolution in rows:
            res_str = f" [{resolution}]" if resolution else ""
            lines.append(f"✅ {title} ({year}) {media_type}{res_str}")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"


def tv_search(*args):
    title = " ".join(args)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.name, COUNT(e.id) AS total_episodes, s.media_type
            FROM tv_shows s
            JOIN tv_seasons se ON se.show_id = s.id
            JOIN tv_episodes e  ON e.season_id = se.id
            WHERE s.name LIKE %s
            GROUP BY s.name, s.media_type
            ORDER BY s.name
        """, (f"%{title}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ `{title}` not found in your library."

        lines = []
        for name, total_episodes, media_type in rows:
            lines.append(f"✅ {name} {media_type} — {total_episodes} episodes")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"


def music_search(*args):
    query = " ".join(args)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, audio_codec, bitrate
            FROM tracks
            WHERE title LIKE %s
            ORDER BY title
        """, (f"%{query}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ `{query}` not found in your library."

        lines = []
        for title, codec, bitrate in rows:
            codec_str   = f" {codec}"   if codec   else ""
            bitrate_str = f" {bitrate}kbps" if bitrate else ""
            lines.append(f"✅ {title}{codec_str}{bitrate_str}")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"


def media_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM movies")
        movie_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tv_shows")
        show_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tv_episodes")
        episode_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tracks")
        track_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        lines = [
            f"Movies:      {movie_count}",
            f"TV Shows:    {show_count}",
            f"TV Episodes: {episode_count}",
            f"Tracks:      {track_count}",
            f"Total:       {movie_count + show_count + episode_count + track_count}",
        ]
        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"

def movie_genre(*args):
    genre = " ".join(args).strip('"').strip("'")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, release_year, media_type, genre
            FROM movies
            WHERE genre LIKE %s
            ORDER BY release_year
        """, (f"%{genre}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ No movies found for genre `{genre}`."

        lines = []
        for title, year, media_type, genre in rows:
            year_str = str(year) if year else "Unknown"
            lines.append(f"✅ {title} ({year_str}) {media_type}")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"


def movie_director(*args):
    director = " ".join(args).strip('"').strip("'")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, release_year, media_type, director
            FROM movies
            WHERE director LIKE %s
            ORDER BY release_year
        """, (f"%{director}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return f"❌ No movies found for director `{director}`."

        lines = []
        for title, year, media_type, director in rows:
            year_str = str(year) if year else "Unknown"
            lines.append(f"✅ {title} ({year_str}) {media_type}")

        return format_block(lines)

    except Exception as e:
        return f"❌ DB error: {e}"

# ---------------------------
# Exports
# ---------------------------
COMMAND_MAP = {
    "movie":    {"func": movie_search,   "help": "Search movies by title.",       "args": "<title>",    "tier": 0},
    "year":     {"func": movie_year,     "help": "List movies by release year.",  "args": "<year>",     "tier": 0},
    "genre":    {"func": movie_genre,    "help": "Search movies by genre.",       "args": "<genre>",    "tier": 0},
    "director": {"func": movie_director, "help": "Search movies by director.",    "args": "<name>",     "tier": 0},
    "tv":       {"func": tv_search,      "help": "Search TV shows by title.",     "args": "<title>",    "tier": 0},
    "music":    {"func": music_search,   "help": "Search music by title.",        "args": "<query>",    "tier": 0},
    "stats":    {"func": media_stats,    "help": "Show total counts for all media.", "args": "",        "tier": 0},
}
