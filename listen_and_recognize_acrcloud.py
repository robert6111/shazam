import subprocess

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

# Separate ACRCloud listener. Your original listen_and_recognize.py is untouched.
SAMPLE_RATE = 48000
DURATION = 12
DEVICE = 1

print(" Listening for ACRCloud...")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    device=DEVICE
)

sd.wait()

filename = "temp_acrcloud.wav"

write(filename, SAMPLE_RATE, (audio * 32767).astype(np.int16))

print(" Recognizing with ACRCloud...")

subprocess.run(["python3", "-m", "engine.acrcloud_recognize", filename])
