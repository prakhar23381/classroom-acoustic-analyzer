# Smart Classroom Acoustic Analyzer

Python tool that measures how clearly speech reaches every seat in a classroom,
using only a phone and a speaker you already own.

For each seat it reports:

| Metric | What it tells you | Target |
|---|---|---|
| **SNR** (speech band, 300–3400 Hz) | How far the teacher's voice is above fan/AC/outside noise | ≥ 15 dB |
| **C50** (1 kHz octave) | Speech clarity: useful early sound vs smearing echoes | ≥ +3 dB good, ≥ 0 dB fair |
| **RT60** (broadband + 500/1k/2k Hz) | How long the room keeps ringing | ≤ 0.6 s for classrooms |
| **Noise level, dB(A)** | Background loudness (absolute if calibrated) | ≤ 35 dB(A) (WHO) |
| **Tonal peaks** | Fan / AC / mains hum frequencies | — |

It outputs a colour-coded seat map, a speech-level-vs-distance plot against the
inverse square law, Schroeder decay curves, noise spectra, `results.csv` and a
`report.md` with recommendations.

## Install

```
pip install numpy scipy matplotlib     # plus ffmpeg on the PATH (reads .m4a/.mp3/.wav)
```

## Run

```
python analyze.py recordings/LH-101 --out results/LH-101
python analyze.py recordings/LH-101 --out results/LH-101 --cal-seat F2 --cal-dba 48   # optional calibration
```

## Validate (synthetic room with known answers)

```
python make_synthetic.py synthetic_room --rt60 0.9
python analyze.py synthetic_room --out synthetic_results
```

Validation results (true value → measured):

- RT60 0.5 / 0.9 / 1.4 s → max error 6.0 / 4.4 / 3.6 % across the 9 seats (EDT-based, slight over-estimate)
- SNR → within 0.01 dB
- C50 → max error 0.45 / 0.28 / 0.19 dB (below the 1 dB JND of ISO 3382-1)
- Run all three: `python validation/summarize.py` after generating `validation/synth_rt{0.5,0.9,1.4}` and `validation/results_rt*`
- If the clap is too quiet, the tool refuses to report RT60 instead of guessing.

---

# Recording protocol (≈ 1 hour, 2 people)

**You need:** one phone for recording (use the SAME phone for everything), one
phone/laptop/Bluetooth speaker to play speech, a measuring tape (or count floor tiles).

### Setup

1. Pick an empty classroom. Note the room number, length × width × height, number
   of fans/ACs, and the main surfaces (glass, plaster, curtains, boards).
2. Put the speaker where the teacher stands, about 1.5 m high (on the lectern),
   facing the class. Set its volume once, **never change it again**.
3. Choose 9 seats as a 3 × 3 grid: front/middle/back rows × left/centre/right.
   Name them `F1 F2 F3 / M1 M2 M3 / B1 B2 B3` (1 = left as seen from the teacher).
4. Measure each seat's distance to the speaker. Write `seats.csv`:

```
seat,row,col,distance_m
F1,1,1,3.2
F2,1,2,2.0
...
```

### Phone settings

- iPhone Voice Memos: turn **Enhance Recording OFF**, set quality to **Lossless**.
- Android: use a recorder with a "raw"/"standard" mode and noise cancellation OFF.
- Hold the phone at seated ear height (~1.2 m), mic pointing at the teacher,
  not touching the desk. Stay still and quiet.

### At every seat, record three files

| File | What to do | Length |
|---|---|---|
| `F1_noise.m4a` | Fans/AC ON as in a normal lecture. Nobody talks. | 20 s |
| `F1_speech.m4a` | Same conditions. Play the reference speech clip from the speaker. | 15–20 s |
| `F1_clap.m4a` | Fans OFF. Person at the speaker gives 3 loud, sharp claps, 3 s apart (or pops a balloon). | 12 s |

Use one fixed speech clip for every seat (any 20 s of clear lecture speech).
Rename files exactly as `<seat>_<noise|speech|clap>.<ext>` and put them, with
`seats.csv`, in one folder.

**Optional calibration:** at seat F2, read the noise level from a free
sound-level-meter app in dB(A) and pass it with `--cal-seat F2 --cal-dba <value>`.
