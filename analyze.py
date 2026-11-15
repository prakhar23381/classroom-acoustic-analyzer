"""
Smart Classroom Acoustic Analyzer: analyze a folder of seat recordings.

Folder layout (one classroom):
    seats.csv            seat,row,col,distance_m
    F1_noise.m4a         ~20 s of room noise only (fans/AC on, nobody talking)
    F1_speech.m4a        the same reference speech clip played from the teacher's spot
    F1_clap.m4a          one sharp clap (or balloon pop) from the teacher's spot
    ...same three files for every seat...

Usage:
    python analyze.py <folder> [--out results] [--cal-seat F1 --cal-dba 52]

--cal-seat/--cal-dba: a sound-level-meter app reading (dB(A)) of the noise at one
seat. Used to turn the relative dBFS levels into estimated dB SPL(A).
"""
import argparse
import csv
import glob
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker

import acoustics as ac

GREEN, AMBER, RED = "#2e9e5b", "#e0a526", "#d1495b"
RATING_COLOR = {"Good": GREEN, "Fair": AMBER, "Poor": RED}


def find(folder, seat, kind):
    hits = glob.glob(os.path.join(folder, f"{seat}_{kind}.*"))
    return hits[0] if hits else None


def read_seats(folder):
    with open(os.path.join(folder, "seats.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["row"], r["col"] = int(r["row"]), int(r["col"])
        r["distance_m"] = float(r["distance_m"])
    return rows


def analyze_seat(folder, seat):
    out = {"seat": seat["seat"], "row": seat["row"], "col": seat["col"],
           "distance_m": seat["distance_m"]}
    noise_p, speech_p, clap_p = (find(folder, seat["seat"], k)
                                 for k in ("noise", "speech", "clap"))
    noise = ac.load_audio(noise_p) if noise_p else None
    if noise is not None:
        out["noise_dbfs_a"] = ac.level_dba(noise)
        out["hum_peaks"] = "; ".join(f"{f:.0f} Hz" for f, _ in ac.tonal_peaks(noise)[:3])
    if speech_p and noise is not None:
        speech = ac.load_audio(speech_p)
        out["speech_dbfs_a"] = ac.level_dba(speech)
        out["snr_db"], out["speech_band_db"], out["noise_band_db"] = ac.snr_db(speech, noise)
    if clap_p:
        h = ac.extract_impulse(ac.load_audio(clap_p))
        r = ac.rt60(h, broadband=True)
        out["rt60_s"], out["rt60_method"] = r["best"], r["method"]
        out["clap_peak_to_noise_db"] = r["peak_to_noise_db"]
        out["edt_s"] = r["EDT"]
        for fc in ac.OCTAVE_BANDS:
            out[f"rt60_{fc}"] = ac.rt60(ac.octave_band(h, fc))["best"]
        out["c50_db"] = ac.c50(ac.octave_band(h, 1000))
        out["_ir"] = h
    out["rating"] = ac.rate(out.get("snr_db", np.nan), out.get("c50_db", np.nan))
    out["_noise"] = noise
    return out


# --------------------------------------------------------------------------
# Plots
# --------------------------------------------------------------------------
def plot_seat_map(results, path):
    rows = max(r["row"] for r in results)
    cols = max(r["col"] for r in results)
    fig, ax = plt.subplots(figsize=(1.9 * cols + 1.5, 1.5 * rows + 1.6))
    for r in results:
        x, y = r["col"] - 1, r["row"] - 1
        ax.add_patch(plt.Rectangle((x + 0.05, y + 0.05), 0.9, 0.9,
                                   color=RATING_COLOR[r["rating"]], alpha=0.9))
        snr = r.get("snr_db", np.nan)
        c = r.get("c50_db", np.nan)
        ax.text(x + 0.5, y + 0.62, r["seat"], ha="center", va="center",
                color="white", fontsize=13, weight="bold")
        ax.text(x + 0.5, y + 0.32, f"SNR {snr:.0f} dB\nC50 {c:+.1f} dB",
                ha="center", va="center", color="white", fontsize=9)
    ax.set_xlim(0, cols)
    ax.set_ylim(rows + 0.6, -0.6)
    ax.text(cols / 2, -0.3, "TEACHER / BOARD", ha="center", fontsize=11, weight="bold")
    ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in RATING_COLOR.values()]
    ax.legend(handles, ["Good: SNR >= 15 dB and C50 >= +3 dB", "Fair", "Poor: SNR < 10 dB or C50 < 0 dB"],
              loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=1, frameon=False, fontsize=9)
    ax.set_title("Seat-wise speech clarity map", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_distance(results, path):
    rs = sorted([r for r in results if "speech_band_db" in r], key=lambda r: r["distance_m"])
    if len(rs) < 2:
        return
    d = np.array([r["distance_m"] for r in rs])
    L = np.array([r["speech_band_db"] for r in rs])
    n = np.array([r["noise_band_db"] for r in rs])
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.scatter(d, L, color=GREEN, zorder=3, label="Measured speech level")
    dd = np.linspace(d.min(), d.max(), 100)
    ax.plot(dd, L[0] - 20 * np.log10(dd / d[0]), "--", color="gray",
            label="Inverse square law (-6 dB per doubling)")
    slope = np.polyfit(np.log2(d), L, 1)[0]
    ax.plot(dd, np.polyval(np.polyfit(np.log2(d), L, 1), np.log2(dd)), color=GREEN,
            alpha=0.6, label=f"Measured trend ({slope:.1f} dB per doubling)")
    ax.scatter(d, n, color=RED, marker="x", label="Background noise")
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("Distance from teacher (m, log scale)")
    ax.set_ylabel("Level in speech band (dBFS)")
    ax.set_title("Speech level vs distance")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_decay(results, path):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for r in results:
        if "_ir" in r:
            t, edc = ac.schroeder_edc(r["_ir"])
            ax.plot(t, edc, label=f"{r['seat']} (RT60 {r['rt60_s']:.2f} s)")
    ax.axhline(-60, color="gray", lw=0.8)
    ax.set_ylim(-70, 2)
    ax.set_xlabel("Time after clap (s)")
    ax.set_ylabel("Energy decay (dB)")
    ax.set_title("Schroeder energy decay curves")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_noise_spectrum(results, path):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for r in results:
        if r.get("_noise") is not None:
            f, p = ac.spectrum(r["_noise"])
            ax.semilogx(f[1:], p[1:], lw=0.9, label=r["seat"])
    ax.axvspan(*ac.SPEECH_BAND, color=GREEN, alpha=0.1, label="Speech band 300-3400 Hz")
    ax.set_xlim(20, 20000)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power (dB/Hz)")
    ax.set_title("Background noise spectrum (Welch FFT)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# --------------------------------------------------------------------------
def recommendations(results, cal_offset):
    recs = []
    rts = [r.get("rt60_s", np.nan) for r in results]
    rt = np.nanmedian(rts) if np.isfinite(rts).any() else np.nan
    if not np.isfinite(rt):
        recs.append("RT60 could not be measured: the claps were too quiet compared with the "
                    "room noise. Re-record with a balloon pop or louder claps, fans off.")
    elif rt > ac.TARGETS["rt60_max"]:
        recs.append(f"Room RT60 is {rt:.2f} s, above the 0.6 s classroom target: add soft "
                    "absorption (curtains, notice-board fabric, ceiling panels) or reduce "
                    "hard parallel surfaces.")
    poor = [r["seat"] for r in results if r["rating"] == "Poor"]
    if poor:
        recs.append(f"Seats {', '.join(poor)} are below the clarity threshold: use a "
                    "microphone + speaker for the teacher, or seat students with hearing "
                    "or language difficulties in the Good zone.")
    hums = {h for r in results for h in str(r.get("hum_peaks", "")).split("; ") if h}
    if hums:
        recs.append(f"Tonal noise at {', '.join(sorted(hums))}: check fans/AC/projector; "
                    "servicing or lower fan speed reduces masking of speech.")
    noise = np.nanmedian([r.get("noise_dbfs_a", np.nan) for r in results]) + (cal_offset or 0)
    if cal_offset is not None and noise > 35:
        recs.append(f"Background noise is about {noise:.0f} dB(A), above the WHO 35 dB(A) "
                    "classroom guideline.")
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="results")
    ap.add_argument("--cal-seat")
    ap.add_argument("--cal-dba", type=float)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    results = [analyze_seat(a.folder, s) for s in read_seats(a.folder)]

    cal_offset = None
    if a.cal_seat and a.cal_dba is not None:
        ref = next(r for r in results if r["seat"] == a.cal_seat)
        cal_offset = a.cal_dba - ref["noise_dbfs_a"]
        for r in results:
            for k in ("noise_dbfs_a", "speech_dbfs_a"):
                if k in r:
                    r[k.replace("dbfs_a", "dba_spl")] = r[k] + cal_offset

    cols = [k for k in results[0] if not k.startswith("_")]
    for r in results[1:]:
        cols += [k for k in r if not k.startswith("_") and k not in cols]
    with open(os.path.join(a.out, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()
                        if not k.startswith("_")})

    plot_seat_map(results, os.path.join(a.out, "seat_map.png"))
    plot_distance(results, os.path.join(a.out, "distance_law.png"))
    plot_decay(results, os.path.join(a.out, "decay_curves.png"))
    plot_noise_spectrum(results, os.path.join(a.out, "noise_spectrum.png"))

    lines = ["# Classroom acoustic report", "",
             "| Seat | Dist (m) | SNR (dB) | C50 (dB) | RT60 (s) | Rating |",
             "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['seat']} | {r['distance_m']:.1f} | {r.get('snr_db', np.nan):.1f} | "
                     f"{r.get('c50_db', np.nan):+.1f} | {r.get('rt60_s', np.nan):.2f} | {r['rating']} |")
    lines += ["", "## Recommendations", ""] + [f"- {x}" for x in recommendations(results, cal_offset)]
    with open(os.path.join(a.out, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
