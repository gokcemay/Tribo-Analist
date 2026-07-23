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
        self.dir_btn.pack(fill=tk.X, pady=(0, 15))
        
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
            
            self.plot_info_widgets.append({
                'card': card,
                'title': title,
                'p1': p1_lbl,
                'p2': p2_lbl,
                'area': area_lbl
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
                 "2. Click once on any plot to set Point 1.\n"
                 "3. Click again to set Point 2.\n"
                 "4. A line is drawn and the area shaded.\n"
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
        Loads the 'DATA' sheet from the Excel file.
        Uses columns E (4) and F (5) as X and Y data points.
        Caches it in self.loaded_data.
        """
        filename = os.path.basename(file_path)
        if filename in self.loaded_data:
            return self.loaded_data[filename]
            
        # Read excel with sheet 'DATA' and header=None (0-indexed columns)
        df = pd.read_excel(file_path, sheet_name='DATA', header=None, engine='xlrd')
        
        # E (column index 4) and F (column index 5) must contain numerical roughness values
        # We drop any NaNs and convert to float
        data = df[[4, 5]].dropna()
        x = data[4].astype(float).values
        y = data[5].astype(float).values
        
        if len(x) == 0:
            raise ValueError("No numeric data rows found in columns E and F of sheet 'DATA'.")
            
        # Ensure it is sorted by x coordinates
        sort_idx = np.argsort(x)
        x = x[sort_idx]
        y = y[sort_idx]
        
        self.loaded_data[filename] = (x, y)
        return x, y

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
                filename = self.current_measurements[i]
                x, y = self.loaded_data[filename]
                
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
        x, y = self.loaded_data[filename]
        
        # Clean scientific style
        ax.set_facecolor('white')
        ax.grid(True, color='#e2e8f0', linestyle='--', linewidth=0.5)
        
        # Plot raw profile data (Navy color)
        ax.plot(x, y, color='#0c2461', linewidth=1.0, zorder=2, label="Profile")
        
        # Title and Labels
        title_no_ext = os.path.splitext(filename)[0]
        ax.set_title(title_no_ext, fontsize=11, fontweight='bold', pad=10)
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
        x, y = self.loaded_data[filename]
        
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
            idx_min, idx_max = min(idx1, idx2), max(idx1, idx2)
            
            x_slice = x[idx_min : idx_max + 1]
            y_slice = y[idx_min : idx_max + 1]
            
            # Straight line points
            if x[idx2] != x[idx1]:
                y_line = y[idx1] + (y[idx2] - y[idx1]) / (x[idx2] - x[idx1]) * (x_slice - x[idx1])
            else:
                y_line = np.full_like(x_slice, y[idx1])
                
            # Absolute difference area calculation (Trapezoidal integration rule)
            diff = np.abs(y_slice - y_line)
            
            # Manual robust trapezoidal implementation (compatible with NumPy 1.x and 2.x)
            dx = np.diff(x_slice)
            diff_mean = (diff[:-1] + diff[1:]) / 2.0
            area = np.sum(diff_mean * dx)
            
            self.computed_areas[ax_idx] = area
            self.update_status(f"Plot {ax_idx+1}: Area calculated successfully.", is_success=True)
            
        else:
            # Third click: reset selections
            self.clicks[ax_idx] = []
            self.computed_areas[ax_idx] = None
            self.clicked_coords[ax_idx] = [None, None]
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
                widget['card'].config(highlightbackground=COLOR_BORDER)
            else:
                # Reset card display if no measurement loaded for this index
                widget['title'].config(text=f"Measurement {i+1} (Empty)", fg=COLOR_TEXT_MUTED)
                widget['p1'].config(text="P1: --", fg=COLOR_TEXT_MUTED)
                widget['p2'].config(text="P2: --", fg=COLOR_TEXT_MUTED)
                widget['area'].config(text="Area: --", fg=COLOR_TEXT_MUTED)
                widget['card'].config(highlightbackground=COLOR_BORDER)

    def reset_all_selections(self, update_plot=True):
        """Clears all coordinates and computed areas across all subplots."""
        for i in range(4):
            self.clicks[i] = []
            self.computed_areas[i] = None
            self.clicked_coords[i] = [None, None]
            
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
