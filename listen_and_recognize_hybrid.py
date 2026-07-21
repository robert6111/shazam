import subprocess

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

# Hybrid mode: try ACRCloud first, then fall back to your original local recognizer.
# Your original listen_and_recognize.py and engine/recognize.py are untouched.
SAMPLE_RATE = 48000
DURATION = 12
DEVICE = 1

print(" Listening...")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    device=DEVICE
)

sd.wait()

filename = "temp_hybrid.wav"

write(filename, SAMPLE_RATE, (audio * 32767).astype(np.int16))

print(" Trying ACRCloud first...")

acr = subprocess.run(["python3", "-m", "engine.acrcloud_recognize", filename])

if acr.returncode != 0:
    print(" ACRCloud did not return a reliable result. Trying your local database...")
    subprocess.run(["python3", "engine/recognize.py", filename])
