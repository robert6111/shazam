# Worldveil — Music Recognition and Listening Analytics

Worldveil listens to music through your microphone, identifies the song, and keeps a personal listening history: how many times each song has been recognised, and when you first and last heard it.

It has two recognition engines:

- **Local audio fingerprinting**, built from scratch: converts audio into a spectrogram, finds peak points, and hashes pairs of peaks into fingerprints (the same idea Shazam uses). Songs you add are stored in a local MySQL database, and recordings are matched against them by aligning fingerprint time offsets. It works fully offline.
- **ACRCloud cloud API**: sends a short recording to ACRCloud's global music database, with requests signed using HMAC-SHA1, and shows the title, artist, album, release date and duration.

A **hybrid mode** tries ACRCloud first and falls back to the local database when there is no reliable cloud match.

## How it works

```
Microphone ──► record WAV (sounddevice) ──┬──► ACRCloud API (signed request) ──┐
                                          │                                    ├──► result table + listening history (MySQL)
                                          └──► local fingerprints (librosa) ───┘
```

Local fingerprinting steps (`engine/fingerprint.py`):

1. Load audio at 22,050 Hz mono and compute a short-time Fourier transform (FFT size 4096, hop 512).
2. Convert to decibels and keep local maxima above −40 dB as spectrogram peaks.
3. Pair each peak with up to 10 following peaks and hash (frequency 1, frequency 2, time gap) with SHA-1.
4. To recognise, hash the recording the same way, look the hashes up in MySQL, and vote on the song whose matches line up at the same time offset.

## Tech stack

Python · NumPy · SciPy · librosa · sounddevice · MySQL (PyMySQL) · ACRCloud API · python-dotenv · tabulate

## Project structure

```
listen_and_recognize.py            Record 20 s and match against the local database
listen_and_recognize_acrcloud.py   Record and identify with ACRCloud only
listen_and_recognize_hybrid.py     Record 12 s, try ACRCloud, then fall back to local
engine/fingerprint.py              Spectrogram-peak fingerprinting
engine/recognize.py                Local matching by fingerprint and time-offset voting
engine/acrcloud_recognize.py       ACRCloud client (signed requests, result table)
engine/recognition_stats.py        Listening history and play counts (tables created automatically)
db/store.py                        Fingerprint every song in audio/ and store it in MySQL
README_ACRCLOUD.md                 Extra notes on the ACRCloud and hybrid modes
```

## Setup

1. **Install the Python packages**

   ```bash
   python3 -m pip install -r requirements_acrcloud.txt librosa
   ```

2. **Create the MySQL database** for local mode

   ```sql
   CREATE DATABASE worldveil_db;
   CREATE USER 'worldveil'@'localhost' IDENTIFIED BY 'choose_a_password';
   GRANT ALL PRIVILEGES ON worldveil_db.* TO 'worldveil'@'localhost';
   USE worldveil_db;
   CREATE TABLE songs (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL UNIQUE);
   CREATE TABLE fingerprints (
       hash VARCHAR(64) NOT NULL, song_id INT NOT NULL, offset INT NOT NULL,
       INDEX idx_hash (hash),
       FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
   );
   ```

   Then set the same user and password in `DB_CONFIG` in `db/store.py`, `engine/recognize.py` and `engine/recognition_stats.py`. The listening-history tables are created automatically.

3. **Add ACRCloud credentials** (for ACRCloud and hybrid modes): copy `.env.example` to `.env` and fill in your host, access key and access secret from the ACRCloud console. `.env` is ignored by Git, so never commit it.

4. **Choose your microphone**: the scripts record from audio input `device=1`. Run `python3 -m sounddevice` to list devices and change the number if needed.

## Usage

```bash
# 1. Put your own audio files (.mp3, .wav, .flac, .ogg) in audio/ and build the local database
python3 db/store.py

# 2. Play a song near the microphone and run one of:
python3 listen_and_recognize.py            # local fingerprints only (offline)
python3 listen_and_recognize_acrcloud.py   # ACRCloud only
python3 listen_and_recognize_hybrid.py     # ACRCloud first, then local fallback
```

Each successful recognition prints the match and its score, then updates the listening history: **First time listened** for a new song, or **Listen count updated** with the total number of times it has been recognised.

On Windows, use `python` instead of `python3`.

## Author

Robert Baraka Kunenga, Computer Engineering, OSTIM Technical University · [github.com/robert6111](https://github.com/robert6111)
