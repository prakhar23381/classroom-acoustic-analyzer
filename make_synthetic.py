"""
Generate a synthetic classroom with KNOWN acoustics to validate analyze.py.

Each seat gets noise / speech / clap recordings produced by convolving sources with
a simulated room impulse response (direct sound + exponentially decaying diffuse
reverberation). Because we build the room, we know the true RT60, SNR and C50,
and can check that the analyzer recovers them.

Usage: python make_synthetic.py <out_folder> [--rt60 0.9]
"""
import argparse
import csv
import json
import os

import numpy as np
from scipy import signal
from scipy.io import wavfile

import acoustics as ac

FS = ac.FS
rng = np.random.default_rng(7)


def room_ir(distance, rt60, length=1.5, reverb_gain=0.035):
    n = int(length * FS)
    t = np.arange(n) / FS
    h = np.zeros(n)
    d = int(distance / 343 * FS) + 10
    h[d] = 1.0 / distance                                   # direct sound (inverse square)
    decay = np.exp(-6.91 * t / rt60)                         # 60 dB in rt60 seconds
    tail = rng.standard_normal(n) * decay * reverb_gain      # diffuse field, same everywhere
    tail[: d + int(0.002 * FS)] = 0
    return h + tail


def speech_like(seconds):
    """Speech-shaped noise with a 4 Hz syllable-rate envelope."""
    n = int(seconds * FS)
    x = ac.bandpass(rng.standard_normal(n), 150, 5000)
    env = 0.5 * (1 + np.sin(2 * np.pi * 4 * np.arange(n) / FS)) ** 2
    return x * env


def fan_noise(seconds, level):
    n = int(seconds * FS)
    t = np.arange(n) / FS
    brown = np.cumsum(rng.standard_normal(n))
    brown = signal.sosfilt(signal.butter(2, 20, "highpass", fs=FS, output="sos"), brown)
    brown /= np.std(brown)
    hum = sum(0.4 / k * np.sin(2 * np.pi * 120 * k * t) for k in (1, 2, 3))  # blade-pass tone
    pink = ac.bandpass(rng.standard_normal(n), 200, 8000) * 0.3
    x = brown + hum + pink
    return x / np.std(x) * level


def write(path, x):
    wavfile.write(path, FS, (x / 1.0).astype(np.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--rt60", type=float, default=0.9)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    seats, truth = [], {}
    src = speech_like(12) * 0.3
    for row, dist_row in enumerate([2.0, 4.5, 8.0], start=1):
        for col, lateral in enumerate([-2.5, 0.0, 2.5], start=1):
            name = f"{'FMB'[row - 1]}{col}"
            dist = float(np.hypot(dist_row, lateral))
            seats.append({"seat": name, "row": row, "col": col, "distance_m": round(dist, 2)})
            h = room_ir(dist, a.rt60)
            noise = fan_noise(20, 0.08 + 0.06 * (col == 3))   # window-side seats noisier
            speech_clean = signal.fftconvolve(src, h)[: len(src)]
            speech_rec = speech_clean + fan_noise(len(src) / FS, 0.08 + 0.06 * (col == 3))
            clap = signal.fftconvolve(np.r_[1.0, np.zeros(200)], h)
            clap = np.r_[np.zeros(FS // 2), clap, np.zeros(FS // 2)] * 0.8
            clap += fan_noise(len(clap) / FS, 0.002)
            write(os.path.join(a.out, f"{name}_noise.wav"), noise)
            write(os.path.join(a.out, f"{name}_speech.wav"), speech_rec)
            write(os.path.join(a.out, f"{name}_clap.wav"), clap)

            true_snr = ac.db(ac.power(ac.bandpass(speech_clean, *ac.SPEECH_BAND)) /
                             ac.power(ac.bandpass(noise, *ac.SPEECH_BAND)))
            e = ac.octave_band(h, 1000) ** 2
            d = int(dist / 343 * FS) + 10 - int(0.001 * FS)    # known direct arrival (−1 ms for filter spread)
            n50 = d + int(0.05 * FS)
            true_c50 = ac.db(e[d:n50].sum() / e[n50:].sum())
            truth[name] = {"rt60": a.rt60, "snr_db": round(true_snr, 2),
                           "c50_db": round(true_c50, 2)}

    with open(os.path.join(a.out, "seats.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["seat", "row", "col", "distance_m"])
        w.writeheader()
        w.writerows(seats)
    with open(os.path.join(a.out, "truth.json"), "w") as f:
        json.dump(truth, f, indent=1)
    print(f"Wrote {len(seats)} seats to {a.out} (true RT60 {a.rt60} s)")


if __name__ == "__main__":
    main()
