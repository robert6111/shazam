import pymysql
from collections import defaultdict, Counter
from engine.fingerprint import generate_fingerprints

DB_CONFIG = {
    "host": "localhost",
    "user": "worldveil",
    "password": "strongpassword",
    "database": "worldveil_db"
}

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
            votes[(song_id, diff)] += 1

    if not votes:
        print("❌ No match found")
        return

    # Cluster per song (Shazam logic)
    song_scores = defaultdict(int)

    for (song_id, _), score in votes.items():
        song_scores[song_id] += score

    best_song = max(song_scores, key=song_scores.get)
    best_score = song_scores[best_song]

    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT name FROM songs WHERE id=%s", (best_song,))
    song_name = cur.fetchone()[0]

    conn.close()

    print(f"🎵 MATCH FOUND: {song_name}")
    print(f"Confidence score: {best_score}")


import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m engine.recognize <audiofile>")
        exit()

    recognize(sys.argv[1])


