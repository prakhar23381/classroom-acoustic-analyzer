"""
Core acoustic measurements for the Smart Classroom Acoustic Analyzer.

All functions take mono float signals (numpy arrays) and a sample rate.
FAE concepts used here: dB / RMS level, A-weighting, band-pass filtering,
signal-to-noise ratio, impulse response, Schroeder backward integration,
reverberation time (RT60), clarity (C50), FFT / Welch spectrum.
"""
import subprocess
import numpy as np
from scipy import signal

FS = 48000  # every file is resampled to this rate

# Speech intelligibility band (telephone band) used for SNR
SPEECH_BAND = (300.0, 3400.0)
OCTAVE_BANDS = [500, 1000, 2000]  # bands that matter most for speech


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_audio(path, fs=FS):
    """Decode any audio file (wav, m4a, mp3, aac, ogg...) to mono float32 via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(fs),
           "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    if x.size == 0:
        raise ValueError(f"No audio decoded from {path}")
    return x - np.mean(x)  # remove DC offset


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
def a_weighting_sos(fs=FS):
    """IEC 61672 A-weighting filter (analog prototype -> bilinear transform)."""
    f1, f2, f3, f4 = 20.598997, 107.65265, 737.86223, 12194.217
    a1000 = 1.9997
    nums = [(2 * np.pi * f4) ** 2 * 10 ** (a1000 / 20), 0, 0, 0, 0]
    dens = np.polymul([1, 4 * np.pi * f4, (2 * np.pi * f4) ** 2],
                      [1, 4 * np.pi * f1, (2 * np.pi * f1) ** 2])
    dens = np.polymul(np.polymul(dens, [1, 2 * np.pi * f3]), [1, 2 * np.pi * f2])
    b, a = signal.bilinear(nums, dens, fs)
    return signal.tf2sos(b, a)


def bandpass(x, lo, hi, fs=FS, order=4):
    sos = signal.butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x)


def octave_band(x, fc, fs=FS):
    return bandpass(x, fc / np.sqrt(2), fc * np.sqrt(2), fs, order=3)


# --------------------------------------------------------------------------
# Levels and SNR
# --------------------------------------------------------------------------
def power(x):
    return float(np.mean(x ** 2)) + 1e-20


def db(p):
    return 10 * np.log10(p)


def level_dbfs(x):
    """RMS level in dB relative to digital full scale."""
    return db(power(x))


def level_dba(x, fs=FS):
    """A-weighted RMS level (dBFS(A)). Add a calibration offset to get dB SPL(A)."""
    return db(power(signal.sosfilt(a_weighting_sos(fs), x)))


def snr_db(speech_plus_noise, noise_only, fs=FS):
    """
    SNR in the speech band.
    The speech recording also contains the room noise, so the speech power is
    estimated by power subtraction:  P_speech = P_(speech+noise) - P_noise.
    """
    ps_n = power(bandpass(speech_plus_noise, *SPEECH_BAND, fs))
    pn = power(bandpass(noise_only, *SPEECH_BAND, fs))
    ps = max(ps_n - pn, 1e-20)
    return db(ps / pn), db(ps), db(pn)


# --------------------------------------------------------------------------
# Impulse response analysis (clap / balloon pop)
# --------------------------------------------------------------------------
def extract_impulse(x, fs=FS, length_s=1.5, pre_s=0.005):
    """Cut the loudest transient (the clap) and the decay after it."""
    peak = int(np.argmax(np.abs(x)))
    start = max(peak - int(pre_s * fs), 0)
    return x[start:start + int(length_s * fs)]


def _noise_compensated_energy(h, fs):
    """
    Squared IR prepared for Schroeder integration (simplified Lundeby method):
      1. estimate the background-noise floor from the last 10 % of the recording,
      2. truncate where the smoothed decay first falls to 5 dB above that floor,
      3. subtract the noise power,
      4. estimate the energy lost by truncation from the decay slope.
    Returns (energy, correction_energy).
    """
    e = h ** 2
    noise = np.mean(e[int(0.9 * len(e)):])
    win = max(int(0.03 * fs), 1)
    env = np.convolve(e, np.ones(win) / win, mode="same")
    p = int(np.argmax(env))
    below = np.where(env[p:] <= noise * 10 ** (5 / 10))[0]
    end = p + int(below[0]) if below.size else len(e)
    e = np.clip(e[:end] - noise, 0, None)

    # decay slope of the envelope between -5 dB and the truncation point
    env_db = db(np.clip(env[p:end] - noise, 1e-20, None) / env[p])
    t = np.arange(len(env_db)) / fs
    sel = env_db < -5
    corr = 0.0
    if sel.sum() > 10:
        k = np.polyfit(t[sel], env_db[sel], 1)[0]  # dB per second (negative)
        if k < 0:
            p_end = np.mean(e[-win:]) if len(e) >= win else e[-1]
            corr = p_end * 10 / (-k * np.log(10)) * fs
    return e, corr


def schroeder_edc(h, fs=FS):
    """Energy decay curve (dB) by Schroeder backward integration."""
    e, corr = _noise_compensated_energy(h, fs)
    edc = np.cumsum(e[::-1])[::-1] + corr
    edc_db = db(edc / edc[0] + 1e-20)
    t = np.arange(len(edc_db)) / fs
    return t, edc_db


def _decay_fit(t, edc_db, top, bottom):
    idx = np.where((edc_db <= top) & (edc_db >= bottom))[0]
    if idx.size < 10:
        return np.nan
    slope, _ = np.polyfit(t[idx], edc_db[idx], 1)  # dB per second
    return -60.0 / slope if slope < 0 else np.nan


def rt60(h, fs=FS, broadband=False):
    """
    Reverberation time. Returns dict with EDT, T20, T30 (all extrapolated to 60 dB)
    and the best available estimate.
    """
    if broadband:
        # claps carry little energy below ~200 Hz, while fans/traffic do: band-limit
        h = bandpass(h, 200, 8000, fs)
    t, edc_db = schroeder_edc(h, fs)
    # peak-to-noise ratio decides which part of the decay is trustworthy
    e = h ** 2
    win = max(int(0.005 * fs), 1)
    env = np.convolve(e, np.ones(win) / win, mode="same")
    pnr = db(env.max() / (np.mean(e[int(0.9 * len(e)):]) + 1e-20))
    out = {
        "EDT": _decay_fit(t, edc_db, 0, -10),
        "T20": _decay_fit(t, edc_db, -5, -25),
        "T30": _decay_fit(t, edc_db, -5, -35),
        "peak_to_noise_db": float(pnr),
    }
    # ISO 3382 rule of thumb: need ~10-15 dB margin below the evaluation range
    allowed = [k for k, need in (("T30", 45), ("T20", 35), ("EDT", 15)) if pnr >= need]
    for k in allowed:
        if np.isfinite(out[k]):
            out["best"], out["method"] = out[k], k
            break
    else:
        out["best"], out["method"] = np.nan, "none"
    return out


def c50(h, fs=FS):
    """
    Speech clarity C50 (dB): early energy (first 50 ms after the direct sound)
    vs late energy. > 0 dB is acceptable for speech, > +3 dB is good.
    """
    e, corr = _noise_compensated_energy(h, fs)
    # t = 0 is the direct-sound onset (ISO 3382-1, A.3.4): the first sample within
    # 20 dB of the peak. Using the peak itself fails when a reflection or a
    # reverberant-tail sample is louder in-band than the direct sound (far seats).
    d = int(np.argmax(e >= np.max(e) * 10 ** (-20 / 10)))
    n50 = d + int(0.050 * fs)
    early, late = np.sum(e[d:n50]), np.sum(e[n50:]) + corr
    return db((early + 1e-20) / (late + 1e-20))


# --------------------------------------------------------------------------
# Spectrum
# --------------------------------------------------------------------------
def spectrum(x, fs=FS, nperseg=8192):
    f, pxx = signal.welch(x, fs, nperseg=min(nperseg, len(x)))
    return f, db(pxx)


def tonal_peaks(x, fs=FS, prominence_db=10, fmin=40, fmax=4000, top=5):
    """Strong narrow peaks in the noise spectrum (fan hum, AC compressor, mains hum)."""
    f, p = spectrum(x, fs, nperseg=16384)
    keep = (f >= fmin) & (f <= fmax)
    f, p = f[keep], p[keep]
    idx, props = signal.find_peaks(p, prominence=prominence_db)
    order = np.argsort(props["prominences"])[::-1][:top]
    return [(float(f[i]), float(props["prominences"][j])) for j, i in
            zip(order, idx[order])]


# --------------------------------------------------------------------------
# Ratings (targets from WHO / ANSI S12.60 / ASHA classroom guidance)
# --------------------------------------------------------------------------
TARGETS = {"snr_good": 15.0, "snr_fair": 10.0, "c50_good": 3.0, "c50_fair": 0.0,
           "rt60_max": 0.6}


def rate(snr, c50_db):
    def grade(v, good, fair):
        if not np.isfinite(v):
            return 1
        return 2 if v >= good else (1 if v >= fair else 0)
    g = min(grade(snr, TARGETS["snr_good"], TARGETS["snr_fair"]),
            grade(c50_db, TARGETS["c50_good"], TARGETS["c50_fair"]))
    return ["Poor", "Fair", "Good"][g]
