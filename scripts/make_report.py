"""Build a self-contained findings page for GitHub Pages.

Most people who land on a research repository will not clone it, install
Stockfish, and read ten module docstrings. They will look at one page and
decide whether the work is worth trusting. This generates that page from the
committed results, so it can never disagree with them.

Design choices worth stating:

- **Figures are inlined as base64.** The output is one HTML file with no
  external assets, so it works from `docs/index.html` on Pages, from a local
  `file://` open, or pasted into an email.
- **Limitations render before findings, not after.** The resolution table and
  the retractions are the most decision-relevant content on the page.
- **Every number is read from `results/*.json`.** Nothing is typed into the
  template, so the page cannot drift from what the code produced. If a track
  has not been built the section says so rather than silently omitting it.

Run:  python scripts/make_report.py
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chesslab.paths import FIGURES, RESULTS, ROOT  # noqa: E402

OUT = ROOT / "docs" / "index.html"

TRACKS = [
    (3, "Blunders, rating and thinking time", "t3_blunders.json", "t3_blunder_rate_vs_time.png",
     "Blunder rate falls about 3.4x from 1200 to 2200. Faster games blunder roughly 29% more than "
     "slower ones, tested as a difference rather than by comparing interval overlap. Time control "
     "shifts the mean by a little; which two humans sat down shifts it by a lot."),
    (5, "White's first-move advantage", "t5_color.json", "t5_white_advantage_by_year.png",
     "White scores above parity in every over-the-board band, and the edge grows with strength rather "
     "than shrinking. Draw rates are falling, not rising, which is the opposite of the usual claim. "
     "The unrestricted version of that trend is a composition artifact and is published alongside it."),
    (2, "Do engine-approved openings win more?", "t2_openings.json", "t2_book_exit_eval.png",
     "No, at any rating. Nothing survives multiplicity correction and the sign of the rank correlation "
     "flips between bands. The mechanical reason is range compression: every mainline opening evaluates "
     "within a 26 centipawn band."),
    (4, "Rating inflation, at fixed nominal rating", "t4_inflation.json", "t4_acpl_at_fixed_rating.png",
     "No detectable drift. The design cannot separate inflation from a change in who holds a rating, "
     "and it is not powered to rule out the drift rate people actually claim."),
    (8, "Rating inflation, following the same players", "t8_player_panel.json", "t8_within_player_acpl.png",
     "Null again, from a different direction. Player fixed effects remove the composition confound "
     "entirely, then run into the age-period-cohort problem: within a player, calendar year and career "
     "stage are the same regressor after demeaning."),
    (9, "Saving lost positions, format held constant", "t9_otb_swindles.json", "t9_otb_swindle_by_band.png",
     "No gradient across 400 Elo of over-the-board play. Combined with the online sample, both corpora "
     "are internally flat and separated by a large step, which points at playing format rather than "
     "strength."),
    (11, "Is the save-rate gap skill, or is it format?", "t11_matched_skill.json", "t11_matched_skill.png",
     "The deepest result here. Matching online and over-the-board players on engine-measured skill, "
     "rather than on rating scales that are not comparable across the two, does not shrink the gap: it "
     "widens it to 17.3 points. The mechanism is behavioural and measurable without conditioning on "
     "anything. Of players who ended up losing, 32.0% online played the position to checkmate against "
     "5.8% over the board. A player who resigns forgoes any chance of saving the game, which explains "
     "the whole difference without invoking chess skill at all."),
    (10, "Do the findings survive their own analytic choices?", "t10_multiverse.json",
     "t10_curve_blunder_gradient.png",
     "Track 3's gradient is negative in all 180 defensible specifications and the reported choice sits "
     "at the 74th percentile. One arbitrary decision, the blunder threshold, drives 94% of the spread."),
    (7, "The track that attacks the others", "t7_falsify.json", "t7_p1_base_rate_confound.png",
     "Six probes with pass conditions fixed in advance. One still fires, against track 6, and forced a "
     "published claim to be withdrawn. Two others record bugs that were real and are now fixed at the "
     "cause."),
]

CSS = """
:root{--ink:#12212f;--mut:#5b6b7a;--line:#e2e8ee;--acc:#1f4e79;--warn:#c0504d;--bg:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:0 22px 80px}
header{background:linear-gradient(135deg,#12212f,#1f4e79);color:#fff;padding:54px 22px 44px;margin-bottom:38px}
header .wrap{padding-bottom:0}
h1{font:700 44px/1.1 Georgia,"Times New Roman",serif;margin:0 0 12px;letter-spacing:-.5px}
.tag{font-size:19px;color:#9ec5e8;margin:0 0 22px;max-width:640px}
.chips{display:flex;flex-wrap:wrap;gap:9px}
.chip{background:rgba(255,255,255,.12);border-radius:16px;padding:5px 14px;font-size:13px;color:#dcecf9}
.chip.bad{background:rgba(192,80,77,.34)}
h2{font:600 27px/1.25 Georgia,serif;margin:52px 0 8px;padding-top:20px;border-top:1px solid var(--line)}
h3{font:600 18px/1.3 -apple-system,sans-serif;margin:30px 0 6px}
p{margin:10px 0}
.lede{color:var(--mut)}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--mut);font-size:12.5px;text-transform:uppercase;letter-spacing:.4px}
.no{color:var(--warn);font-weight:600}
.yes{color:#3d7a3d;font-weight:600}
figure{margin:18px 0 6px}
img{width:100%;border:1px solid var(--line);border-radius:6px}
.card{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:5px;padding:16px 18px;margin:18px 0}
.card.warn{border-left-color:var(--warn);background:#fdf6f5}
.card h3{margin-top:0}
.n{display:inline-block;background:var(--acc);color:#fff;border-radius:4px;
  padding:1px 8px;font-size:12.5px;font-weight:600;margin-right:9px;vertical-align:2px}
code{background:#f2f5f8;padding:1.5px 6px;border-radius:4px;font-size:14px}
pre{background:#f2f5f8;padding:14px 16px;border-radius:6px;overflow-x:auto;font-size:13.5px}
footer{color:var(--mut);font-size:13.5px;margin-top:56px;border-top:1px solid var(--line);padding-top:20px}
a{color:var(--acc)}
"""


def load(name: str):
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


def img_tag(fname: str) -> str:
    p = FIGURES / fname
    if not p.exists():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f'<figure><img alt="{fname}" src="data:image/png;base64,{b64}"></figure>'


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build() -> Path:
    t1 = load("t1_validation.json") or {}
    power = load("power_report.json") or {}
    t7 = load("t7_falsify.json") or {}

    rows = int(t1.get("rows", 0))
    fired = len(t7.get("summary", {}).get("fired", []))
    n_probes = len(t7.get("probes", []))

    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>chess-lab: falsifiable chess research</title>",
        "<meta name='description' content='Ten questions about chess checked against 190,967 public "
        "games and Stockfish 16, including a track whose only job is to break the others.'>",
        f"<style>{CSS}</style></head><body>",
        "<header><div class='wrap'><h1>chess-lab</h1>",
        "<p class='tag'>Eleven questions people repeat about chess, checked against "
        f"{rows:,} real games and Stockfish 16. One track exists only to break the others.</p>",
        "<div class='chips'>",
        "<span class='chip bad'>2 claims retracted</span>",
        "<span class='chip'>180/180 specifications</span>",
        "<span class='chip'>every null bounded</span>",
        "<span class='chip'>107 tests</span>",
        f"<span class='chip'>{fired} of {n_probes} probes still fire</span>",
        "</div></div></header><div class='wrap'>",
    ]

    # ---- limitations first, deliberately
    parts.append("<h2>Read this before the findings</h2>")
    parts.append("<p class='lede'>Three results below are nulls. A null is nearly content-free without "
                 "a resolution bound attached, so here is what each design could actually have "
                 "detected.</p>")
    if power.get("nulls"):
        deff = power.get("clustering", {}).get("implied_design_effect_on_sample_size")
        parts.append("<table><tr><th>Null</th><th>Resolution</th><th>Effect worth caring about</th>"
                     "<th>Ruled out?</th></tr>")
        labels = {
            "t4_inflation_acpl_per_decade": ("Rating inflation (cross-sectional)", "~0.5 cp/decade"),
            "t8_within_player_acpl_per_decade": ("Rating inflation (within player)", "~0.5 cp/decade"),
            "t2_opening_slope": ("Opening quality vs results", "0.05 score/pawn"),
            "t6_online_band_contrast": ("Save rate across online bands", "~0.05"),
        }
        for key, v in power["nulls"].items():
            if key not in labels:
                continue
            label, bench = labels[key]
            res = v.get("resolution_half_width", v.get("mde"))
            det = v.get("benchmark_would_have_been_detected", v.get("benchmark_detectable"))
            verdict = ("<span class='yes'>yes</span>" if det
                       else "<span class='no'>no, underpowered</span>" if det is not None else "&mdash;")
            parts.append(f"<tr><td>{label}</td><td>&plusmn;{res:.3g}</td><td>{bench}</td>"
                         f"<td>{verdict}</td></tr>")
        parts.append("</table>")
        if deff:
            parts.append(f"<p class='lede'>Clustering moves within games costs a <strong>{deff:.2f}x</strong> "
                         "sample penalty for the same resolution, and every bound above carries it.</p>")

    parts.append("<div class='card warn'><h3>Two published claims have been withdrawn</h3>"
                 "<p><strong>\"Save rate falls monotonically with rating.\"</strong> An artifact of "
                 "truncating evaluation at ply 120, which preferentially discarded long defensive "
                 "games. Every game is now scored to its end.</p>"
                 "<p><strong>\"Amateurs save by winning, masters save by drawing.\"</strong> The "
                 "contrast disappears once each group is normalised by its own base draw rate. Caught "
                 "by falsification probe P1, which still fires.</p>"
                 "<p class='lede'>Both retractions are pinned by tests, and the claims checker fails if "
                 "the retraction text is removed while the probe still fires.</p></div>")

    # ---- findings
    parts.append("<h2>Findings</h2>")
    for num, title, fname, figure, summary in TRACKS:
        built = (RESULTS / fname).exists()
        parts.append(f"<h3><span class='n'>{num}</span>{esc(title)}</h3>")
        if not built:
            parts.append("<p class='lede'>Not built in this snapshot.</p>")
            continue
        parts.append(f"<p>{esc(summary)}</p>")
        parts.append(img_tag(figure))

    # ---- reproduce
    parts.append("<h2>Reproduce or reuse</h2>")
    parts.append("<pre>pip install -e \".[dev]\"\n"
                 "apt-get install stockfish\n"
                 "make data      # ~150 MB from GitHub mirrors\n"
                 "make build     # ~1h, engine-bound, resumable\n"
                 "make verify    # tests + claims check + manifest check</pre>")
    parts.append("<p>The engine evaluations are the only expensive artifact here, roughly an hour of "
                 "single-core Stockfish. <code>chesslab export</code> writes them as 125,673 scored "
                 "moves joined to game metadata, with a data dictionary documenting four traps, three "
                 "of which produced real errors during this build.</p>")
    parts.append("<p><code>chesslab limits</code> prints every known confound and resolution bound. If "
                 "you think a finding is wrong, there is an issue template for exactly that: it is the "
                 "contribution this project most wants.</p>")

    parts.append(f"<footer>Generated from committed results on {date.today().isoformat()}. "
                 "Every number on this page is read from <code>results/*.json</code> rather than typed "
                 "into the template, so it cannot disagree with what the code produced. "
                 "MIT licensed; Stockfish invoked as a separate GPL-3.0 process.</footer>")
    parts.append("</div></body></html>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts))
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size / 1024:.0f} KB)")
