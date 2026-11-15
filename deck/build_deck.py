"""
Build the FAE Stage 2 progress-report deck (.pptx) in the Stage 1 green style.

Run from the project root after the synthetic validation has been generated:
    .venv/bin/python deck/build_deck.py
Output: deck/FAE_Stage2_Progress_Report.pptx
"""
import csv
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)
RES = os.path.join(ROOT, "validation", "results_rt0.9")

DARK = RGBColor(0x0B, 0x2A, 0x1F)
MINT = RGBColor(0x6E, 0xE7, 0xA0)
PALE = RGBColor(0xD9, 0xFB, 0xE6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DEEP = RGBColor(0x14, 0x4D, 0x37)
AMBER = RGBColor(0xF2, 0xC1, 0x4E)
FONT = "Montserrat"


# ---------------------------------------------------------------------------
# Generated assets
# ---------------------------------------------------------------------------
def make_background(path):
    """Dark green textured background with decorative curly lines (Stage 1 look)."""
    w, h = 1920, 1080
    rng = np.random.default_rng(3)
    y, x = np.mgrid[0:h, 0:w]
    g = 1 - 0.45 * np.hypot((x - w * 0.3) / w, (y - h * 0.35) / h)
    base = np.array([0x10, 0x3F, 0x2F]) / 255
    img = base[None, None, :] * g[..., None]
    img += rng.normal(0, 0.012, (h, w, 1))                     # paper texture
    img = np.clip(img, 0, 1)
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img, extent=[0, w, h, 0])
    t = np.linspace(0, 1, 600)
    for k, (x0, y0, s, a) in enumerate([(1500, 980, 420, 0.35), (1650, 140, 300, 0.25),
                                         (120, 1000, 260, 0.2)]):
        xs = x0 + s * (t - 0.5) * 2 + 40 * np.sin(2 * np.pi * 3 * t + k)
        ys = y0 + 60 * np.sin(2 * np.pi * 2 * t + k) + 35 * np.cos(2 * np.pi * 5 * t)
        ax.plot(xs, ys, color="#6EE7A0", lw=3, alpha=a, solid_capstyle="round")
    ax.set_xlim(0, w); ax.set_ylim(h, 0); ax.axis("off")
    fig.savefig(path, dpi=100); plt.close(fig)


def load_validation():
    out = []
    for rt in ("0.5", "0.9", "1.4"):
        truth = json.load(open(os.path.join(ROOT, f"validation/synth_rt{rt}/truth.json")))
        res = {r["seat"]: r for r in
               csv.DictReader(open(os.path.join(ROOT, f"validation/results_rt{rt}/results.csv")))}
        rows = []
        for s, t in truth.items():
            m = res[s]
            rows.append(dict(seat=s, rt_true=t["rt60"], rt=float(m["rt60_s"]),
                             snr_true=t["snr_db"], snr=float(m["snr_db"]),
                             c50_true=t["c50_db"], c50=float(m["c50_db"])))
        out.append((float(rt), rows))
    return out


def make_validation_plot(val, path):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    cols = {0.5: "#2e9e5b", 0.9: "#1f6fb2", 1.4: "#c0504d"}
    for rt, rows in val:
        c = cols[rt]
        axes[0].scatter([r["rt_true"] for r in rows], [r["rt"] for r in rows], color=c,
                        label=f"room RT60 {rt} s", s=28)
        axes[1].scatter([r["snr_true"] for r in rows], [r["snr"] for r in rows], color=c, s=28)
        axes[2].scatter([r["c50_true"] for r in rows], [r["c50"] for r in rows], color=c, s=28)
    for ax, (lo, hi), name, unit in zip(axes, [(0.3, 1.6), (12, 22), (-3, 4)],
                                         ["RT60", "SNR", "C50"], ["s", "dB", "dB"]):
        ax.plot([lo, hi], [lo, hi], "--", color="grey", lw=1, label="perfect")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel(f"True {name} ({unit})"); ax.set_ylabel(f"Measured {name} ({unit})")
        ax.set_title(name); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Synthetic validation: measured vs known truth (27 seats, 3 rooms)", fontsize=12)
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


# ---------------------------------------------------------------------------
# Slide helpers
# ---------------------------------------------------------------------------
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
BG = os.path.join(ASSETS, "background.png")


def new_slide():
    s = prs.slides.add_slide(BLANK)
    s.shapes.add_picture(BG, 0, 0, prs.slide_width, prs.slide_height)
    return s


def text(slide, x, y, w, h, runs, size=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP):
    """runs: str, or list of paragraphs; each paragraph a str or (str, dict) tuple."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.08)
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        txt, opt = (p, {}) if isinstance(p, str) else p
        r = para.add_run()
        r.text = txt
        f = r.font
        f.name = FONT
        f.size = Pt(opt.get("size", size))
        f.bold = opt.get("bold", bold)
        f.color.rgb = opt.get("color", color)
        para.space_after = Pt(opt.get("after", 6))
    return tb


def title(slide, t, sub=None):
    text(slide, 0.6, 0.35, 12.1, 0.9, t, size=34, color=PALE, bold=True)
    if sub:
        text(slide, 0.62, 1.12, 12.1, 0.5, sub, size=15, color=MINT)


def box(slide, x, y, w, h, fill=MINT, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    shp.adjustments[0] = 0.08
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
    shp.shadow.inherit = False
    return shp


def card(slide, x, y, w, h, head, body, size=14, fill=MINT, fg=DARK):
    box(slide, x, y, w, h, fill)
    paras = [(head, {"bold": True, "size": size + 3, "color": fg, "after": 4})]
    paras += [(b, {"size": size, "color": fg, "after": 3}) for b in body]
    text(slide, x + 0.12, y + 0.1, w - 0.24, h - 0.2, paras)


def picture(slide, path, x, y, w=None, h=None, pad=0.08):
    pic = slide.shapes.add_picture(path, Inches(x + pad), Inches(y + pad),
                                   Inches(w - 2 * pad) if w else None,
                                   Inches(h - 2 * pad) if h else None)
    # white panel behind the plot
    pw, ph = pic.width + Inches(2 * pad), pic.height + Inches(2 * pad)
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), pw, ph)
    panel.adjustments[0] = 0.03
    panel.fill.solid(); panel.fill.fore_color.rgb = WHITE
    panel.line.fill.background()
    sp = slide.shapes._spTree
    sp.remove(panel._element); sp.insert(3, panel._element)   # behind the picture
    return pic


def tag(slide, x, y, label, fill=AMBER):
    shp = box(slide, x, y, 2.6, 0.38, fill)
    tf = shp.text_frame
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label
    r.font.size = Pt(12); r.font.bold = True; r.font.name = FONT; r.font.color.rgb = DARK


def footer(slide, txt):
    text(slide, 0.6, 6.95, 12.1, 0.4, txt, size=10, color=PALE)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
make_background(BG)
VAL = load_validation()
VAL_PNG = os.path.join(ASSETS, "validation_scatter.png")
make_validation_plot(VAL, VAL_PNG)

# 1. Title ------------------------------------------------------------------
s = new_slide()
text(s, 0.8, 1.6, 11.7, 1.0, "Smart Classroom Acoustic Analyzer", size=40, color=PALE, bold=True)
text(s, 0.82, 2.75, 11.7, 0.6, "Speech Clarity Assessment and Seating Optimization",
     size=24, color=MINT)
text(s, 0.82, 3.35, 11.7, 0.6, "“Every Seat Deserves to Hear Every Word.”",
     size=20, color=WHITE)
box(s, 0.8, 4.5, 6.2, 1.55)
text(s, 0.95, 4.6, 6.0, 1.4, [
    ("Stage 2: Progress Report", {"bold": True, "size": 20, "color": DARK}),
    ("Prakhar Saxena  ·  Rohit", {"size": 16, "color": DARK}),
    ("Fundamentals of Audio for Engineers · IIIT-Delhi · Monsoon 2026",
     {"size": 13, "color": DARK})])

# 2. Since Stage 1 ----------------------------------------------------------
s = new_slide()
title(s, "Since Stage 1: what changed", "Idea → working, validated measurement tool")
rows = [
    ("Metrics were vague", "Four concrete metrics with targets from standards: SNR, C50, RT60, dB(A) noise"),
    ("“Seating optimization” undefined", "Every seat rated Good / Fair / Poor → colour seat map → who should sit where"),
    ("Manual Audacity analysis", "Automated Python analyzer: phone recordings in, report + plots out"),
    ("No tools, roles or timeline", "Tool stack, named contributions and dated timeline (this deck)"),
    ("Accuracy unknown", "Validated on a synthetic room with known answers before field use"),
]
text(s, 0.7, 1.75, 4.6, 0.4, "Stage 1 gap", size=16, color=MINT, bold=True)
text(s, 5.6, 1.75, 7.0, 0.4, "Stage 2 status", size=16, color=MINT, bold=True)
for i, (a, b) in enumerate(rows):
    y = 2.2 + i * 0.92
    box(s, 0.6, y, 4.7, 0.78, DEEP)
    text(s, 0.75, y, 4.5, 0.78, a, size=15, color=PALE, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 5.5, y, 7.2, 0.78)
    text(s, 5.65, y, 7.0, 0.78, b, size=15, color=DARK, anchor=MSO_ANCHOR.MIDDLE)

# 3. Social relevance --------------------------------------------------------
s = new_slide()
title(s, "Why it matters", "In a large, noisy room, the back seats can miss the lecture")
card(s, 0.6, 1.8, 5.9, 2.4, "Indian classrooms", [
    "• 60–100+ students per room",
    "• Hard walls, glass, ceiling fans; back-benchers sit under fans",
    "• Teachers rarely use a microphone",
], size=17)
card(s, 0.6, 4.4, 5.9, 2.3, "Who is hit hardest", [
    "• Students with hearing difficulties",
    "• Students learning in a second language",
    "• Students with attention difficulties",
], size=17)
text(s, 7.0, 1.8, 5.7, 0.4, "What the standards ask for", size=18, color=MINT, bold=True)
for i, (v, d) in enumerate([("≤ 35 dB(A)", "background noise (WHO)"),
                            ("≤ 0.6 s", "reverberation time RT60 (ANSI S12.60)"),
                            ("≥ +15 dB", "speech-to-noise ratio (ASHA)")]):
    y = 2.35 + i * 1.45
    box(s, 7.0, y, 5.7, 1.25, DEEP)
    text(s, 7.15, y + 0.08, 5.4, 0.6, v, size=28, color=MINT, bold=True)
    text(s, 7.15, y + 0.72, 5.4, 0.45, d, size=14, color=PALE)

# 4. FAE concepts -> metrics ------------------------------------------------
s = new_slide()
title(s, "FAE concepts → what we measure")
concepts = [
    ("SNR (speech band)", "Band-pass 300–3400 Hz; power subtraction P_speech = P_(speech+noise) − P_noise. Target ≥ 15 dB."),
    ("RT60 via Schroeder", "Clap → impulse response → backward-integrated energy decay; EDT / T20 / T30 from the slope."),
    ("C50 clarity", "Early (0–50 ms) vs late energy at 1 kHz. Early sound helps speech; late sound smears it."),
    ("A-weighting", "IEC 61672 filter via bilinear transform: noise in dB(A), as the ear hears it."),
    ("Inverse square law", "Direct sound falls 6 dB per distance doubling; we test where the room breaks it."),
    ("FFT / Welch spectrum", "Noise spectrum + tonal peak search (40–4000 Hz) to find fan / AC hum."),
]
for i, (h, b) in enumerate(concepts):
    x = 0.6 + (i % 3) * 4.1
    y = 1.55 + (i // 3) * 2.75
    card(s, x, y, 3.9, 2.55, h, [b], size=17)

# 5. Seating optimization defined --------------------------------------------
s = new_slide()
title(s, "“Seating optimization”, defined", "Every seat gets a rating; the map drives the advice")
for i, (lab, rule, fill) in enumerate([
        ("GOOD", "SNR ≥ 15 dB  and  C50 ≥ +3 dB", RGBColor(0x2E, 0x9E, 0x5B)),
        ("FAIR", "SNR ≥ 10 dB  and  C50 ≥ 0 dB", RGBColor(0xE0, 0xA5, 0x26)),
        ("POOR", "anything worse", RGBColor(0xD1, 0x49, 0x5B))]):
    y = 1.8 + i * 1.05
    b = box(s, 0.6, y, 1.6, 0.85, fill)
    text(s, 0.6, y, 1.6, 0.85, lab, size=18, bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, 2.35, y, 4.3, 0.85, rule, size=16, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 5.1, 6.0, 1.6, [
    ("A seat is only as good as its worse metric.", {"bold": True, "color": MINT}),
    ("Loud but echoey, or clear but noisy, both fail the student.", {"color": PALE})], size=15)
card(s, 7.0, 1.8, 5.7, 4.9, "What the map is used for", [
    "• Seat students with hearing or language difficulties in the Good zone",
    "• Find Poor zones: needs a mic + speaker for the teacher",
    "• Find the cause: low SNR → noise (fans, windows); low C50 → echo (add absorption)",
    "• Fan/AC hum frequencies → which fan to service or slow down",
    "• Re-measure after a fix (fans off, curtains) to show the gain",
], size=16)

# 6. Pipeline ----------------------------------------------------------------
s = new_slide()
title(s, "System pipeline and tools", "Zero hardware spend: one phone, one speaker, open-source software")
steps = [("Record", "Phone at 9 seats (3×3 grid): noise, speech clip, clap"),
         ("Decode", "ffmpeg: any phone format → 48 kHz mono"),
         ("Analyze", "NumPy / SciPy DSP: SNR, C50, RT60, dB(A), hum"),
         ("Rate", "Good / Fair / Poor per seat"),
         ("Report", "Seat map, plots, CSV, recommendations")]
for i, (h, b) in enumerate(steps):
    x = 0.6 + i * 2.5
    card(s, x, 1.9, 2.2, 2.3, h, [b], size=14)
    if i < len(steps) - 1:
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + 2.2), Inches(3.05),
                                   Inches(x + 2.5), Inches(3.05))
        c.line.color.rgb = PALE; c.line.width = Pt(3)
text(s, 0.6, 4.6, 12.1, 0.4, "Tools", size=18, color=MINT, bold=True)
tools = ["Python 3", "NumPy", "SciPy (filters, Welch)", "Matplotlib", "ffmpeg",
         "Phone voice recorder (enhancement OFF)", "Sound-level-meter app (calibration)",
         "Streamlit (Stage 3)"]
for i, t in enumerate(tools):
    x = 0.6 + (i % 4) * 3.05
    y = 5.1 + (i // 4) * 0.8
    box(s, x, y, 2.9, 0.62, DEEP)
    text(s, x, y, 2.9, 0.62, t, size=13, color=PALE, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)

# 7. Progress: what is built ---------------------------------------------------
s = new_slide()
title(s, "Progress till date", "Analysis software complete and validated; field recordings next")
done = [
    "acoustics.py: core DSP (A-weighting, octave filters, SNR, Schroeder RT60 with noise "
    "compensation, C50, spectrum, hum peaks)",
    "analyze.py: one command turns a folder of seat recordings into a full report",
    "make_synthetic.py: virtual classroom with known RT60 / SNR / C50 for testing",
    "Validation on 3 synthetic rooms × 9 seats (27 cases)",
    "Recording protocol written (phone settings, seat grid, 3 recordings per seat)",
    "Bug found by validation and fixed: C50 start time (next slide)",
]
todo = [
    "Record a real classroom (9 seats)",
    "Calibrate with a sound-level-meter app",
    "Streamlit upload-and-report app",
    "Sabine RT60 prediction vs measured",
    "Before/after experiment (fans on/off)",
]
text(s, 0.6, 1.7, 7.4, 0.4, "Done ✓", size=18, color=MINT, bold=True)
text(s, 0.6, 2.15, 7.4, 4.6, [("✓  " + d, {"after": 10}) for d in done], size=16, color=WHITE)
card(s, 8.4, 1.7, 4.3, 4.9, "Remaining", ["• " + t for t in todo], size=17)

# 8. Validation ----------------------------------------------------------------
s = new_slide()
title(s, "Validation against known answers",
      "Synthetic rooms with known truth: direct sound (1/r) + exponentially decaying reverberant tail + fan noise")
tag(s, 10.1, 0.45, "SYNTHETIC TEST DATA")
picture(s, VAL_PNG, 0.6, 1.75, w=12.1)
summary = []
for rt, rows in VAL:
    e_rt = max(abs(r["rt"] - r["rt_true"]) / r["rt_true"] * 100 for r in rows)
    e_snr = max(abs(r["snr"] - r["snr_true"]) for r in rows)
    e_c50 = max(abs(r["c50"] - r["c50_true"]) for r in rows)
    summary.append(f"RT60 {rt} s room:  RT60 ≤ {e_rt:.1f} %   ·   SNR ≤ {e_snr:.2f} dB"
                   f"   ·   C50 ≤ {e_c50:.2f} dB")
box(s, 0.6, 5.85, 12.1, 1.05)
text(s, 0.75, 5.88, 11.9, 1.0, [("Max error over 9 seats:", {"bold": True})] +
     [(t, {"after": 0, "size": 13}) for t in summary], size=13, color=DARK)

# 9. Bug found by validation -------------------------------------------------------
s = new_slide()
title(s, "Validation caught a real bug", "Why we test on known answers before going into a classroom")
card(s, 0.6, 1.8, 5.9, 4.8, "C50: where does “t = 0” start?", [
    "C50 compares energy in the first 50 ms after the direct sound with everything later.",
    "Our first version used the loudest sample as t = 0.",
    "At far seats a reverberant reflection can be louder in the 1 kHz band than the "
    "direct sound, so t = 0 started up to 67 ms late.",
    "Fix (ISO 3382-1): t = 0 = first sample within 20 dB of the peak.",
], size=15)
for i, (v, d) in enumerate([("2.6 dB", "worst C50 error before"),
                            ("0.45 dB", "worst C50 error after (below the 1 dB just-noticeable difference)")]):
    y = 1.8 + i * 2.45
    box(s, 7.0, y, 5.7, 2.2, DEEP)
    text(s, 7.2, y + 0.2, 5.3, 0.9, v, size=44, color=MINT if i else AMBER, bold=True)
    text(s, 7.2, y + 1.2, 5.3, 0.9, d, size=15, color=PALE)

# 10. Example outputs: seat map + distance law ---------------------------------------
s = new_slide()
title(s, "What the tool produces", "Example output for the synthetic RT60 = 0.9 s room")
tag(s, 10.1, 0.45, "SYNTHETIC TEST DATA")
picture(s, os.path.join(RES, "seat_map.png"), 0.6, 1.7, h=4.6)
picture(s, os.path.join(RES, "distance_law.png"), 6.4, 1.7, w=6.3)
text(s, 6.4, 5.65, 6.3, 1.3, [
    ("FAE talking point: speech drops only ~0.8 dB per doubling, not 6 dB.", {"bold": True, "color": MINT}),
    ("Beyond the critical distance the reverberant field dominates, so moving "
     "closer barely helps, while echo still hurts C50. Absorption fixes that; "
     "loudness alone does not.", {"color": PALE})], size=13)

# 11. Decay + spectrum ------------------------------------------------------------
s = new_slide()
title(s, "Reverberation and noise diagnostics", "Example output for the synthetic RT60 = 0.9 s room")
tag(s, 10.1, 0.45, "SYNTHETIC TEST DATA")
picture(s, os.path.join(RES, "decay_curves.png"), 0.6, 1.7, w=6.0)
picture(s, os.path.join(RES, "noise_spectrum.png"), 6.75, 1.7, w=6.0)
text(s, 0.6, 5.6, 6.0, 1.3, [
    ("Schroeder decay curves", {"bold": True, "color": MINT}),
    ("Slope → RT60. If the clap is too quiet over the noise (< 15 dB), the tool "
     "refuses to report RT60 instead of guessing.", {"color": PALE})], size=13)
text(s, 6.75, 5.6, 6.0, 1.3, [
    ("Noise spectrum (Welch)", {"bold": True, "color": MINT}),
    ("Tonal peaks at 120 / 240 / 360 Hz = fan blade-pass hum. Window-side seats "
     "are noisier → lower SNR.", {"color": PALE})], size=13)

# 12. Recommendations ---------------------------------------------------------------
s = new_slide()
title(s, "Automatic recommendations", "Generated by analyze.py from the measurements (synthetic room shown)")
tag(s, 10.1, 0.45, "SYNTHETIC TEST DATA")
recs = [l[2:].strip() for l in open(os.path.join(RES, "report.md")) if l.startswith("- ")]
for i, r in enumerate(recs[:3]):
    card(s, 0.6, 1.8 + i * 1.6, 12.1, 1.4, ["Absorption", "Seating + amplification", "Noise source"][i],
         [r], size=14)

# 13. Contributions -------------------------------------------------------------------
s = new_slide()
title(s, "Contribution of each member", "Split ≈ 50 / 50 · “lead” = who drove that task")
card(s, 0.6, 1.7, 5.95, 4.95, "Prakhar Saxena", [
    "Code (lead)",
    "• acoustics.py core DSP: A-weighting, filters, SNR power subtraction",
    "• Schroeder RT60 with noise compensation (EDT / T20 / T30)",
    "• Validation runs; found and fixed the C50 onset bug",
    "Research (lead)",
    "• Room-acoustics standards: ANSI S12.60 (RT60), ISO 3382 (C50, RT60 method)",
    "• Stage 2 progress report deck",
], size=16)
card(s, 6.75, 1.7, 5.95, 4.95, "Rohit", [
    "Code (lead)",
    "• analyze.py pipeline: seats.csv, per-seat analysis, seat map & plots",
    "• Recommendation rules + fan/AC hum (tonal peak) detection",
    "• make_synthetic.py: virtual classroom with known truth",
    "Research (lead)",
    "• WHO noise, ASHA SNR, Indian classroom context",
    "• Phone recording protocol + README documentation",
], size=16)
footer(s, "We worked in joint sessions, so both members reviewed and contributed to every part. "
          "Both submit this same deck individually.")

# 14. Teamwork ---------------------------------------------------------------------
s = new_slide()
title(s, "Teamwork and key decisions", "Decisions we discussed and agreed on together")
decisions = [
    ("Automate instead of Audacity", "Stage 1 planned manual Audacity analysis; we moved to Python so 9 seats × 3 recordings take one command."),
    ("Test on a fake room first", "Built a synthetic room with known answers before recording. It caught the C50 bug before any real data."),
    ("Refuse rather than guess", "If the clap is too quiet over the noise, report “no RT60” instead of a wrong number."),
    ("Relative over absolute", "Phone mics are uncalibrated: compare seats with each other; one sound-level-meter reading gives estimated dB(A)."),
]
for i, (h, b) in enumerate(decisions):
    x = 0.6 + (i % 2) * 6.15
    y = 1.75 + (i // 2) * 2.55
    card(s, x, y, 5.95, 2.35, h, [b], size=17)

# 15. Challenges ---------------------------------------------------------------
s = new_slide()
title(s, "Challenges and how we handled them")
ch = [
    ("Phone mic is not a measurement mic", "Auto gain and noise cancellation change levels.",
     "Enhancement OFF, same phone for all seats, relative comparison + optional calibration."),
    ("Clap dynamic range", "T30 needs 45 dB above noise; a clap in a fan room gets ~25 dB.",
     "Fans OFF for claps, balloon-pop option, automatic EDT/T20/T30 choice, refuse below 15 dB."),
    ("Reverberant rooms break the 1/r² law", "Speech level is nearly flat past the critical distance.",
     "Report C50 alongside SNR: loudness alone hides the echo problem."),
    ("Defining t = 0 for C50", "Loudest sample ≠ direct sound at far seats.",
     "ISO 3382-1 onset detection (-20 dB threshold), verified on synthetic data."),
]
for i, (h, p, f) in enumerate(ch):
    y = 1.45 + i * 1.38
    box(s, 0.6, y, 4.0, 1.2, DEEP)
    text(s, 0.75, y, 3.8, 1.2, h, size=15, color=MINT, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 4.75, y, 3.6, 1.2, DEEP)
    text(s, 4.85, y, 3.4, 1.2, p, size=13, color=PALE, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 8.5, y, 4.2, 1.2)
    text(s, 8.6, y, 4.0, 1.2, f, size=13, color=DARK, anchor=MSO_ANCHOR.MIDDLE)

# 16. Timeline ------------------------------------------------------------------
s = new_slide()
title(s, "Timeline to completion", "Baseline for judging progress at Stage 3")
tl = [
    ("18 Oct", "Stage 1 idea submitted", True),
    ("19 Oct – 14 Nov", "Metrics, DSP analyzer, synthetic validation, protocol", True),
    ("15 Nov", "Stage 2 progress report", True),
    ("16 – 22 Nov", "Record 1–2 real classrooms (9 seats each) + calibrate; run analyzer", False),
    ("23 – 29 Nov", "Streamlit app: upload recordings → seat map + report in browser", False),
    ("30 Nov – 6 Dec", "Sabine RT60 prediction vs measured; before/after (fans on/off, curtains)", False),
    ("Stage 3 (TBA)", "Online presentation + live demo", False),
    ("Final (TBA)", "Final report, code and recordings", False),
]
y0 = 1.65
line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(2.95), Inches(y0 + 0.2),
                              Inches(2.95), Inches(y0 + 0.2 + 0.64 * (len(tl) - 1)))
line.line.color.rgb = MINT; line.line.width = Pt(3)
for i, (d, what, ok) in enumerate(tl):
    y = y0 + i * 0.64
    text(s, 0.4, y, 2.35, 0.45, d, size=14, color=MINT, bold=True, align=PP_ALIGN.RIGHT)
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(2.82), Inches(y + 0.08), Inches(0.26), Inches(0.26))
    dot.fill.solid(); dot.fill.fore_color.rgb = MINT if ok else DEEP
    dot.line.color.rgb = MINT
    text(s, 3.3, y, 7.6, 0.45, what, size=14, color=WHITE if ok else PALE)
    tag_txt = "DONE" if ok else "PLANNED"
    b = box(s, 11.2, y + 0.04, 1.4, 0.36, MINT if ok else DEEP, line=MINT)
    text(s, 11.2, y + 0.04, 1.4, 0.36, tag_txt, size=10, bold=True,
         color=DARK if ok else MINT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# 17. Thank you -------------------------------------------------------------------
s = new_slide()
text(s, 0.8, 2.5, 11.7, 1.2, "Thank you", size=54, color=PALE, bold=True)
text(s, 0.82, 3.7, 11.7, 0.6, "Every Seat Deserves to Hear Every Word.", size=22, color=MINT)
text(s, 0.82, 4.5, 11.7, 0.5, "Prakhar Saxena  ·  Rohit", size=16, color=WHITE)

out = os.path.join(HERE, "FAE_Stage2_Progress_Report.pptx")
prs.save(out)
print("Saved", out, "with", len(prs.slides), "slides")
