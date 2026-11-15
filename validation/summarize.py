"""Compare analyzer output with synthetic ground truth for each RT60 room."""
import csv, json, sys
import numpy as np
rows_out = []
for rt in ("0.5", "0.9", "1.4"):
    truth = json.load(open(f"validation/synth_rt{rt}/truth.json"))
    res = {r["seat"]: r for r in csv.DictReader(open(f"validation/results_rt{rt}/results.csv"))}
    e_rt, e_snr, e_c50, methods = [], [], [], set()
    for seat, t in truth.items():
        m = res[seat]
        f = lambda k: float(m[k]) if m[k] not in ("", "nan") else np.nan
        e_rt.append(100 * (f("rt60_s") - t["rt60"]) / t["rt60"])
        e_snr.append(f("snr_db") - t["snr_db"])
        e_c50.append(f("c50_db") - t["c50_db"])
        methods.add(m["rt60_method"])
    a = lambda x: np.nanmax(np.abs(x))
    print(f"RT60 {rt}s: RT60 err max {a(e_rt):.1f}% (mean {np.nanmean(e_rt):+.1f}%), "
          f"SNR err max {a(e_snr):.2f} dB, C50 err max {a(e_c50):.2f} dB, "
          f"C50 within 0.1 dB: {sum(abs(np.array(e_c50))<=0.1)}/9, method {methods}")
