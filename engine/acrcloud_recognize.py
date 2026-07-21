import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tabulate import tabulate

from engine.recognition_stats import record_recognition


# ---------------------------------------------------------
# PROJECT / ENVIRONMENT SETUP
# ---------------------------------------------------------

# This assumes this file is:
# worldveil/engine/acrcloud_recognize.py
#
# Therefore:
# parent       = engine/
# parent.parent = worldveil/

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load credentials from:
# worldveil/.env
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------
# ACRCLOUD CREDENTIALS
# ---------------------------------------------------------

ACRCLOUD_HOST = os.getenv("ACRCLOUD_HOST")
ACRCLOUD_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY")
ACRCLOUD_ACCESS_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET")


# ---------------------------------------------------------
# ACRCLOUD API SETTINGS
# ---------------------------------------------------------

HTTP_METHOD = "POST"
HTTP_URI = "/v1/identify"
DATA_TYPE = "audio"
SIGNATURE_VERSION = "1"


# ---------------------------------------------------------
# CREATE ACRCLOUD SIGNATURE
# ---------------------------------------------------------

def _make_signature(timestamp: str) -> str:
    """
    Generate the HMAC-SHA1 signature required by ACRCloud.
    """

    string_to_sign = "\n".join([
        HTTP_METHOD,
        HTTP_URI,
        ACRCLOUD_ACCESS_KEY,
        DATA_TYPE,
        SIGNATURE_VERSION,
        timestamp,
    ])

    digest = hmac.new(
        ACRCLOUD_ACCESS_SECRET.encode("ascii"),
        string_to_sign.encode("ascii"),
        digestmod=hashlib.sha1,
    ).digest()

    signature = base64.b64encode(digest).decode("ascii")

    return signature


# ---------------------------------------------------------
# SEND AUDIO TO ACRCLOUD
# ---------------------------------------------------------

def recognize_with_acrcloud(file_path: str) -> dict:
    """
    Send an audio file to ACRCloud for identification.
    """

    # Check credentials
    if not ACRCLOUD_HOST:
        raise RuntimeError(
            "Missing ACRCLOUD_HOST. Check your .env file."
        )

    if not ACRCLOUD_ACCESS_KEY:
        raise RuntimeError(
            "Missing ACRCLOUD_ACCESS_KEY. Check your .env file."
        )

    if not ACRCLOUD_ACCESS_SECRET:
        raise RuntimeError(
            "Missing ACRCLOUD_ACCESS_SECRET. Check your .env file."
        )

    # Check audio file
    audio_path = Path(file_path)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    if not audio_path.is_file():
        raise RuntimeError(
            f"Audio path is not a file: {audio_path}"
        )

    sample_bytes = audio_path.stat().st_size

    if sample_bytes <= 0:
        raise RuntimeError(
            "Audio file is empty."
        )

    # Keep samples reasonably small.
    if sample_bytes > 5 * 1024 * 1024:
        raise RuntimeError(
            "Audio sample is too large. "
            "Use a shorter recording, preferably 10-15 seconds."
        )

    # ACRCloud timestamp
    timestamp = str(int(time.time()))

    # Generate signature
    signature = _make_signature(timestamp)

    # Build API URL
    url = f"https://{ACRCLOUD_HOST}{HTTP_URI}"

    # POST parameters
    data = {
        "access_key": ACRCLOUD_ACCESS_KEY,
        "sample_bytes": sample_bytes,
        "timestamp": timestamp,
        "signature": signature,
        "data_type": DATA_TYPE,
        "signature_version": SIGNATURE_VERSION,
    }

    # Send audio
    with open(audio_path, "rb") as audio_file:

        files = {
            "sample": (
                audio_path.name,
                audio_file,
                "application/octet-stream",
            )
        }

        try:
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=30,
            )

        except requests.exceptions.Timeout:
            raise RuntimeError(
                "ACRCloud request timed out."
            )

        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not connect to ACRCloud: {exc}"
            )

        except requests.exceptions.RequestException as exc:
            raise RuntimeError(
                f"ACRCloud request failed: {exc}"
            )

    # Check HTTP status
    try:
        response.raise_for_status()

    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"ACRCloud HTTP error: {exc}\n"
            f"Response: {response.text}"
        )

    # Parse JSON
    try:
        result = response.json()

    except ValueError:
        raise RuntimeError(
            "ACRCloud returned an invalid JSON response."
        )

    return result


# ---------------------------------------------------------
# EXTRACT NAMES
# ---------------------------------------------------------

def _names(items) -> str:
    """
    Extract names from ACRCloud artist/composer/etc lists.
    """

    if not items:
        return "Unknown"

    names = [
        item.get("name", "Unknown")
        for item in items
        if isinstance(item, dict)
    ]

    return ", ".join(names) if names else "Unknown"


# ---------------------------------------------------------
# DISPLAY RECOGNITION RESULT AS TABLE
# ---------------------------------------------------------

def print_result(result: dict) -> bool:
    """
    Display the best ACRCloud recognition result
    in a terminal table.
    """

    status = result.get("status", {})

    status_code = status.get("code")
    status_message = status.get("msg", "Unknown")


    # -----------------------------------------------------
    # Check recognition status
    # -----------------------------------------------------

    if status_code != 0:

        print("\nACRCLOUD RECOGNITION RESULT\n")

        error_table = [
            ["Status Code", status_code],
            ["Message", status_message],
            ["Result", "No reliable match found"],
        ]

        print(
            tabulate(
                error_table,
                headers=["FIELD", "VALUE"],
                tablefmt="grid",
            )
        )

        return False


    # -----------------------------------------------------
    # Get music results
    # -----------------------------------------------------

    metadata = result.get("metadata", {})

    music = metadata.get("music", [])

    if not music:

        print("\nACRCLOUD RECOGNITION RESULT\n")

        no_match_table = [
            ["Result", "No music match found"],
        ]

        print(
            tabulate(
                no_match_table,
                headers=["FIELD", "VALUE"],
                tablefmt="grid",
            )
        )

        return False


    # -----------------------------------------------------
    # Best match
    # -----------------------------------------------------

    best = music[0]


    # -----------------------------------------------------
    # Basic song information
    # -----------------------------------------------------

    title = best.get(
        "title",
        "Unknown title",
    )

    artists = _names(
        best.get(
            "artists",
            [],
        )
    )

    album = (
        best
        .get("album", {})
        .get("name", "Unknown album")
    )

    label = best.get(
        "label",
        "Unknown label",
    )

    release_date = best.get(
        "release_date",
        "Unknown",
    )

    score = best.get(
        "score",
        "N/A",
    )


    # -----------------------------------------------------
    # Optional additional information
    # -----------------------------------------------------

    duration_ms = best.get(
        "duration_ms"
    )

    if duration_ms:
        duration_seconds = int(duration_ms / 1000)

        minutes = duration_seconds // 60

        seconds = duration_seconds % 60

        duration = f"{minutes}:{seconds:02d}"

    else:
        duration = "Unknown"


    acrid = best.get(
        "acrid",
        "N/A",
    )


    # -----------------------------------------------------
    # External Metadata
    # -----------------------------------------------------

    external_metadata = best.get(
        "external_metadata",
        {},
    )


    # Spotify
    spotify_id = (
        external_metadata
        .get("spotify", {})
        .get("track", {})
        .get("id", "N/A")
    )


    # YouTube
    youtube_id = (
        external_metadata
        .get("youtube", {})
        .get("vid", "N/A")
    )


    # Deezer
    deezer_id = (
        external_metadata
        .get("deezer", {})
        .get("track", {})
        .get("id", "N/A")
    )


    # ISRC
    external_ids = best.get(
        "external_ids",
        {},
    )

    isrc = external_ids.get(
        "isrc",
        "N/A",
    )

    upc = external_ids.get(
        "upc",
        "N/A",
    )


    # -----------------------------------------------------
    # Database-backed listen counter / recognition history
    # -----------------------------------------------------

    listen_stats = None

    try:
        listen_stats = record_recognition(
            source="acrcloud",
            title=title,
            artist=artists,
            album=album,
            score=score,
            acrid=acrid,
            isrc=isrc,
        )
    except Exception as exc:
        # Recognition itself must keep working even if the statistics
        # database is temporarily unavailable.
        print(f"Warning: Could not update listen counter: {exc}")


    # -----------------------------------------------------
    # Create result table
    # -----------------------------------------------------

    table_data = [
        ["Title", title],
        ["Artist", artists],
        ["Album", album],
        ["Label", label],
        ["Release Date", release_date],
        ["Duration", duration],
        ["Recognition Score", score],
    ]

    if listen_stats:
        table_data.extend([
            ["Times Recognized", listen_stats["listen_count"]],
            ["Listen Status", listen_stats["listen_status"]],
            ["First Listened", listen_stats["first_listened_at"]],
            ["Last Listened", listen_stats["last_listened_at"]],
        ])

    table_data.extend([
        ["ISRC", isrc],
        ["UPC", upc],
        ["ACRCloud ID", acrid],
        ["Spotify Track ID", spotify_id],
        ["YouTube Video ID", youtube_id],
        ["Deezer Track ID", deezer_id],
    ])


    # -----------------------------------------------------
    # Print table
    # -----------------------------------------------------

    print("\n")
    print("=" * 75)
    print("                        ACRCLOUD MATCH FOUND")
    print("=" * 75)
    print()

    print(
        tabulate(
            table_data,
            headers=[
                "FIELD",
                "RECOGNITION RESULT",
            ],
            tablefmt="grid",
        )
    )

    print()


    # -----------------------------------------------------
    # Save raw response
    # -----------------------------------------------------

    try:

        response_file = (
            PROJECT_ROOT
            / "last_acrcloud_response.json"
        )

        with open(
            response_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                result,
                file,
                indent=2,
                ensure_ascii=False,
            )

    except Exception as exc:

        print(
            f"Warning: Could not save raw response: {exc}"
        )


    return True


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    """
    Run recognition from command line.

    Example:

    python3 -m engine.acrcloud_recognize temp.wav
    """

    import sys


    # -----------------------------------------------------
    # Check command line argument
    # -----------------------------------------------------

    if len(sys.argv) < 2:

        print(
            "\nUsage:\n"
            "python3 -m engine.acrcloud_recognize <audiofile>\n"
        )

        print(
            "Example:\n"
            "python3 -m engine.acrcloud_recognize temp.wav\n"
        )

        return 1


    audio_file = sys.argv[1]


    # -----------------------------------------------------
    # Perform recognition
    # -----------------------------------------------------

    try:

        result = recognize_with_acrcloud(
            audio_file
        )

        matched = print_result(
            result
        )

        return 0 if matched else 2


    except KeyboardInterrupt:

        print(
            "\nRecognition cancelled."
        )

        return 130


    except Exception as exc:

        print("\nACRCLOUD RECOGNITION FAILED")

        print(
            f"Error: {exc}"
        )

        return 1


# ---------------------------------------------------------
# PROGRAM ENTRY
# ---------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(
        main()
    )