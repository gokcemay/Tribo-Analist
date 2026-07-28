# Tribo-Analist — Demo Video Script

A step-by-step script for recording a walkthrough video of both tools. Pairs with [USAGE.md](USAGE.md) — record your screen (Win+G / Xbox Game Bar, or OBS Studio) while following these beats. Each beat lists what to show, what to click, and suggested narration. Target length: ~4–5 minutes.

Tips before recording:
- Maximize the window before you start each section — cleaner frame, easier to follow.
- Pause ~1 second after each click so viewers can register what changed before you talk over it.
- Keep the mouse still while narrating a static screen; only move it when you're about to click.

---

## Scene 1 — Intro (10–15s)

**Show:** Launcher window (`python main.py`, or double-click `Tribo-Analist.exe`).

**Say:**
> "This is Tribo-Analist — two tools for post-processing tribometer and profilometer output. On the left, the CSM tribometer friction analyser; on the right, the Mitutoyo profilometer wear-track analyser. Let's start with the wear-track tool."

**Do:** Click **Launch Mitutoyo Profilometer Analyser**.

---

## Scene 2 — Loading data (15–20s)

**Show:** Empty Roughness Analyser window, sidebar with **Select Roughness Folder** and the sample list.

**Say:**
> "The tool groups .xls files into samples by filename — A1-01 through A1-04 all belong to sample A1. Let's select one."

**Do:** Click **Select Roughness Folder** if not already loaded, then click sample **A1** in the list.

---

## Scene 3 — Automatic wear-track detection (30–40s)

**Show:** All four A1 measurements loaded in the 2×2 grid, each with a green **AUTO ✓** badge.

**Say:**
> "As soon as a sample is selected, the tool automatically finds the wear track in every measurement — no manual clicking needed. Each plot gets a green AUTO badge with a confidence score. The two boundary points, the connecting line, and the shaded cross-sectional area are all placed automatically."

**Do:** Point at one plot's badge, then at the sidebar's **Calculated Areas** panel showing the coordinates and area for A1-01.

> "It works by fitting the un-worn surface trend and flagging valleys that are both much deeper and much wider than the background roughness — that's what tells a real wear scar apart from ordinary surface noise."

---

## Scene 4 — When detection can't decide (25–35s)

**Show:** Switch to sample **C1** — one measurement auto-detected, three flagged manual.

**Say:**
> "Not every measurement has a track deep or wide enough to tell apart from roughness — and the tool is honest about that. Here, only C1-01 was detected; the other three get an amber MANUAL SELECTION badge."

**Do:** Point at the sidebar text under one manual card (the reason, e.g. "No valley deeper than 4x the roughness").

> "It tells you exactly why it gave up, so you know it's not guessing."

---

## Scene 5 — Manual point selection (20–30s)

**Show:** Click on one of the manual-flagged plots.

**Say:**
> "For any measurement — flagged or not — you can just click two points on the curve yourself: first click sets P1, second sets P2 and computes the area, third click resets."

**Do:** Click twice on C1-02's curve to place P1 and P2, and show the area appearing in the sidebar.

---

## Scene 6 — Wear-rate calculation (20–25s)

**Show:** Sidebar's Radius / Distance / Load fields and **Calculate Specific Wear Rate** button.

**Say:**
> "Enter your test parameters — counter-ball radius, sliding distance, applied load — and calculate the specific wear rate. It's saved automatically per sample."

**Do:** Click **Calculate Specific Wear Rate**, point at the resulting wear volume / wear rate labels.

---

## Scene 7 — Batch analysis (45–60s)

**Show:** Click **Batch Analysis (All Samples)**.

**Say:**
> "For a full dataset, Batch Analysis processes every sample at once."

**Do:** Show the **Measurement Selection** tab — point out the pre-checked auto-detected rows and the disabled/unchecked manual ones.

> "Every measurement is listed with its detection result. Anything that couldn't be auto-detected is unchecked and can't be included in the average — but you can uncheck anything else too, and the graphs update instantly."

**Do:** Uncheck one measurement to demonstrate the live update, then switch to the **Averaged Tracks** tab.

> "This tab averages each sample's wear-track profiles — baseline-corrected so the surface sits at zero, and centered on the track — so you can compare the shape and depth across samples directly."

**Do:** Switch to the **Specific Wear Rate** tab.

> "And this is the specific wear rate across every sample, computed from those same checked measurements. Both graphs have a Save Graph button underneath, exporting a 300 DPI PNG."

---

## Scene 8 — Switching to the friction tool (10s)

**Show:** Close the roughness analyser (or go back to the launcher) and open the CSM Tribometer Analyser.

**Say:**
> "Now let's look at the other tool — friction coefficient analysis from the CSM tribometer."

---

## Scene 9 — Single friction curve (20–25s)

**Show:** Select one `.txt` file, click **Plot Selected**.

**Say:**
> "Pick a file, and it plots friction coefficient against sliding distance — the raw signal in the background, with a moving-average trend on top. The averaging window is adjustable from the sidebar."

**Do:** Drag the window-size slider to show the trend line change.

---

## Scene 10 — Overlay mode (15–20s)

**Show:** Check **Overlay Mode**, select all files, **Plot Selected** again.

**Say:**
> "Overlay mode puts several tests on the same axes for direct comparison instead of paging through them one at a time."

---

## Scene 11 — Average µ comparison (15–20s)

**Show:** Click the **Average µ Comparison** tab.

**Say:**
> "And this tab summarizes the mean friction coefficient per file as a bar chart — useful for a quick comparison across an entire test series."

---

## Scene 12 — Outro (10s)

**Show:** Back to the launcher, or a still frame of both tools.

**Say:**
> "That's Tribo-Analist — automatic wear-track detection with a manual fallback, batch analysis across a full dataset, and friction-curve comparison, all in one place. Links to the code and full written guide are in the description."

---

## Suggested on-screen text / description box

```
Tribo-Analist — automatic wear-track detection & friction analysis for tribometer/profilometer data
Source & full usage guide: https://github.com/gokcemay/Tribo-Analist
```
