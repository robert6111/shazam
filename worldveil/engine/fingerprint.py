import librosa
import numpy as np
import hashlib
from scipy.ndimage import maximum_filter

SAMPLE_RATE = 22050
FFT_SIZE = 4096
HOP_LENGTH = 512

PEAK_NEIGHBORHOOD = 30
AMP_MIN = -40          # dB threshold
FAN_VALUE = 10         # number of peak pairs
MIN_DELTA_T = 1
MAX_DELTA_T = 200


def generate_fingerprints(file_path):
    y, sr = librosa.load(file_path, sr=SAMPLE_RATE, mono=True)

    S = np.abs(librosa.stft(y, n_fft=FFT_SIZE, hop_length=HOP_LENGTH))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    local_max = maximum_filter(S_db, size=PEAK_NEIGHBORHOOD)
    peaks = np.where((S_db == local_max) & (S_db > AMP_MIN))

    freq_idxs = peaks[0]
    time_idxs = peaks[1]

    # Sort by time
    peaks = sorted(zip(time_idxs, freq_idxs))
    fingerprints = []

    for i in range(len(peaks)):
        t1, f1 = peaks[i]
        for j in range(1, FAN_VALUE):
            if i + j < len(peaks):
                t2, f2 = peaks[i + j]
                delta_t = t2 - t1

                if MIN_DELTA_T <= delta_t <= MAX_DELTA_T:
                    hash_input = f"{f1}|{f2}|{delta_t}"
                    h = hashlib.sha1(hash_input.encode()).hexdigest()[:20]
                    fingerprints.append((h, t1))

    return fingerprints

