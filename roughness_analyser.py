import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import Cursor

# Dark theme color palette (Catppuccin Mocha inspired for premium look)
COLOR_BG = "#1E1E2E"         # Deep charcoal/navy background
COLOR_SIDEBAR = "#11111B"    # Darker sidebar background
COLOR_CARD = "#181825"       # Sub-panel/Card background
COLOR_ACCENT = "#89B4FA"     # Vibrant blue accent
COLOR_HIGHLIGHT = "#e84393"  # Vibrant pink highlight for selections and area
COLOR_P1 = "#0984e3"         # Vibrant blue for the first selected point (P1)
COLOR_SUCCESS = "#A6E3A1"    # Green accent for success messages
COLOR_TEXT = "#CDD6F4"       # Primary light text
COLOR_TEXT_MUTED = "#A6ADC8" # Muted text
COLOR_BORDER = "#313244"     # Panel borders
COLOR_BUTTON = "#313244"     # Default button background
COLOR_BUTTON_HOVER = "#45475A" # Button hover
COLOR_WARN = "#F9E2AF"       # Amber for "needs manual review"

# --- Automatic wear-track detection -----------------------------------------
# A wear track is a valley that is both much deeper than the surface roughness
# and much wider than any roughness feature. The routines below locate the
# un-worn surface trend, measure how far the profile drops below it, and keep
# only valleys that clearly stand out from the roughness noise floor.

DETECT_MIN_DEPTH_SIGMA = 4.0   # valley must be this many roughness sigmas deep
DETECT_MIN_WIDTH_FRAC = 0.02   # ...and this fraction of the trace long
DETECT_MIN_WIDTH_ABS = 0.05    # ...with an absolute floor in X units (mm)
DETECT_MAX_WIDTH_FRAC = 0.80   # a valley wider than this leaves no reference


def _trapz(yv, xv):
    """Trapezoidal integration (compatible with both NumPy 1.x and 2.x)."""
    if len(xv) < 2:
        return 0.0
    return float(np.sum((yv[:-1] + yv[1:]) / 2.0 * np.diff(xv)))


def _moving_average(y, w):
    """Smooths point-to-point roughness noise without shifting features."""
    if w < 3:
        return y.copy()
    if w % 2 == 0:
        w += 1
    pad = w // 2
    yp = np.pad(y, pad, mode='edge')
    return np.convolve(yp, np.ones(w, dtype=float) / w, mode='valid')


def _mad_sigma(v):
    """Outlier-resistant standard deviation estimate."""
    if len(v) == 0:
        return 0.0
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def _robust_baseline(x, y, deg=1, iters=20):
    """
    Fits the trend of the *un-worn* surface.

    A plain least-squares fit would be dragged down into the wear groove, so
    points sitting far below the current trend are rejected and the fit is
    repeated until it settles on the intact surface.
    """
    span = x.max() - x.min()
    xn = (x - x.mean()) / (span / 2.0 if span > 0 else 1.0)
    keep = np.ones(len(x), dtype=bool)
    coef = np.polyfit(xn, y, deg)
    for _ in range(iters):
        coef = np.polyfit(xn[keep], y[keep], deg)
        r = y - np.polyval(coef, xn)
        s = _mad_sigma(r[keep])
        if s <= 0:
            break
        new = (r > -2.0 * s) & (r < 3.0 * s)
        if new.sum() < max(50, 0.15 * len(y)):
            break
        if np.array_equal(new, keep):
            break
        keep = new
    return np.polyval(coef, xn), keep


def _true_runs(mask):
    """Returns (start, end_inclusive) index pairs for each contiguous True run."""
    if not mask.any():
        return []
    edges = np.flatnonzero(np.diff(mask.astype(np.int8)))
    starts = np.r_[0, edges + 1]
    ends = np.r_[edges, len(mask) - 1]
    return [(s, e) for s, e in zip(starts, ends) if mask[s]]


def detect_wear_scar(x, y,
                     min_depth_sigma=DETECT_MIN_DEPTH_SIGMA,
                     min_width_frac=DETECT_MIN_WIDTH_FRAC,
                     min_width_abs=DETECT_MIN_WIDTH_ABS,
                     max_width_frac=DETECT_MAX_WIDTH_FRAC):
    """
    Locates the wear track in a stylus profile.

    Returns a dict with:
        status     : 'ok' | 'ambiguous' | 'none'
        i1, i2     : endpoint indices into x/y (None when nothing was found)
        depth      : maximum drop below the un-worn surface
        width      : track width in X units
        snr        : depth divided by the roughness noise level
        confidence : 0..1 heuristic score
        reason     : human-readable explanation, shown to the user
    """
    out = {'status': 'none', 'i1': None, 'i2': None, 'reason': '',
           'depth': 0.0, 'width': 0.0, 'area': 0.0, 'snr': 0.0, 'confidence': 0.0}

    n = len(x)
    if n < 200:
        out['reason'] = "Too few data points to analyse"
        return out

    L = float(x[-1] - x[0])
    if L <= 0:
        out['reason'] = "Invalid X range"
        return out

    # 1) Suppress point-to-point roughness noise (window ~1% of the trace).
    ys = _moving_average(y, max(5, int(round(0.01 * n))))

    # 2) Locate the un-worn surface and measure the drop below it.
    base, keep = _robust_baseline(x, ys, deg=1)
    d = base - ys                       # positive => below the original surface
    sigma = _mad_sigma((ys - base)[keep]) or _mad_sigma(ys - base)
    if sigma <= 0:
        out['reason'] = "Flat or degenerate profile"
        return out

    dpeak = float(d.max())
    out['snr'] = dpeak / sigma
    if dpeak <= 0:
        out['reason'] = "No valley below the surface trend"
        return out

    # 3) Hysteresis segmentation: find a strong core, then grow out to the foot.
    hi = max(min_depth_sigma * sigma, 0.45 * dpeak)
    lo = max(0.5 * sigma, 0.05 * dpeak)

    cores = _true_runs(d > hi)
    if not cores:
        out['reason'] = (f"No valley deeper than {min_depth_sigma:.0f}x the roughness "
                         f"(best is {out['snr']:.1f}x)")
        return out

    # Walk outwards until the profile reaches the groove foot, or stops
    # descending -- the latter catches the shoulder / pile-up ridge and keeps a
    # curved un-worn surface from swallowing the whole trace.
    rise_tol = max(0.5 * sigma, 0.02 * dpeak)

    def walk(start, step):
        i = start
        run_min = d[i]
        while 0 <= i + step <= n - 1:
            v = d[i + step]
            if v <= lo:
                return i + step
            if v > run_min + rise_tol:
                return i
            run_min = min(run_min, v)
            i += step
        return i

    cands = []
    for s, e in cores:
        i1, i2 = walk(s, -1), walk(e, +1)
        cands.append({'i1': i1, 'i2': i2,
                      'depth': float(d[s:e + 1].max()),
                      'width': float(x[i2] - x[i1]),
                      'area': _trapz(np.clip(d[i1:i2 + 1], 0, None), x[i1:i2 + 1])})

    # Merge candidates whose grown extents overlap.
    cands.sort(key=lambda c: c['i1'])
    merged = [cands[0]]
    for c in cands[1:]:
        prev = merged[-1]
        if c['i1'] <= prev['i2']:
            prev['i2'] = max(prev['i2'], c['i2'])
            prev['depth'] = max(prev['depth'], c['depth'])
            prev['width'] = float(x[prev['i2']] - x[prev['i1']])
            prev['area'] = _trapz(np.clip(d[prev['i1']:prev['i2'] + 1], 0, None),
                                  x[prev['i1']:prev['i2'] + 1])
        else:
            merged.append(c)

    min_width = max(min_width_abs, min_width_frac * L)
    valid = [c for c in merged if c['width'] >= min_width]
    if not valid:
        widest = max(merged, key=lambda c: c['width'])
        out['reason'] = (f"Deepest valley is only {widest['width']:.3f} wide "
                         f"(needs {min_width:.3f}) - looks like roughness, not a track")
        return out

    valid.sort(key=lambda c: c['area'], reverse=True)
    best = valid[0]

    if best['width'] > max_width_frac * L:
        out.update(best)
        out['reason'] = "Valley spans nearly the whole trace - no un-worn surface to reference"
        return out

    # A track touching a trace end has no shoulder on that side to measure from.
    edge_gap = max(3, int(0.005 * n))
    if best['i1'] <= edge_gap or best['i2'] >= n - 1 - edge_gap:
        out.update(best)
        out['reason'] = "Valley runs off the edge of the trace"
        return out

    if len(valid) > 1 and valid[1]['area'] > 0.55 * best['area']:
        out.update(best)
        out['status'] = 'ambiguous'
        out['reason'] = f"{len(valid)} valleys of comparable size - cannot tell which is the track"
        return out

    depth_score = min(1.0, (best['depth'] / sigma) / 12.0)
    width_score = min(1.0, best['width'] / (4.0 * min_width))
    sep_score = 1.0 if len(valid) == 1 else min(1.0, 1.0 - valid[1]['area'] / best['area'])

    out.update(best)
    out['status'] = 'ok'
    out['confidence'] = float(0.5 * depth_score + 0.25 * width_score + 0.25 * sep_score)
    out['reason'] = "Detected"
    return out


class RoughnessAnalyserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Roughness Data Analyser & Area Calculator")
        self.root.geometry("1300x880")
        self.root.minsize(1000, 750)
        self.root.configure(bg=COLOR_BG)
        
        # State variables
        # Default directory is the Roughness folder in the script folder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_dir = os.path.join(script_dir, "Roughness")
        if not os.path.exists(self.current_dir):
            self.current_dir = script_dir # Fallback
            
        self.samples = {}       # Unique samples: {sample_name: [list of files]}
        self.selected_sample = None
        self.current_measurements = [] # List of filenames for the selected sample (max 4)
        
        self.loaded_data = {}   # Cached parsed data: {filename: (x, y)}
        self.raw_data = {}      # Unfiltered profile (cols C&D): {filename: (x, y)}
        self.detections = {0: None, 1: None, 2: None, 3: None} # Auto-detect result per subplot
        self.auto_detect_enabled = True  # Run detection automatically on sample load
        # 'filtered' = cols E&F (original behaviour), 'raw' = cols C&D
        self.profile_source = tk.StringVar(value='filtered')
        self.clicks = {0: [], 1: [], 2: [], 3: []} # Snapped indices clicked for each subplot: {ax_idx: [idx1, idx2]}
        self.computed_areas = {0: None, 1: None, 2: None, 3: None} # Saved area results: {ax_idx: float or None}
        self.clicked_coords = {0: [None, None], 1: [None, None], 2: [None, None], 3: [None, None]} # Clicked coordinates for display: {ax_idx: [(x1,y1), (x2,y2)]}
        self.cursors = {0: None, 1: None, 2: None, 3: None} # Crosshair cursors for subplots
        self.wear_rates = {} # Saved wear rates: {sample_name: {radius, distance, load, avg_area, volume, wear_rate}}
        
        # Canvas state
        self.fig = None
        self.axes = None
        self.canvas = None
        
        # UI Elements setup
        self.setup_styles()
        self.build_ui()
        
        # Load the default directory
        self.load_directory(self.current_dir)

    def setup_styles(self):
        """Set up styling and configurations for the ttk widgets."""
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure styles to match the dark theme
        self.style.configure('.', bg=COLOR_BG, fg=COLOR_TEXT)
        self.style.configure("Custom.TLabel", bg=COLOR_CARD, fg=COLOR_TEXT, font=("Segoe UI", 10))
        
        # Scrollbar styling
        self.style.configure(
            "TScrollbar",
            gripcount=0,
            background=COLOR_BORDER,
            troughcolor=COLOR_SIDEBAR,
            bordercolor=COLOR_BORDER,
            lightcolor=COLOR_BORDER,
            darkcolor=COLOR_BORDER,
            arrowcolor=COLOR_TEXT_MUTED
        )
        self.style.map("TScrollbar", background=[('active', COLOR_BUTTON_HOVER)])

    def build_ui(self):
        """Create the layout of the GUI."""
        # Top Header Bar
        self.top_bar = tk.Frame(self.root, bg=COLOR_SIDEBAR, height=60, bd=0, highlightthickness=0)
        self.top_bar.pack(fill=tk.X, side=tk.TOP)
        self.top_bar.pack_propagate(False)
        
        # App Title
        title_lbl = tk.Label(
            self.top_bar, 
            text="ROUGHNESS PROFILE ANALYSER", 
            fg=COLOR_ACCENT, 
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 16, "bold"),
            padx=20
        )
        title_lbl.pack(side=tk.LEFT)
        
        # Current Folder Display
        self.folder_lbl = tk.Label(
            self.top_bar,
            text="",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "italic"),
            padx=20
        )
        self.folder_lbl.pack(side=tk.RIGHT)
        
        # Main Split Container (Sidebar and Content Area)
        self.main_container = tk.Frame(self.root, bg=COLOR_BG)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left Sidebar (width 360px)
        self.sidebar = tk.Frame(self.main_container, bg=COLOR_SIDEBAR, width=360, bd=0, highlightthickness=0)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # Add visual separator
        sep = tk.Frame(self.main_container, bg=COLOR_BORDER, width=2)
        sep.pack(side=tk.LEFT, fill=tk.Y)
        
        # Center/Right Content Panel
        self.content_area = tk.Frame(self.main_container, bg=COLOR_BG)
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.build_sidebar()
        self.build_content_area()
        
        # Bottom Status Bar
        self.status_bar = tk.Frame(self.root, bg=COLOR_SIDEBAR, height=30, bd=0, highlightthickness=0)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_lbl = tk.Label(
            self.status_bar, 
            text="Ready", 
            fg=COLOR_TEXT_MUTED, 
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 9),
            padx=15
        )
        self.status_lbl.pack(side=tk.LEFT)

    def build_sidebar(self):
        """Build the control panel on the left sidebar."""
        # Scrollable wrapper frame to prevent elements clipping on smaller screens
        sidebar_canvas = tk.Canvas(self.sidebar, bg=COLOR_SIDEBAR, bd=0, highlightthickness=0)
        sidebar_scrollbar = ttk.Scrollbar(self.sidebar, orient="vertical", command=sidebar_canvas.yview, style="TScrollbar")
        sidebar_scroll_frame = tk.Frame(sidebar_canvas, bg=COLOR_SIDEBAR, padx=15, pady=15)
        
        sidebar_scroll_frame.bind(
            "<Configure>",
            lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))
        )
        canvas_win = sidebar_canvas.create_window((0, 0), window=sidebar_scroll_frame, anchor="nw")
        sidebar_canvas.bind('<Configure>', lambda event: sidebar_canvas.itemconfig(canvas_win, width=event.width))
        
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Enable mouse wheel scrolling for the sidebar canvas, excluding the listbox
        def _on_mousewheel(event):
            try:
                widget = event.widget
                is_sidebar = False
                current = widget
                while current:
                    if current == sidebar_canvas:
                        is_sidebar = True
                        break
                    if isinstance(current, tk.Listbox):
                        return # Let listbox handle its own scroll
                    parent_name = current.winfo_parent()
                    current = current.nametowidget(parent_name) if parent_name else None
                
                if is_sidebar:
                    sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
                
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        # Kept so other windows (e.g. batch analysis) can restore it after
        # temporarily claiming the global mouse-wheel binding.
        self._sidebar_wheel_handler = _on_mousewheel
        
        # Folder Selector Button
        self.dir_btn = tk.Button(
            sidebar_scroll_frame,
            text="📁 Select Roughness Folder",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self.browse_folder
        )
        self.dir_btn.pack(fill=tk.X, pady=(0, 8))
        
        # Clear / Reset Dataset Button
        self.clear_btn = tk.Button(
            sidebar_scroll_frame,
            text="🧹 Clear / New Dataset",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_HIGHLIGHT,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self.clear_all_data
        )
        self.clear_btn.pack(fill=tk.X, pady=(0, 15))
        
        # Sample listbox header
        lbl = tk.Label(
            sidebar_scroll_frame,
            text="SAMPLES FOUND:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        lbl.pack(fill=tk.X, pady=(0, 5))
        
        # Sample selection Listbox
        list_frame = tk.Frame(sidebar_scroll_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        list_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.sample_listbox = tk.Listbox(
            list_frame,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_SIDEBAR,
            activestyle="none",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 11, "bold"),
            height=6
        )
        self.sample_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.sample_listbox.yview, style="TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sample_listbox.config(yscrollcommand=scrollbar.set)
        
        # Bind double click / single click to select sample
        self.sample_listbox.bind("<<ListboxSelect>>", self.on_sample_selected)
        
        # Automatic wear track detection section
        detect_lbl = tk.Label(
            sidebar_scroll_frame,
            text="WEAR TRACK DETECTION:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        detect_lbl.pack(fill=tk.X, pady=(0, 5))

        detect_card = tk.Frame(sidebar_scroll_frame, bg=COLOR_CARD, bd=1,
                               highlightbackground=COLOR_BORDER, highlightthickness=1,
                               padx=10, pady=8)
        detect_card.pack(fill=tk.X, pady=(0, 15))

        # Which trace is plotted and measured. 'filtered' reproduces the
        # original behaviour exactly, so existing results are unaffected.
        src_row = tk.Frame(detect_card, bg=COLOR_CARD)
        src_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(src_row, text="Profil:", fg=COLOR_TEXT, bg=COLOR_CARD,
                 font=("Segoe UI", 9), anchor=tk.W).pack(side=tk.LEFT)
        for label, value in (("E&F (filtre)", 'filtered'), ("C&D (ham)", 'raw')):
            tk.Radiobutton(
                src_row, text=label, value=value, variable=self.profile_source,
                bg=COLOR_CARD, fg=COLOR_TEXT, selectcolor=COLOR_BG,
                activebackground=COLOR_CARD, activeforeground=COLOR_ACCENT,
                font=("Segoe UI", 9), bd=0, highlightthickness=0, cursor="hand2",
                command=self.on_profile_source_changed
            ).pack(side=tk.LEFT, padx=(6, 0))

        self.auto_detect_var = tk.BooleanVar(value=self.auto_detect_enabled)
        auto_chk = tk.Checkbutton(
            detect_card,
            text="Auto-mark when a sample is selected",
            variable=self.auto_detect_var,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            selectcolor=COLOR_BG,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_ACCENT,
            font=("Segoe UI", 9),
            anchor=tk.W,
            bd=0,
            highlightthickness=0,
            cursor="hand2"
        )
        auto_chk.pack(fill=tk.X)

        self.detect_btn = tk.Button(
            detect_card,
            text="🎯 Detect Wear Track (This Sample)",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            pady=6,
            cursor="hand2",
            command=lambda: self.auto_detect_current_sample(announce=True)
        )
        self.detect_btn.pack(fill=tk.X, pady=(8, 4))

        self.scan_btn = tk.Button(
            detect_card,
            text="🔍 Scan All Samples & Report",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.scan_all_samples
        )
        self.scan_btn.pack(fill=tk.X, pady=(0, 4))

        self.batch_btn = tk.Button(
            detect_card,
            text="📑 Batch Analysis (All Samples)",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_ACCENT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_SUCCESS,
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.open_batch_window
        )
        self.batch_btn.pack(fill=tk.X, pady=(0, 0))

        # Selection Results header
        results_lbl = tk.Label(
            sidebar_scroll_frame,
            text="CALCULATED AREAS:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        results_lbl.pack(fill=tk.X, pady=(0, 5))
        
        # Results container (displays coordinate selection & calculated area for each of the 4 plots)
        self.results_frame = tk.Frame(sidebar_scroll_frame, bg=COLOR_SIDEBAR)
        self.results_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.plot_info_widgets = []
        for i in range(4):
            card = tk.Frame(self.results_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=10, pady=8)
            card.pack(fill=tk.X, pady=(0, 8))
            
            # Title
            title = tk.Label(card, text=f"Measurement {i+1}", fg=COLOR_ACCENT, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"), anchor=tk.W)
            title.pack(fill=tk.X)
            
            # Coord labels
            p1_lbl = tk.Label(card, text="P1: --", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9), anchor=tk.W)
            p1_lbl.pack(fill=tk.X)
            p2_lbl = tk.Label(card, text="P2: --", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9), anchor=tk.W)
            p2_lbl.pack(fill=tk.X)
            
            # Area label
            area_lbl = tk.Label(card, text="Area: --", fg=COLOR_HIGHLIGHT, bg=COLOR_CARD, font=("Segoe UI", 10, "bold"), anchor=tk.W)
            area_lbl.pack(fill=tk.X)

            # Auto-detection status
            det_lbl = tk.Label(card, text="", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD,
                               font=("Segoe UI", 8), anchor=tk.W,
                               justify=tk.LEFT, wraplength=290)
            det_lbl.pack(fill=tk.X)

            self.plot_info_widgets.append({
                'card': card,
                'title': title,
                'p1': p1_lbl,
                'p2': p2_lbl,
                'area': area_lbl,
                'detect': det_lbl
            })
            
        # Wear Rate Parameters section
        wear_lbl = tk.Label(
            sidebar_scroll_frame,
            text="WEAR RATE PARAMETERS:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        wear_lbl.pack(fill=tk.X, pady=(5, 5))
        
        wear_card = tk.Frame(sidebar_scroll_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=10, pady=8)
        wear_card.pack(fill=tk.X, pady=(0, 15))
        
        # Radius entry (default 2.5 mm)
        r_frame = tk.Frame(wear_card, bg=COLOR_CARD)
        r_frame.pack(fill=tk.X, pady=3)
        r_lbl = tk.Label(r_frame, text="Radius (mm):", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 9), width=12, anchor=tk.W)
        r_lbl.pack(side=tk.LEFT)
        self.radius_ent = tk.Entry(r_frame, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=1, highlightthickness=0, font=("Segoe UI", 9, "bold"), width=12)
        self.radius_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.radius_ent.insert(0, "2.5")
        
        # Distance entry (default 100.0 m)
        d_frame = tk.Frame(wear_card, bg=COLOR_CARD)
        d_frame.pack(fill=tk.X, pady=3)
        d_lbl = tk.Label(d_frame, text="Distance (m):", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 9), width=12, anchor=tk.W)
        d_lbl.pack(side=tk.LEFT)
        self.dist_ent = tk.Entry(d_frame, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=1, highlightthickness=0, font=("Segoe UI", 9, "bold"), width=12)
        self.dist_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.dist_ent.insert(0, "100.0")
        
        # Load entry (default 10.0 N)
        l_frame = tk.Frame(wear_card, bg=COLOR_CARD)
        l_frame.pack(fill=tk.X, pady=3)
        l_lbl = tk.Label(l_frame, text="Load (N):", fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 9), width=12, anchor=tk.W)
        l_lbl.pack(side=tk.LEFT)
        self.load_ent = tk.Entry(l_frame, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT, bd=1, highlightthickness=0, font=("Segoe UI", 9, "bold"), width=12)
        self.load_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.load_ent.insert(0, "10.0")
        
        # Calculate Wear Button
        self.calc_wear_btn = tk.Button(
            wear_card,
            text="🧮 Calculate Specific Wear Rate",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.calculate_wear_rate
        )
        self.calc_wear_btn.pack(fill=tk.X, pady=(8, 4))

        # Show Specific Wear Rate Bar Plot Button
        self.show_chart_btn = tk.Button(
            wear_card,
            text="📊 Specific Wear Rate Graph",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.show_wear_rate_chart
        )
        self.show_chart_btn.pack(fill=tk.X, pady=(4, 0))

        # Results display inside wear_card
        res_sep = tk.Frame(wear_card, bg=COLOR_BORDER, height=1)
        res_sep.pack(fill=tk.X, pady=(10, 8))

        self.wear_vol_lbl = tk.Label(wear_card, text="Wear Volume: --", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 9), anchor=tk.W)
        self.wear_vol_lbl.pack(fill=tk.X)
        self.wear_rate_lbl = tk.Label(wear_card, text="Specific Wear Rate: --", fg=COLOR_HIGHLIGHT, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"), anchor=tk.W)
        self.wear_rate_lbl.pack(fill=tk.X)
            
        # Helper instructions text
        instruct_card = tk.Frame(sidebar_scroll_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=12, pady=12)
        instruct_card.pack(fill=tk.X, pady=(0, 15))
        
        instr_lbl = tk.Label(
            instruct_card,
            text="💡 Instructions:\n"
                 "1. Select a sample name above.\n"
                 "2. The wear track is marked automatically\n"
                 "    (green AUTO badge on the plot).\n"
                 "3. Amber MANUAL badge = not detected,\n"
                 "    select those two points by hand.\n"
                 "4. Click once on a plot to clear the auto\n"
                 "    selection, then click P1 and P2.\n"
                 "5. A third click resets the selection.",
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            font=("Segoe UI", 9, "italic"),
            justify=tk.LEFT,
            anchor=tk.W
        )
        instr_lbl.pack(fill=tk.X)
        
        # Reset selections button
        self.reset_btn = tk.Button(
            sidebar_scroll_frame,
            text="🔄 Reset Selections",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_HIGHLIGHT,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self.reset_all_selections
        )
        self.reset_btn.pack(fill=tk.X)

    def build_content_area(self):
        """Build the main content window containing the 2x2 grid of subplots."""
        self.graph_panel = tk.Frame(self.content_area, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        self.graph_panel.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Default placeholder inside graph panel
        self.placeholder_lbl = tk.Label(
            self.graph_panel,
            text="📉\nNo sample loaded.\n\nChoose a sample from the list on the left to display its profiles.",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 14, "italic"),
            justify=tk.CENTER
        )
        self.placeholder_lbl.pack(fill=tk.BOTH, expand=True)

    def load_directory(self, path):
        """Scans the directory for .xls files, groups them, and updates listbox."""
        self.current_dir = path
        self.folder_lbl.config(text=f"Folder: {self.current_dir}")
        self.update_status(f"Scanning folder: {self.current_dir}")
        self.loaded_data.clear()  # Clear memory cache when changing or reloading a directory
        self.raw_data.clear()
        
        try:
            if not os.path.exists(path):
                # If folder does not exist, do not raise error immediately, let user browse
                self.sample_listbox.delete(0, tk.END)
                self.samples = {}
                self.update_status("Roughness folder not found. Please select a folder.")
                return
                
            all_files = os.listdir(path)
            xls_files = sorted([f for f in all_files if f.lower().endswith('.xls') and os.path.isfile(os.path.join(path, f))])
            
            # Group by prefix before '-'
            self.samples = {}
            for f in xls_files:
                if '-' in f:
                    sample_name = f.split('-')[0].strip()
                    if sample_name not in self.samples:
                        self.samples[sample_name] = []
                    self.samples[sample_name].append(f)
            
            # Sort files inside each sample group
            for sname in self.samples:
                self.samples[sname] = sorted(self.samples[sname])
                
            # Populate listbox
            self.sample_listbox.delete(0, tk.END)
            for sname in sorted(self.samples.keys()):
                self.sample_listbox.insert(tk.END, sname)
                
            self.update_status(f"Found {len(self.samples)} unique sample groups in directory.")
            
            # Clear canvas and reset results on folder change
            self.reset_gui_plots()
            
            # Load existing wear rates from CSV
            self.load_wear_rates_from_csv()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not read directory:\n{str(e)}")
            self.update_status("Error loading directory.")

    def clear_all_data(self):
        """Clears cached loaded data, resets sample list, and resets plots to allow choosing a new dataset cleanly."""
        self.loaded_data.clear()
        self.raw_data.clear()
        self.samples.clear()
        if hasattr(self, 'sample_listbox'):
            self.sample_listbox.delete(0, tk.END)
        self.reset_gui_plots()
        self.update_status("Old data and cache cleared. You can select a new dataset.", is_success=True)
        messagebox.showinfo("Data Cleared", "Old dataset and cache cleared. You can select a new folder or sample.")

    def reset_gui_plots(self):
        """Hides plots and restores placeholders."""
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
            
        self.placeholder_lbl.pack(fill=tk.BOTH, expand=True)
        self.selected_sample = None
        self.current_measurements = []
        self.reset_all_selections(update_plot=False)
        
        # Reset wear rate labels
        if hasattr(self, 'wear_vol_lbl'):
            self.wear_vol_lbl.config(text="Wear Volume: --")
            self.wear_rate_lbl.config(text="Specific Wear Rate: --")

    def browse_folder(self):
        """Prompts the user to select a folder."""
        selected = filedialog.askdirectory(initialdir=self.current_dir, title="Select Roughness Data Folder")
        if selected:
            self.load_directory(selected)

    def on_sample_selected(self, event):
        """Triggered when a sample name is selected in the listbox."""
        selection = self.sample_listbox.curselection()
        if not selection:
            return
            
        sample_name = self.sample_listbox.get(selection[0])
        self.selected_sample = sample_name
        self.current_measurements = self.samples[sample_name][:4] # limit to 4 files
        
        self.update_status(f"Loading data for {sample_name}...")
        self.root.config(cursor="watch")
        self.root.update()
        
        # Load and parse excel files for this sample
        load_success = True
        for filename in self.current_measurements:
            file_path = os.path.join(self.current_dir, filename)
            try:
                self.parse_excel_file(file_path)
            except Exception as e:
                load_success = False
                self.root.config(cursor="")
                messagebox.showerror("Parse Error", f"Could not load data from {filename}:\n{str(e)}")
                break
                
        self.root.config(cursor="")
        
        if load_success:
            # Clear selections
            self.reset_all_selections(update_plot=False)
            
            # Draw grid plots
            self.placeholder_lbl.pack_forget()
            self.draw_grid_plots()
            self.update_status(f"Loaded sample: {sample_name} ({len(self.current_measurements)} measurements).", is_success=True)

            # Pre-select the wear track so the plots come up already marked.
            # Silent here: the per-plot badges and the sidebar cards already say
            # which measurements need a manual selection.
            if self.auto_detect_var.get():
                self.auto_detect_current_sample(announce=False)

            # Load existing wear rate calculations for this sample if they exist
            if self.selected_sample in self.wear_rates:
                sdata = self.wear_rates[self.selected_sample]
                self.radius_ent.delete(0, tk.END)
                self.radius_ent.insert(0, str(sdata['radius']))
                self.dist_ent.delete(0, tk.END)
                self.dist_ent.insert(0, str(sdata['distance']))
                self.load_ent.delete(0, tk.END)
                self.load_ent.insert(0, str(sdata['load']))
                
                self.wear_vol_lbl.config(text=f"Wear Volume: {sdata['volume']:.4e} mm³")
                self.wear_rate_lbl.config(text=f"Wear Rate: {sdata['wear_rate']:.4e} mm³/(N·m)")
            else:
                self.wear_vol_lbl.config(text="Wear Volume: --")
                self.wear_rate_lbl.config(text="Specific Wear Rate: --")

    def parse_excel_file(self, file_path):
        """
        Loads columns E (4) and F (5) from the 'DATA' sheet in the Excel file.
        Non-numeric header rows are safely coerced to NaN and dropped.
        If E & F produce no numeric data (e.g. older files with 2 columns),
        it falls back to columns A and B (indices 0 and 1).
        Caches it in self.loaded_data.

        Columns C (2) and D (3) hold the same trace before Gaussian filtering.
        The wear track survives intact there, so it is cached separately in
        self.raw_data and used for automatic detection.
        """
        filename = os.path.basename(file_path)
        if filename in self.loaded_data:
            return self.loaded_data[filename]
            
        # Case-insensitive sheet name search for 'DATA'
        excel_file = pd.ExcelFile(file_path, engine='xlrd')
        try:
            data_sheet = next(
                (s for s in excel_file.sheet_names if s.strip().casefold() == 'data'),
                excel_file.sheet_names[0]
            )
            df = pd.read_excel(excel_file, sheet_name=data_sheet, header=None)
        finally:
            excel_file.close()
        
        # Check available columns: preferred E (idx 4) & F (idx 5), fallback A (idx 0) & B (idx 1)
        col_x, col_y = 4, 5
        if df.shape[1] < 6:
            col_x, col_y = 0, 1

        sub = df[[col_x, col_y]].copy()
        sub[col_x] = pd.to_numeric(sub[col_x], errors='coerce')
        sub[col_y] = pd.to_numeric(sub[col_y], errors='coerce')
        data = sub.dropna()

        # If columns E&F yielded no numeric data, try columns A&B
        if len(data) == 0 and (col_x != 0 or col_y != 1) and df.shape[1] >= 2:
            sub_fb = df[[0, 1]].copy()
            sub_fb[0] = pd.to_numeric(sub_fb[0], errors='coerce')
            sub_fb[1] = pd.to_numeric(sub_fb[1], errors='coerce')
            data = sub_fb.dropna()
            col_x, col_y = 0, 1
        
        x = data[col_x].to_numpy(dtype=float)
        y = data[col_y].to_numpy(dtype=float)
        
        if len(x) == 0:
            raise ValueError("No numeric data rows found in sheet 'DATA'.")
            
        # Ensure it is sorted by x coordinates
        sort_idx = np.argsort(x, kind='stable')
        x = x[sort_idx]
        y = y[sort_idx]

        self.loaded_data[filename] = (x, y)

        # Cache the unfiltered trace (cols C & D) for wear-track detection
        self.raw_data.pop(filename, None)
        if col_x == 4 and df.shape[1] >= 4:
            raw = df[[2, 3]].copy()
            raw[2] = pd.to_numeric(raw[2], errors='coerce')
            raw[3] = pd.to_numeric(raw[3], errors='coerce')
            raw = raw.dropna()
            if len(raw) == len(x):
                rx = raw[2].to_numpy(dtype=float)
                ry = raw[3].to_numpy(dtype=float)
                rsort = np.argsort(rx, kind='stable')
                self.raw_data[filename] = (rx[rsort], ry[rsort])

        return x, y

    def detection_profile(self, filename):
        """
        Returns the (x, y) pair detection should run on.

        The unfiltered trace (cols C & D) is preferred: the Gaussian roughness
        filter flattens the wear track, so detecting on the filtered data is far
        less reliable. Indices are shared between the two traces, so a track
        found on the raw profile maps directly onto the displayed one.
        """
        if filename in self.raw_data:
            return self.raw_data[filename]
        return self.loaded_data.get(filename)

    def display_profile(self, filename):
        """
        Returns the (x, y) pair that is plotted and measured.

        'filtered' (cols E & F) is the default and keeps every previously
        calculated area unchanged. 'raw' (cols C & D) plots the unfiltered
        trace, where the wear groove keeps its true depth -- the Gaussian
        roughness filter removes most of it, so areas measured on the filtered
        trace under-state the worn cross-section.
        """
        if self.profile_source.get() == 'raw' and filename in self.raw_data:
            return self.raw_data[filename]
        return self.loaded_data[filename]

    def on_profile_source_changed(self):
        """Re-plots (and re-detects) after the user switches the profile source."""
        if not self.current_measurements:
            return
        src = "raw (C&D, unfiltered)" if self.profile_source.get() == 'raw' \
            else "filtered (E&F)"
        self.reset_all_selections(update_plot=False)
        self.draw_grid_plots()
        if self.auto_detect_var.get():
            self.auto_detect_current_sample(announce=False)
        else:
            self.canvas.draw()
        self.update_status(f"Profile source switched to {src}. Areas recalculated.",
                           is_success=True)

    def compute_area_between(self, x, y, idx1, idx2):
        """Area between the profile and the straight chord joining two points."""
        idx_min, idx_max = min(idx1, idx2), max(idx1, idx2)
        x_slice = x[idx_min: idx_max + 1]
        y_slice = y[idx_min: idx_max + 1]

        if x[idx2] != x[idx1]:
            y_line = y[idx1] + (y[idx2] - y[idx1]) / (x[idx2] - x[idx1]) * (x_slice - x[idx1])
        else:
            y_line = np.full_like(x_slice, y[idx1])

        return _trapz(np.abs(y_slice - y_line), x_slice)

    def apply_detection(self, ax_idx, result):
        """Turns a detection result into the same selection a manual click makes."""
        filename = self.current_measurements[ax_idx]
        x, y = self.display_profile(filename)
        i1, i2 = result['i1'], result['i2']

        # Detection may have run on the raw trace; clamp to the displayed one.
        i1 = int(min(max(i1, 0), len(x) - 1))
        i2 = int(min(max(i2, 0), len(x) - 1))

        self.clicks[ax_idx] = [i1, i2]
        self.clicked_coords[ax_idx] = [(x[i1], y[i1]), (x[i2], y[i2])]
        self.computed_areas[ax_idx] = self.compute_area_between(x, y, i1, i2)

    def auto_detect_current_sample(self, announce=True):
        """
        Runs wear-track detection on every measurement of the loaded sample and
        pre-selects the track. Measurements that cannot be resolved are left
        blank for the user to pick by hand.
        """
        if not self.current_measurements:
            if announce:
                messagebox.showwarning("No Sample Loaded", "Please select a sample first.")
            return []

        undetected = []
        for i, filename in enumerate(self.current_measurements):
            x_det, y_det = self.detection_profile(filename)
            result = detect_wear_scar(x_det, y_det)
            self.detections[i] = result

            if result['status'] == 'ok':
                self.apply_detection(i, result)
            else:
                self.clicks[i] = []
                self.computed_areas[i] = None
                self.clicked_coords[i] = [None, None]
                undetected.append((os.path.splitext(filename)[0], result['reason']))

        if self.canvas:
            for i in range(len(self.current_measurements)):
                self.draw_subplot(i)
            self.canvas.draw()
        self.update_results_display()

        found = len(self.current_measurements) - len(undetected)
        if announce:
            if undetected:
                lines = "\n".join(f"  • {code}  —  {reason}" for code, reason in undetected)
                messagebox.showwarning(
                    "Partial Auto-Detection",
                    f"{self.selected_sample}: wear track automatically found in "
                    f"{found}/{len(self.current_measurements)} measurements.\n\n"
                    f"The wear track could not be distinguished in the measurements "
                    f"below — these must be selected MANUALLY:\n\n{lines}"
                )
            else:
                messagebox.showinfo(
                    "Auto-Detection Complete",
                    f"{self.selected_sample}: wear track automatically found and "
                    f"selected in all {found}/{len(self.current_measurements)} measurements."
                )

        self.update_status(
            f"Auto-detect: {found}/{len(self.current_measurements)} tracks found for {self.selected_sample}.",
            is_success=not undetected
        )
        return undetected

    def scan_all_samples(self):
        """
        Runs detection across every sample in the folder and reports which
        measurements need manual selection, listed by sample code.
        """
        if not self.samples:
            messagebox.showwarning("No Samples", "No sample files loaded. Select a folder first.")
            return

        report = []          # (code, status, reason)
        self.root.config(cursor="watch")
        try:
            for sname in sorted(self.samples.keys()):
                for filename in self.samples[sname][:4]:
                    code = os.path.splitext(filename)[0]
                    self.update_status(f"Scanning {code}...")
                    try:
                        self.parse_excel_file(os.path.join(self.current_dir, filename))
                        x_det, y_det = self.detection_profile(filename)
                        result = detect_wear_scar(x_det, y_det)
                        report.append((code, result['status'], result['reason'], result))
                    except Exception as e:
                        report.append((code, 'error', str(e), None))
        finally:
            self.root.config(cursor="")

        self.show_scan_report(report)

    def show_scan_report(self, report):
        """Displays the batch detection results in a scrollable window."""
        auto_ok = [r for r in report if r[1] == 'ok']
        manual = [r for r in report if r[1] != 'ok']

        win = tk.Toplevel(self.root)
        win.title("Wear Track Auto-Detection Report")
        win.geometry("820x620")
        win.configure(bg=COLOR_BG)
        win.grab_set()

        tk.Label(
            win,
            text="WEAR TRACK AUTO-DETECTION REPORT",
            font=("Segoe UI", 14, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG, pady=12
        ).pack(fill=tk.X)

        tk.Label(
            win,
            text=f"Wear track automatically found in {len(auto_ok)} / {len(report)} measurements."
                 + (f"    •    {len(manual)} measurement(s) need manual selection." if manual else ""),
            font=("Segoe UI", 10), fg=COLOR_WARN if manual else COLOR_SUCCESS,
            bg=COLOR_BG, pady=4
        ).pack(fill=tk.X)

        text_frame = tk.Frame(win, bg=COLOR_CARD, bd=1,
                              highlightbackground=COLOR_BORDER, highlightthickness=1)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        txt = tk.Text(text_frame, bg=COLOR_CARD, fg=COLOR_TEXT, bd=0,
                      highlightthickness=0, font=("Consolas", 10), wrap=tk.WORD, padx=12, pady=12)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview, style="TScrollbar")
        txt.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        txt.tag_config('head', foreground=COLOR_ACCENT, font=("Consolas", 11, "bold"))
        txt.tag_config('ok', foreground=COLOR_SUCCESS)
        txt.tag_config('warn', foreground=COLOR_WARN)

        if manual:
            txt.insert(tk.END, "MEASUREMENTS REQUIRING MANUAL SELECTION\n", 'head')
            txt.insert(tk.END, "(wear track could not be distinguished from normal surface roughness)\n\n")
            for code, status, reason, _ in manual:
                txt.insert(tk.END, f"  {code:<12} {reason}\n", 'warn')
            txt.insert(tk.END, "\n" + "-" * 78 + "\n\n")

        txt.insert(tk.END, "AUTO-DETECTED MEASUREMENTS\n", 'head')
        txt.insert(tk.END, f"\n  {'Sample':<12}{'Position (X)':<22}{'Depth':>10}{'Width':>10}{'Confidence':>11}\n\n")
        for code, status, reason, res in auto_ok:
            fname = self._file_for_code(code)
            profile = self.detection_profile(fname) if fname else None
            span = (f"{profile[0][res['i1']]:.3f} - {profile[0][res['i2']]:.3f}"
                    if profile is not None else "-")
            txt.insert(
                tk.END,
                f"  {code:<12}{span:<22}{res['depth']:>10.2f}{res['width']:>10.3f}"
                f"{res['confidence'] * 100:>7.0f}%\n",
                'ok'
            )

        txt.config(state=tk.DISABLED)

        btns = tk.Frame(win, bg=COLOR_BG)
        btns.pack(fill=tk.X, pady=(0, 15))

        def save_report():
            path = os.path.join(self.current_dir, "wear_track_detection_report.txt")
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(f"Wear track auto-detection report — {self.current_dir}\n")
                    fh.write(f"{len(auto_ok)}/{len(report)} detected automatically\n\n")
                    if manual:
                        fh.write("MANUAL SELECTION REQUIRED:\n")
                        for code, status, reason, _ in manual:
                            fh.write(f"  {code:<12} {reason}\n")
                        fh.write("\n")
                    fh.write("AUTO-DETECTED:\n")
                    for code, status, reason, res in auto_ok:
                        fh.write(f"  {code:<12} depth={res['depth']:.2f} "
                                 f"width={res['width']:.3f} confidence={res['confidence']*100:.0f}%\n")
                messagebox.showinfo("Report Saved", f"Report saved as:\n{path}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not write report:\n{e}")

        tk.Button(btns, text="💾 Save Report", font=("Segoe UI", 10, "bold"),
                  bg=COLOR_BUTTON, fg=COLOR_TEXT, activebackground=COLOR_BUTTON_HOVER,
                  activeforeground=COLOR_ACCENT, bd=0, padx=15, pady=8,
                  cursor="hand2", command=save_report).pack(side=tk.LEFT, padx=20)

        tk.Button(btns, text="❌ Close", font=("Segoe UI", 10, "bold"),
                  bg=COLOR_BUTTON, fg=COLOR_TEXT, activebackground=COLOR_BUTTON_HOVER,
                  activeforeground=COLOR_HIGHLIGHT, bd=0, padx=15, pady=8,
                  cursor="hand2", command=win.destroy).pack(side=tk.RIGHT, padx=20)

        self.update_status(
            f"Scanned {len(report)} measurements: {len(auto_ok)} auto-detected, "
            f"{len(manual)} need manual selection.",
            is_success=not manual
        )

    def _file_for_code(self, code):
        """Maps a measurement code (filename without extension) back to its file."""
        for files in self.samples.values():
            for f in files:
                if os.path.splitext(f)[0] == code:
                    return f
        return None

    # ------------------------------------------------------------------
    # Batch analysis window (all samples, tabbed)
    # ------------------------------------------------------------------

    def open_batch_window(self):
        """
        Analyses every measurement in the folder and opens the tabbed batch
        window: measurement checklist, averaged wear-track profiles
        (surface = 0) and the specific wear rate comparison.

        Averaging always runs on the raw C&D trace: the Gaussian roughness
        filter flattens the track, so only the unfiltered profile keeps the
        true worn cross-section.
        """
        if not self.samples:
            messagebox.showwarning("No Samples", "No sample files loaded. Select a folder first.")
            return

        entries = []
        self.root.config(cursor="watch")
        try:
            for sname in sorted(self.samples.keys()):
                for filename in self.samples[sname][:4]:
                    code = os.path.splitext(filename)[0]
                    self.update_status(f"Analysing {code}...")
                    entry = {'sample': sname, 'code': code, 'file': filename,
                             'det': None, 'error': None}
                    try:
                        self.parse_excel_file(os.path.join(self.current_dir, filename))
                    except Exception as e:
                        entry['error'] = str(e)
                        entries.append(entry)
                        continue

                    x, y = self.detection_profile(filename)
                    det = detect_wear_scar(x, y)
                    entry.update({'x': x, 'y': y, 'det': det})

                    if det['status'] == 'ok':
                        i1, i2 = det['i1'], det['i2']
                        entry['area'] = self.compute_area_between(x, y, i1, i2)
                        # Surface-zero profile for averaging: subtract the
                        # un-worn surface trend so intact surface sits at 0.
                        smooth = _moving_average(y, max(5, int(round(0.01 * len(y)))))
                        base, _ = _robust_baseline(x, smooth)
                        entry['ynorm'] = y - base
                        entry['center'] = 0.5 * (x[i1] + x[i2])
                        entry['half'] = 0.5 * (x[i2] - x[i1])
                    entries.append(entry)
        finally:
            self.root.config(cursor="")

        self.update_status(f"Batch analysis: {len(entries)} measurements scanned.", is_success=True)
        self._build_batch_window(entries)

    def _batch_params(self):
        """Reads wear-rate parameters from the sidebar, falling back to defaults."""
        try:
            radius = float(self.radius_ent.get())
            distance = float(self.dist_ent.get())
            load = float(self.load_ent.get())
            if radius <= 0 or distance <= 0 or load <= 0:
                raise ValueError
        except ValueError:
            radius, distance, load = 2.5, 100.0, 10.0
        return radius, distance, load

    def _build_batch_window(self, entries):
        """Creates the tabbed Toplevel for the batch analysis results."""
        win = tk.Toplevel(self.root)
        win.title("Batch Analysis — All Samples")
        win.geometry("1150x780")
        win.configure(bg=COLOR_BG)

        style = ttk.Style()
        style.configure("Batch.TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("Batch.TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 6))

        notebook = ttk.Notebook(win, style="Batch.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Tab 1: measurement checklist -----------------------------
        sel_tab = tk.Frame(notebook, bg=COLOR_BG)
        notebook.add(sel_tab, text="  ☑ Measurement Selection  ")

        tk.Label(
            sel_tab,
            text="Uncheck any measurements you don't want — the graphs update instantly.\n"
                 "⚠-marked measurements had a wear track that could not be auto-detected; they cannot be included in the average.",
            fg=COLOR_TEXT_MUTED, bg=COLOR_BG, font=("Segoe UI", 10),
            justify=tk.LEFT, padx=12, pady=8, anchor=tk.W
        ).pack(fill=tk.X)

        list_canvas = tk.Canvas(sel_tab, bg=COLOR_BG, bd=0, highlightthickness=0)
        list_scroll = ttk.Scrollbar(sel_tab, orient="vertical",
                                    command=list_canvas.yview, style="TScrollbar")
        list_inner = tk.Frame(list_canvas, bg=COLOR_BG)
        list_inner.bind("<Configure>",
                        lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
        list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=(0, 12))
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 12))

        # Route the mouse wheel to this list while the pointer is over the
        # batch window, then hand the global binding back to the sidebar.
        def _batch_wheel(event):
            list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _claim_wheel(_e):
            self.root.bind_all("<MouseWheel>", _batch_wheel)

        def _release_wheel(_e=None):
            self.root.bind_all("<MouseWheel>", self._sidebar_wheel_handler)

        sel_tab.bind("<Enter>", _claim_wheel)
        sel_tab.bind("<Leave>", _release_wheel)

        # --- Tab 2: averaged wear-track profiles ----------------------
        avg_tab = tk.Frame(notebook, bg=COLOR_BG)
        notebook.add(avg_tab, text="  📉 Averaged Tracks  ")

        fig_avg, ax_avg = plt.subplots(figsize=(10, 6))
        fig_avg.patch.set_facecolor('#ffffff')
        avg_canvas = FigureCanvasTkAgg(fig_avg, master=avg_tab)
        avg_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 0))

        # --- Tab 3: specific wear rate --------------------------------
        rate_tab = tk.Frame(notebook, bg=COLOR_BG)
        notebook.add(rate_tab, text="  📊 Specific Wear Rate  ")

        fig_rate, ax_rate = plt.subplots(figsize=(10, 6))
        fig_rate.patch.set_facecolor('#ffffff')
        rate_canvas = FigureCanvasTkAgg(fig_rate, master=rate_tab)
        rate_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 0))

        # --- Save buttons under the graph tabs ------------------------
        def make_save_button(parent, fig, default_name):
            def save():
                graphs_dir = os.path.join(self.current_dir, "..", "graphs")
                os.makedirs(graphs_dir, exist_ok=True)
                path = os.path.join(graphs_dir, default_name)
                fig.savefig(path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
                messagebox.showinfo("Graph Saved", f"Saved as:\n{os.path.abspath(path)}",
                                    parent=win)
            btn = tk.Button(parent, text="💾 Save Graph", font=("Segoe UI", 10, "bold"),
                            bg=COLOR_BUTTON, fg=COLOR_TEXT,
                            activebackground=COLOR_BUTTON_HOVER, activeforeground=COLOR_ACCENT,
                            bd=0, padx=15, pady=8, cursor="hand2", command=save)
            btn.pack(side=tk.BOTTOM, pady=10)
            return btn

        make_save_button(avg_tab, fig_avg, "averaged_wear_tracks.png")
        make_save_button(rate_tab, fig_rate, "specific_wear_rates.png")

        # --- Refresh logic --------------------------------------------
        palette = ['#0984e3', '#e84393', '#00b894', '#e17055',
                   '#6c5ce7', '#fdcb6e', '#00cec9', '#d63031']

        def selected_by_sample():
            groups = {}
            for e in entries:
                if e.get('det') and e['det']['status'] == 'ok' and e['var'].get():
                    groups.setdefault(e['sample'], []).append(e)
            return groups

        def refresh(_event=None):
            groups = selected_by_sample()
            radius, distance, load = self._batch_params()

            # Averaged, surface-zero, centre-aligned track profiles
            ax_avg.clear()
            ax_avg.set_facecolor('white')
            ax_avg.grid(True, color='#e2e8f0', linestyle='--', linewidth=0.5)
            ax_avg.axhline(0, color='black', linewidth=0.8, linestyle='-', alpha=0.6)
            for ci, (sname, sel) in enumerate(sorted(groups.items())):
                reach = 1.3 * max(e['half'] for e in sel)
                for e in sel:
                    reach = min(reach, e['center'] - e['x'][0], e['x'][-1] - e['center'])
                if reach <= 0:
                    continue
                grid = np.linspace(-reach, reach, 1200)
                curves = [np.interp(grid, e['x'] - e['center'], e['ynorm']) for e in sel]
                mean_curve = np.mean(curves, axis=0)
                ax_avg.plot(grid, mean_curve, linewidth=1.6,
                            color=palette[ci % len(palette)],
                            label=f"{sname} track  ({len(sel)} measurement{'s' if len(sel) != 1 else ''})")
            ax_avg.set_xlabel('Distance from track center [mm]', fontsize=10, fontweight='semibold')
            ax_avg.set_ylabel('Depth [µm]  (surface = 0)', fontsize=10, fontweight='semibold')
            ax_avg.set_title('Averaged Wear Track Profiles', fontsize=12, fontweight='bold', pad=10)
            if groups:
                ax_avg.legend(fontsize=9)
            for spine in ax_avg.spines.values():
                spine.set_color('black')
            fig_avg.tight_layout()
            avg_canvas.draw()

            # Specific wear rate bar chart
            ax_rate.clear()
            ax_rate.set_facecolor('white')
            ax_rate.grid(True, axis='y', color='#e2e8f0', linestyle='--', linewidth=0.5)
            names, rates = [], []
            for sname, sel in sorted(groups.items()):
                avg_area = float(np.mean([e['area'] for e in sel]))
                volume = (avg_area / 1000.0) * 2.0 * np.pi * radius
                rates.append(volume / (load * distance))
                names.append(sname)
            if names:
                bars = ax_rate.bar(names, rates, color='#e84393',
                                   edgecolor='#0c2461', linewidth=1.0, width=0.5)
                for bar in bars:
                    h = bar.get_height()
                    ax_rate.text(bar.get_x() + bar.get_width() / 2., h * 1.02,
                                 f"{h:.2e}", ha='center', va='bottom',
                                 fontsize=8, fontweight='bold')
                ax_rate.yaxis.get_major_formatter().set_powerlimits((0, 0))
            ax_rate.set_xlabel('Sample', fontsize=10, fontweight='bold', labelpad=10)
            ax_rate.set_ylabel('Specific Wear Rate [mm³/(N·m)]', fontsize=10, fontweight='bold', labelpad=10)
            ax_rate.set_title(f'Specific Wear Rate  (R={radius} mm, d={distance} m, F={load} N)',
                              fontsize=12, fontweight='bold', pad=10)
            for spine in ax_rate.spines.values():
                spine.set_color('black')
            fig_rate.tight_layout()
            rate_canvas.draw()

        # --- Checklist rows -------------------------------------------
        current_sample = None
        for e in entries:
            if e['sample'] != current_sample:
                current_sample = e['sample']
                tk.Label(list_inner, text=current_sample, fg=COLOR_ACCENT, bg=COLOR_BG,
                         font=("Segoe UI", 11, "bold"), anchor=tk.W
                         ).pack(fill=tk.X, padx=4, pady=(10, 2))

            row = tk.Frame(list_inner, bg=COLOR_CARD, bd=1,
                           highlightbackground=COLOR_BORDER, highlightthickness=1)
            row.pack(fill=tk.X, padx=4, pady=1)

            det = e.get('det')
            ok = det is not None and det['status'] == 'ok'
            e['var'] = tk.BooleanVar(value=ok)

            chk = tk.Checkbutton(
                row, text=e['code'], variable=e['var'],
                bg=COLOR_CARD, fg=COLOR_TEXT, selectcolor=COLOR_BG,
                activebackground=COLOR_CARD, activeforeground=COLOR_ACCENT,
                font=("Segoe UI", 10, "bold"), bd=0, highlightthickness=0,
                cursor="hand2", width=10, anchor=tk.W,
                command=refresh,
                state=tk.NORMAL if ok else tk.DISABLED
            )
            chk.pack(side=tk.LEFT, padx=(8, 4), pady=4)

            if e['error']:
                info, color = f"ERROR — {e['error']}", COLOR_HIGHLIGHT
            elif ok:
                info = (f"✓ track found   depth {det['depth']:.1f} µm   "
                        f"width {det['width']:.3f} mm   area {e['area']:.2f}   "
                        f"confidence {det['confidence'] * 100:.0f}%")
                color = COLOR_SUCCESS
            else:
                info, color = f"⚠ could not distinguish — {det['reason']}", COLOR_WARN
            tk.Label(row, text=info, fg=color, bg=COLOR_CARD,
                     font=("Segoe UI", 9), anchor=tk.W).pack(side=tk.LEFT, fill=tk.X,
                                                             expand=True, padx=4)

        def on_close():
            _release_wheel()
            plt.close(fig_avg)
            plt.close(fig_rate)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        refresh()

    def draw_grid_plots(self):
        """Creates the 2x2 grid of Matplotlib subplots inside Tkinter."""
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
            
        # Create figure and flatten axes
        self.fig, self.axes = plt.subplots(2, 2, figsize=(10, 7))
        self.axes = self.axes.flatten()
        
        # Style details
        self.fig.patch.set_facecolor('#ffffff')
        
        # Render each measurement
        for i in range(4):
            ax = self.axes[i]
            if i < len(self.current_measurements):
                # Draw the plot
                self.draw_subplot(i)
                ax.set_visible(True)
            else:
                # If there are fewer than 4 files, hide the remaining subplots
                ax.set_visible(False)
                
        self.fig.tight_layout(pad=3.0)
        
        # Connect click event
        self.fig.canvas.mpl_connect('button_press_event', self.on_plot_click)
        
        # Embed canvas in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_panel)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def draw_subplot(self, ax_idx):
        """Clears and redraws the specified subplot, including curves and selections."""
        ax = self.axes[ax_idx]
        ax.clear()
        
        filename = self.current_measurements[ax_idx]
        x, y = self.display_profile(filename)

        # Clean scientific style
        ax.set_facecolor('white')
        ax.grid(True, color='#e2e8f0', linestyle='--', linewidth=0.5)
        
        # Plot raw profile data (Navy color)
        ax.plot(x, y, color='#0c2461', linewidth=1.0, zorder=2, label="Profile")
        
        # Title and Labels
        title_no_ext = os.path.splitext(filename)[0]
        src_tag = "raw C&D" if (self.profile_source.get() == 'raw'
                                and filename in self.raw_data) else "filtered E&F"
        ax.set_title(f"{title_no_ext}  [{src_tag}]", fontsize=11, fontweight='bold', pad=10)
        ax.set_xlabel('Distance [X]', fontsize=9, fontweight='semibold')
        ax.set_ylabel('Height [Y]', fontsize=9, fontweight='semibold')
        
        # Black solid axes borders
        for spine in ax.spines.values():
            spine.set_color('black')
            spine.set_linewidth(1.0)
            
        ax.tick_params(colors='black', labelsize=8, direction='out')
        
        # Draw click indicators (P1, P2, straight line, and shaded area)
        clicks = self.clicks[ax_idx]
        if len(clicks) >= 1:
            idx1 = clicks[0]
            # Marker 1 (Blue dot)
            ax.scatter(x[idx1], y[idx1], color=COLOR_P1, s=40, zorder=5, label="P1")
            
        if len(clicks) == 2:
            idx1, idx2 = clicks[0], clicks[1]
            idx_min, idx_max = min(idx1, idx2), max(idx1, idx2)
            
            # Marker 2 (Pink dot)
            ax.scatter(x[idx2], y[idx2], color=COLOR_HIGHLIGHT, s=40, zorder=5, label="P2")
            
            # Straight line between P1 and P2
            x_line = x[[idx1, idx2]]
            y_line = y[[idx1, idx2]]
            ax.plot(x_line, y_line, color=COLOR_HIGHLIGHT, linestyle='--', linewidth=1.5, zorder=4, label="Reference")
            
            # Slice coordinates
            x_slice = x[idx_min : idx_max + 1]
            y_slice = y[idx_min : idx_max + 1]
            
            # Interpolated straight line values for the slice
            if x[idx2] != x[idx1]:
                y_line_slice = y[idx1] + (y[idx2] - y[idx1]) / (x[idx2] - x[idx1]) * (x_slice - x[idx1])
            else:
                y_line_slice = np.full_like(x_slice, y[idx1])
                
            # Shade/highlight the area between the line and the profile curve
            ax.fill_between(x_slice, y_slice, y_line_slice, color=COLOR_HIGHLIGHT, alpha=0.25, zorder=3)
            
            # Display Area value box in the upper-right corner of the plot
            area = self.computed_areas[ax_idx]
            if area is not None:
                ax.text(
                    0.95, 0.95, 
                    f"Area: {area:.4e}", 
                    transform=ax.transAxes, 
                    ha='right', va='top', 
                    fontsize=9, fontweight='bold',
                    color='black',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffffff', alpha=0.85, edgecolor='black', linewidth=0.5)
                )
        
        # Auto-detection badge in the upper-left corner
        det = self.detections.get(ax_idx)
        if det is not None:
            if det['status'] == 'ok':
                badge_txt = f"AUTO ✓  {det['confidence']*100:.0f}%"
                badge_fg, badge_bg = '#1b5e20', '#c8e6c9'
            else:
                badge_txt = "MANUAL SELECTION"
                badge_fg, badge_bg = '#7f4f00', '#ffe0a3'
            ax.text(
                0.02, 0.05, badge_txt,
                transform=ax.transAxes, ha='left', va='bottom',
                fontsize=8, fontweight='bold', color=badge_fg,
                bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_bg,
                          alpha=0.95, edgecolor=badge_fg, linewidth=0.6)
            )

        # Recreate cursor for this axis to follow the mouse pointer (crosshair)
        # We disable useblit to prevent restoring clean canvas background over drawn elements
        self.cursors[ax_idx] = Cursor(ax, useblit=False, color=COLOR_HIGHLIGHT, linewidth=0.8, linestyle=':')

    def on_plot_click(self, event):
        """Callback for mouse clicks on the subplots."""
        if event.inaxes is None:
            return
            
        # Find which subplot was clicked
        clicked_ax_idx = -1
        for idx, ax in enumerate(self.axes[:len(self.current_measurements)]):
            if ax == event.inaxes:
                clicked_ax_idx = idx
                break
                
        if clicked_ax_idx == -1:
            return
            
        filename = self.current_measurements[clicked_ax_idx]
        x, y = self.display_profile(filename)

        # Snap to closest data point
        click_x = event.xdata
        idx = np.abs(x - click_x).argmin()
        
        self.handle_plot_click(clicked_ax_idx, idx, x, y)

    def handle_plot_click(self, ax_idx, data_idx, x, y):
        """Processes clicks for a specific plot, rotating selections (0 -> 1 -> 2 -> 0)."""
        current_clicks = self.clicks[ax_idx]
        
        if len(current_clicks) == 0:
            # First click: select Point 1
            self.clicks[ax_idx] = [data_idx]
            self.clicked_coords[ax_idx][0] = (x[data_idx], y[data_idx])
            self.update_status(f"Plot {ax_idx+1}: Selected Point 1.")
            
        elif len(current_clicks) == 1:
            # Second click: select Point 2, calculate area
            self.clicks[ax_idx].append(data_idx)
            self.clicked_coords[ax_idx][1] = (x[data_idx], y[data_idx])
            
            # Compute area
            idx1, idx2 = self.clicks[ax_idx]
            self.computed_areas[ax_idx] = self.compute_area_between(x, y, idx1, idx2)
            self.detections[ax_idx] = None  # this selection is now the user's, not the detector's
            self.update_status(f"Plot {ax_idx+1}: Area calculated successfully.", is_success=True)

        else:
            # Third click: reset selections
            self.clicks[ax_idx] = []
            self.computed_areas[ax_idx] = None
            self.clicked_coords[ax_idx] = [None, None]
            self.detections[ax_idx] = None
            self.update_status(f"Plot {ax_idx+1}: Selections reset.")
            
        # Redraw only the modified subplot
        self.draw_subplot(ax_idx)
        self.canvas.draw()
        
        # Update results cards in sidebar
        self.update_results_display()

    def update_results_display(self):
        """Refreshes the numeric results printed in the sidebar cards."""
        for i in range(4):
            widget = self.plot_info_widgets[i]
            
            if i < len(self.current_measurements):
                filename = self.current_measurements[i]
                title_no_ext = os.path.splitext(filename)[0]
                widget['title'].config(text=title_no_ext, fg=COLOR_ACCENT)
                
                # Coordinate details
                coords = self.clicked_coords[i]
                p1_str = f"P1: ({coords[0][0]:.4f}, {coords[0][1]:.4f})" if coords[0] else "P1: Click to set"
                p2_str = f"P2: ({coords[1][0]:.4f}, {coords[1][1]:.4f})" if coords[1] else "P2: Click to set"
                widget['p1'].config(text=p1_str, fg=COLOR_TEXT)
                widget['p2'].config(text=p2_str, fg=COLOR_TEXT)
                
                # Area details
                area = self.computed_areas[i]
                area_str = f"Area: {area:.6e}" if area is not None else "Area: --"
                widget['area'].config(text=area_str, fg=COLOR_HIGHLIGHT)

                # Auto-detection status
                det = self.detections.get(i)
                if det is None:
                    widget['detect'].config(text="", fg=COLOR_TEXT_MUTED)
                    widget['card'].config(highlightbackground=COLOR_BORDER)
                elif det['status'] == 'ok':
                    widget['detect'].config(
                        text=f"✓ Auto-detected — depth {det['depth']:.2f}, "
                             f"width {det['width']:.3f}, confidence {det['confidence']*100:.0f}%",
                        fg=COLOR_SUCCESS
                    )
                    widget['card'].config(highlightbackground=COLOR_SUCCESS)
                else:
                    widget['detect'].config(
                        text=f"⚠ MANUAL SELECTION NEEDED — {det['reason']}",
                        fg=COLOR_WARN
                    )
                    widget['card'].config(highlightbackground=COLOR_WARN)
            else:
                # Reset card display if no measurement loaded for this index
                widget['title'].config(text=f"Measurement {i+1} (Empty)", fg=COLOR_TEXT_MUTED)
                widget['p1'].config(text="P1: --", fg=COLOR_TEXT_MUTED)
                widget['p2'].config(text="P2: --", fg=COLOR_TEXT_MUTED)
                widget['area'].config(text="Area: --", fg=COLOR_TEXT_MUTED)
                widget['detect'].config(text="")
                widget['card'].config(highlightbackground=COLOR_BORDER)

    def reset_all_selections(self, update_plot=True):
        """Clears all coordinates and computed areas across all subplots."""
        for i in range(4):
            self.clicks[i] = []
            self.computed_areas[i] = None
            self.clicked_coords[i] = [None, None]
            self.detections[i] = None

        self.update_results_display()
        
        if update_plot and self.canvas:
            for i in range(len(self.current_measurements)):
                self.draw_subplot(i)
            self.canvas.draw()
            self.update_status("All selections reset.")

    def save_selected_plots(self):
        """Saves both the raw and the analyzed grid plots as a high-resolution PNG image."""
        if not self.selected_sample:
            messagebox.showwarning("No Sample Loaded", "Please select a sample and plot it first.")
            return
            
        graphs_dir = os.path.join(self.current_dir, "..", "graphs")
        os.makedirs(graphs_dir, exist_ok=True)
        
        self.update_status("Saving roughness analysis plot...")
        
        # Save the current figure
        if self.fig:
            save_path = os.path.join(graphs_dir, f"{self.selected_sample}_roughness_analysis.png")
            # Save using high quality 300 DPI
            self.fig.savefig(save_path, dpi=300, facecolor=self.fig.get_facecolor(), edgecolor='none')
            messagebox.showinfo("Plot Saved Successfully", f"Roughness analysis grid saved successfully as:\n{save_path}")
            self.update_status(f"Saved {self.selected_sample}_roughness_analysis.png", is_success=True)

    def load_wear_rates_from_csv(self):
        """Loads wear rates from wear_rates_summary.csv in current directory if it exists."""
        self.wear_rates = {}
        csv_path = os.path.join(self.current_dir, "wear_rates_summary.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    sample = str(row['Sample'])
                    self.wear_rates[sample] = {
                        'radius': float(row['Radius (mm)']),
                        'distance': float(row['Distance (m)']),
                        'load': float(row['Load (N)']),
                        'avg_area': float(row['Avg Area (mm*um)']),
                        'volume': float(row['Wear Volume (mm^3)']),
                        'wear_rate': float(row['Specific Wear Rate (mm^3/N-m)'])
                    }
                self.update_status(f"Loaded {len(self.wear_rates)} saved wear rates from CSV.", is_success=True)
            except Exception as e:
                print(f"Error loading wear_rates_summary.csv: {e}")

    def save_wear_rate_to_csv(self, sample, data):
        """Saves/updates a single sample's wear rate data in wear_rates_summary.csv."""
        self.wear_rates[sample] = data
        
        # Prepare DataFrame to save
        rows = []
        for sname, sdata in self.wear_rates.items():
            rows.append({
                'Sample': sname,
                'Radius (mm)': sdata['radius'],
                'Distance (m)': sdata['distance'],
                'Load (N)': sdata['load'],
                'Avg Area (mm*um)': sdata['avg_area'],
                'Wear Volume (mm^3)': sdata['volume'],
                'Specific Wear Rate (mm^3/N-m)': sdata['wear_rate']
            })
        df = pd.DataFrame(rows)
        csv_path = os.path.join(self.current_dir, "wear_rates_summary.csv")
        try:
            df.to_csv(csv_path, index=False)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not write to wear_rates_summary.csv:\n{str(e)}")

    def calculate_wear_rate(self):
        """Calculates wear volume and specific wear rate, and saves them to memory & CSV."""
        if not self.selected_sample:
            messagebox.showwarning("No Sample Loaded", "Please select a sample and perform point measurements first.")
            return
            
        # Get parameter inputs
        try:
            radius = float(self.radius_ent.get())
            distance = float(self.dist_ent.get())
            load = float(self.load_ent.get())
            
            if radius <= 0 or distance <= 0 or load <= 0:
                raise ValueError("Values must be positive numbers.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid positive numbers for parameters.\nError: {e}")
            return
            
        # Find active subplots with calculated areas
        valid_areas = [self.computed_areas[i] for i in range(len(self.current_measurements)) if self.computed_areas[i] is not None]
        
        if not valid_areas:
            messagebox.showwarning("No Area Measurements", "Please select at least two points on one of the plots to calculate an area first.")
            return
            
        # 1. Average Area (mm * um)
        avg_area = np.mean(valid_areas)
        
        # Convert to mm^2 (divide by 1000)
        avg_area_mm2 = avg_area / 1000.0
        
        # 2. Wear Volume (mm^3) = Avg Area (mm^2) * 2 * pi * Radius (mm)
        volume = avg_area_mm2 * 2.0 * np.pi * radius
        
        # 3. Specific Wear Rate (mm^3 / N-m) = Volume (mm^3) / (Load (N) * Distance (m))
        wear_rate = volume / (load * distance)
        
        # Update display labels
        self.wear_vol_lbl.config(text=f"Wear Volume: {volume:.4e} mm³")
        self.wear_rate_lbl.config(text=f"Wear Rate: {wear_rate:.4e} mm³/(N·m)")
        
        # Save to memory and CSV
        data = {
            'radius': radius,
            'distance': distance,
            'load': load,
            'avg_area': avg_area,
            'volume': volume,
            'wear_rate': wear_rate
        }
        self.save_wear_rate_to_csv(self.selected_sample, data)
        self.update_status(f"Calculated specific wear rate for {self.selected_sample}: {wear_rate:.4e}", is_success=True)

    def show_wear_rate_chart(self):
        """Displays a bar chart of Specific Wear Rates in a new window."""
        if not self.wear_rates:
            messagebox.showwarning("No Data", "No calculated specific wear rates available. Please calculate at least one sample first.")
            return
            
        chart_win = tk.Toplevel(self.root)
        chart_win.title("Specific Wear Rate Comparison")
        chart_win.geometry("800x600")
        chart_win.configure(bg=COLOR_BG)
        chart_win.grab_set() # Make modal
        
        # Header inside popup
        hdr = tk.Label(
            chart_win,
            text="SPECIFIC WEAR RATE COMPARISON",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_ACCENT,
            bg=COLOR_BG,
            pady=15
        )
        hdr.pack(fill=tk.X)
        
        # Matplotlib Figure
        fig, ax = plt.subplots(figsize=(7, 4.5))
        fig.patch.set_facecolor('#ffffff')
        ax.set_facecolor('white')
        
        # Data preparation
        samples = list(self.wear_rates.keys())
        rates = [self.wear_rates[s]['wear_rate'] for s in samples]
        
        # Plot bars (using a beautiful palette)
        bars = ax.bar(samples, rates, color='#e84393', edgecolor='#0c2461', linewidth=1.0, width=0.5)
        
        # Customize labels and style
        ax.set_xlabel('Sample Name', fontsize=10, fontweight='bold', labelpad=10)
        ax.set_ylabel('Specific Wear Rate [mm³/(N·m)]', fontsize=10, fontweight='bold', labelpad=10)
        ax.grid(True, axis='y', color='#e2e8f0', linestyle='--', linewidth=0.5)
        
        # Format Y-axis in scientific notation
        ax.yaxis.get_major_formatter().set_powerlimits((0, 0))
        
        # Add values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2.,
                height + (height * 0.02),
                f"{height:.2e}",
                ha='center', va='bottom', fontsize=8, fontweight='bold'
            )
            
        # Spines and ticks
        for spine in ax.spines.values():
            spine.set_color('black')
            spine.set_linewidth(1.0)
        ax.tick_params(colors='black', labelsize=9)
        plt.xticks(rotation=15)
        
        fig.tight_layout()
        
        # Embed canvas
        canvas_frame = tk.Frame(chart_win, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Button frame
        btn_frame = tk.Frame(chart_win, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=15)
        
        def save_chart():
            graphs_dir = os.path.join(self.current_dir, "..", "graphs")
            os.makedirs(graphs_dir, exist_ok=True)
            save_path = os.path.join(graphs_dir, "wear_rates_comparison.png")
            fig.savefig(save_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
            messagebox.showinfo("Chart Saved", f"Comparison chart saved as:\n{save_path}")
            
        save_btn = tk.Button(
            btn_frame,
            text="💾 Save Graph Image",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=save_chart
        )
        save_btn.pack(side=tk.LEFT, padx=20)
        
        def on_close():
            plt.close(fig)
            chart_win.destroy()
            
        chart_win.protocol("WM_DELETE_WINDOW", on_close)
        
        close_btn = tk.Button(
            btn_frame,
            text="❌ Close",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_HIGHLIGHT,
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=on_close
        )
        close_btn.pack(side=tk.RIGHT, padx=20)

    def update_status(self, message, is_success=False):
        """Updates text of status bar."""
        color = COLOR_SUCCESS if is_success else COLOR_TEXT_MUTED
        self.status_lbl.config(text=message, fg=color)
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = RoughnessAnalyserApp(root)
    root.mainloop()
