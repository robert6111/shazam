import hashlib

import pymysql


# Keep the exact same database connection already used by the local
# WorldVeil fingerprint store/recognizer.
DB_CONFIG = {
    "host": "localhost",
    "user": "worldveil",
    "password": "strongpassword",
    "database": "worldveil_db"
}


def connect():
    return pymysql.connect(**DB_CONFIG)


def _make_recognition_key(source, title, artist, acrid=None, isrc=None, local_song_id=None):
    """Build a stable unique key for one recognized song."""
    if source == "local" and local_song_id is not None:
        return f"local:{local_song_id}"

    if acrid and acrid != "N/A":
        return f"acr:{acrid}"

    if isrc and isrc != "N/A":
        return f"isrc:{isrc}"

    raw_key = f"{source}::{title.strip().lower()}::{artist.strip().lower()}"
    return "song:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _ensure_tables(cur):
    """Create the listen-counter tables when they do not yet exist."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recognized_songs (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            recognition_key VARCHAR(255) NOT NULL UNIQUE,
            source VARCHAR(20) NOT NULL,
            source_song_id BIGINT NULL,
            acrid VARCHAR(100) NULL,
            isrc VARCHAR(100) NULL,
            title VARCHAR(255) NOT NULL,
            artist VARCHAR(255) NOT NULL,
            album VARCHAR(255) NULL,
            listen_count BIGINT UNSIGNED NOT NULL DEFAULT 1,
            first_listened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_listened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_recognized_source (source),
            INDEX idx_recognized_acrid (acrid),
            INDEX idx_recognized_isrc (isrc),
            INDEX idx_recognized_title (title),
            INDEX idx_recognized_artist (artist),
            INDEX idx_recognized_listen_count (listen_count)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recognition_history (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            song_id BIGINT UNSIGNED NOT NULL,
            source VARCHAR(20) NOT NULL,
            recognition_score DECIMAL(10,2) NULL,
            recognized_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_recognition_history_song
                FOREIGN KEY (song_id)
                REFERENCES recognized_songs(id)
                ON DELETE CASCADE,
            INDEX idx_history_song_id (song_id),
            INDEX idx_history_source (source),
            INDEX idx_history_recognized_at (recognized_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def record_recognition(
    source,
    title,
    artist="Unknown",
    album=None,
    score=None,
    acrid=None,
    isrc=None,
    local_song_id=None,
):
    """
    Record one successful recognition in MySQL.

    First recognition:
        listen_count = 1
        status = FIRST TIME LISTENED

    Later recognitions:
        listen_count increases by 1
        last_listened_at is updated
        status = LISTEN COUNT UPDATED

    Every successful recognition is also inserted into recognition_history.
    """
    recognition_key = _make_recognition_key(
        source=source,
        title=title,
        artist=artist,
        acrid=acrid,
        isrc=isrc,
        local_song_id=local_song_id,
    )

    try:
        score_value = float(score) if score not in (None, "N/A") else None
    except (TypeError, ValueError):
        score_value = None

    conn = None
    cur = None

    try:
        conn = connect()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        _ensure_tables(cur)

        cur.execute(
            """
            INSERT INTO recognized_songs (
                recognition_key,
                source,
                source_song_id,
                acrid,
                isrc,
                title,
                artist,
                album,
                listen_count,
                first_listened_at,
                last_listened_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                id = LAST_INSERT_ID(id),
                source = VALUES(source),
                source_song_id = COALESCE(VALUES(source_song_id), source_song_id),
                acrid = COALESCE(VALUES(acrid), acrid),
                isrc = COALESCE(VALUES(isrc), isrc),
                title = VALUES(title),
                artist = VALUES(artist),
                album = VALUES(album),
                listen_count = listen_count + 1,
                last_listened_at = NOW()
            """,
            (
                recognition_key,
                source,
                local_song_id,
                acrid if acrid not in (None, "N/A") else None,
                isrc if isrc not in (None, "N/A") else None,
                title,
                artist,
                album,
            ),
        )

        song_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO recognition_history (
                song_id,
                source,
                recognition_score,
                recognized_at
            )
            VALUES (%s, %s, %s, NOW())
            """,
            (song_id, source, score_value),
        )

        cur.execute(
            """
            SELECT
                listen_count,
                first_listened_at,
                last_listened_at
            FROM recognized_songs
            WHERE id = %s
            """,
            (song_id,),
        )

        stats = cur.fetchone()
        conn.commit()

        if not stats:
            raise RuntimeError("Recognition was saved but its statistics could not be read back.")

        listen_count = int(stats["listen_count"])

        return {
            "song_id": song_id,
            "listen_count": listen_count,
            "listen_status": (
                "FIRST TIME LISTENED"
                if listen_count == 1
                else "LISTEN COUNT UPDATED"
            ),
            "first_listened_at": stats["first_listened_at"],
            "last_listened_at": stats["last_listened_at"],
        }

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
