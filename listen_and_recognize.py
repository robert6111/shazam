import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import subprocess

SAMPLE_RATE = 48000
DURATION = 20

print(" Listening...")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    device=1
)

sd.wait()

filename = "temp.wav"

write(filename, SAMPLE_RATE, (audio * 32767).astype(np.int16))

print(" Recognizing...")

subprocess.run(["python3", "engine/recognize.py", filename])
