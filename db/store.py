import os
import pymysql
from engine.fingerprint import generate_fingerprints

DB_CONFIG = {
    "host": "localhost",
    "user": "worldveil",
    "password": "strongpassword",
    "database": "worldveil_db"
}

AUDIO_FOLDER = "audio"

def connect():
    return pymysql.connect(**DB_CONFIG)

def store_all_songs():
    conn = connect()
    cur = conn.cursor()

    for file in os.listdir(AUDIO_FOLDER):
        if not file.lower().endswith((".mp3", ".wav", ".flac", ".ogg")):
            continue

        path = os.path.join(AUDIO_FOLDER, file)

        # Check if already stored
        cur.execute("SELECT id FROM songs WHERE name=%s", (file,))
        if cur.fetchone():
            print(f"Skipping {file} (already added)")
            continue

        print(f"🎵 Fingerprinting {file}...")

        cur.execute("INSERT INTO songs (name) VALUES (%s)", (file,))
        song_id = cur.lastrowid

        fingerprints = generate_fingerprints(path)

        sql = "INSERT INTO fingerprints (hash, song_id, offset) VALUES (%s, %s, %s)"
        data = [(h, song_id, int(o)) for h, o in fingerprints]

        cur.executemany(sql, data)
        conn.commit()

        print(f"✅ Stored {len(fingerprints)} fingerprints for {file}")

    conn.close()
    print("🎉 All songs processed!")

if __name__ == "__main__":
    store_all_songs()

