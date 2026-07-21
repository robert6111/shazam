import pymysql
from collections import defaultdict, Counter
from fingerprint import generate_fingerprints
from recognition_stats import record_recognition

DB_CONFIG = {
    "host": "localhost",
    "user": "worldveil",
    "password": "strongpassword",
    "database": "worldveil_db"
}

MIN_CONFIDENCE = 20


def connect():
    return pymysql.connect(**DB_CONFIG)


def recognize(file_path):
    print("Generating query fingerprints...")

    fingerprints = generate_fingerprints(file_path)

    if not fingerprints:
        print("No fingerprints generated")
        return

    # Reduce for speed but keep structure
    fingerprints = fingerprints[::3][:5000]

    print("Preparing batch query...")

    hashes = [h for h, _ in fingerprints]

    conn = connect()
    cur = conn.cursor()

    placeholders = ",".join(["%s"] * len(hashes))

    sql = f"""
        SELECT hash, song_id, offset
        FROM fingerprints
        WHERE hash IN ({placeholders})
    """

    print("Searching database (BATCH MODE)...")

    cur.execute(sql, hashes)
    rows = cur.fetchall()

    print(f"Fetched {len(rows)} matching fingerprints")

    conn.close()

    # Build map of query offsets
    query_offsets = defaultdict(list)

    for h, off in fingerprints:
        query_offsets[h].append(int(off))

    # Offset-based voting
    votes = Counter()

    for h, song_id, db_offset in rows:
        if h not in query_offsets:
            continue

        for q_off in query_offsets[h]:
            diff = int(db_offset) - q_off

            # Group close offsets together
            diff_bin = round(diff / 5) * 5

            votes[(song_id, diff_bin)] += 1

    if not votes:
        print(" No match found,acha ujinga")
        return

    # Use strongest offset alignment per song
    song_scores = defaultdict(int)

    for (song_id, diff), score in votes.items():
        if score > song_scores[song_id]:
            song_scores[song_id] = score

    best_song = max(song_scores, key=song_scores.get)
    best_score = song_scores[best_song]

    if best_score < MIN_CONFIDENCE:
        print(" No reliable match found ,,acha ujinga")
        print(f"Best weak match score: {best_score}")
        return

    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT name FROM songs WHERE id=%s", (best_song,))
    result = cur.fetchone()

    conn.close()

    if not result:
        print(" Song ID found but song name missing in database")
        return

    song_name = result[0]

    print(f" MATCH FOUND: {song_name}")
    print(f"Confidence score: {best_score}")

    try:
        listen_stats = record_recognition(
            source="local",
            title=song_name,
            artist="Unknown",
            score=best_score,
            local_song_id=best_song,
        )

        print(f"Times Recognized: {listen_stats['listen_count']}")
        print(f"Listen Status: {listen_stats['listen_status']}")
        print(f"First Listened: {listen_stats['first_listened_at']}")
        print(f"Last Listened: {listen_stats['last_listened_at']}")
    except Exception as exc:
        # Keep the existing local recognition working even if statistics
        # cannot be written at this moment.
        print(f"Warning: Could not update listen counter: {exc}")


import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 engine/recognize.py <audiofile>")
        exit()

    recognize(sys.argv[1])
