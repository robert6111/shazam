# Worldveil ACRCloud Add-on

This add-on keeps your original local fingerprint system unchanged.

Your original command still works:

```bash
python3 listen_and_recognize.py
```

New ACRCloud-only command:

```bash
python3 listen_and_recognize_acrcloud.py
```

Hybrid command, which tries ACRCloud first and then falls back to your local database:

```bash
python3 listen_and_recognize_hybrid.py
```

## Install

```bash
python3 -m pip install --user -r requirements_acrcloud.txt
```

## Credentials

The project uses `.env` in the project root:

```env
ACRCLOUD_HOST=your_host
ACRCLOUD_ACCESS_KEY=your_key
ACRCLOUD_ACCESS_SECRET=your_secret
```

Do not upload `.env` publicly. Keep it private.

## Files added

- `engine/acrcloud_recognize.py`
- `engine/__init__.py`
- `listen_and_recognize_acrcloud.py`
- `listen_and_recognize_hybrid.py`
- `requirements_acrcloud.txt`
- `.env.example`
- `.env`
- `README_ACRCLOUD.md`

## Important

ACRCloud does not use your custom local `fingerprint.py` hashes. This add-on sends a short WAV sample to ACRCloud and ACRCloud compares it with its own online database. Your local MySQL fingerprint system remains available as the offline fallback.
