import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Dark theme color palette (Catppuccin Mocha inspired for premium look)
COLOR_BG = "#1E1E2E"         # Deep charcoal/navy background
COLOR_SIDEBAR = "#11111B"    # Darker sidebar background
COLOR_CARD = "#181825"       # Sub-panel/Card background
COLOR_ACCENT = "#89B4FA"     # Vibrant blue/periwinkle accent
COLOR_ACCENT_HOVER = "#B4BEFE" # Hover color
COLOR_SUCCESS = "#A6E3A1"    # Green accent for saving
COLOR_TEXT = "#CDD6F4"       # Primary light text
COLOR_TEXT_MUTED = "#A6ADC8" # Muted text
COLOR_BORDER = "#313244"     # Panel borders
COLOR_BUTTON = "#313244"     # Default button background
COLOR_BUTTON_HOVER = "#45475A" # Button hover

class TriboPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CLab Tribo Data Plotter")
        self.root.geometry("1220x880")
        self.root.minsize(950, 750)
        self.root.configure(bg=COLOR_BG)
        
        # State variables
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.txt_files = []
        self.file_vars = []  # List of tuples: (filename, tk.BooleanVar)
        self.plotted_data = {}  # Cache of parsed data: {filename: (distances, mus)}
        self.active_plots = []  # List of filenames currently plotted
        self.current_plot_index = -1
        
        # Filter State
        self.filter_enabled = tk.BooleanVar(value=True)
        self.filter_window = tk.IntVar(value=51)  # Default window size
        
        # Overlay Mode State
        self.overlay_mode = tk.BooleanVar(value=False)
        
        # UI Elements setup
        self.setup_styles()
        self.build_ui()
        
        # Load files in the initial directory
        self.load_directory(self.current_dir)

    def setup_styles(self):
        """Set up styling and configurations for the ttk widgets."""
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure styles to match the dark theme
        self.style.configure('.', bg=COLOR_BG, fg=COLOR_TEXT)
        
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
            text="CLAB TRIBO DATA PLOTTER", 
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
        
        # Left Sidebar (width 320px)
        self.sidebar = tk.Frame(self.main_container, bg=COLOR_SIDEBAR, width=320, bd=0, highlightthickness=0)
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
        # Padding wrapper
        pad_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR, padx=15, pady=15)
        pad_frame.pack(fill=tk.BOTH, expand=True)
        
        # Folder Selector Button
        self.dir_btn = tk.Button(
            pad_frame,
            text="📁 Select Folder",
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
        
        # File list section header
        lbl = tk.Label(
            pad_frame,
            text="SELECT FILES:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        lbl.pack(fill=tk.X, pady=(0, 5))
        
        # Scrollable file list container (Canvas + Scrollbar)
        list_outer = tk.Frame(pad_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        list_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        self.canvas = tk.Canvas(list_outer, bg=COLOR_CARD, bd=0, highlightthickness=0, yscrollincrement=4)
        self.scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview, style="TScrollbar")
        self.scroll_frame = tk.Frame(self.canvas, bg=COLOR_CARD)
        
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        
        # Bind canvas resize to stretch the scroll_frame horizontally
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfig(self.canvas_frame_id, width=event.width))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Selection helper buttons (All / None)
        sel_btn_frame = tk.Frame(pad_frame, bg=COLOR_SIDEBAR)
        sel_btn_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.all_btn = tk.Button(
            sel_btn_frame,
            text="Select All",
            font=("Segoe UI", 9),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_TEXT,
            bd=0,
            padx=5,
            pady=4,
            cursor="hand2",
            command=self.select_all_files
        )
        self.all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.none_btn = tk.Button(
            sel_btn_frame,
            text="Deselect All",
            font=("Segoe UI", 9),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_TEXT,
            bd=0,
            padx=5,
            pady=4,
            cursor="hand2",
            command=self.deselect_all_files
        )
        self.none_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Plot Options card
        options_lbl = tk.Label(
            pad_frame,
            text="PLOT OPTIONS:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        options_lbl.pack(fill=tk.X, pady=(5, 5))
        
        options_card = tk.Frame(pad_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=12, pady=12)
        options_card.pack(fill=tk.X, pady=(0, 15))
        
        # Overlay mode checkbox
        self.overlay_chk = tk.Checkbutton(
            options_card,
            text="Overlay Mode (Aynı Plotta Göster)",
            variable=self.overlay_mode,
            onvalue=True,
            offvalue=False,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            selectcolor=COLOR_SIDEBAR,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_ACCENT,
            font=("Segoe UI", 9, "bold"),
            command=self.on_overlay_toggle
        )
        self.overlay_chk.pack(anchor=tk.W)
        
        # Filter settings section
        filter_lbl = tk.Label(
            pad_frame,
            text="FILTER SETTINGS:",
            fg=COLOR_ACCENT,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W
        )
        filter_lbl.pack(fill=tk.X, pady=(5, 5))
        
        filter_card = tk.Frame(pad_frame, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=12, pady=12)
        filter_card.pack(fill=tk.X, pady=(0, 15))
        
        # Checkbutton to enable/disable filter
        self.filter_chk = tk.Checkbutton(
            filter_card,
            text="Enable Moving Average",
            variable=self.filter_enabled,
            onvalue=True,
            offvalue=False,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            selectcolor=COLOR_SIDEBAR,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_ACCENT,
            font=("Segoe UI", 9, "bold"),
            command=self.on_filter_toggle
        )
        self.filter_chk.pack(anchor=tk.W, pady=(0, 6))
        
        # Slider label
        self.slider_val_lbl = tk.Label(
            filter_card,
            text=f"Window Size: {self.filter_window.get()} points",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 9)
        )
        self.slider_val_lbl.pack(anchor=tk.W)
        
        # Slider
        self.slider = tk.Scale(
            filter_card,
            from_=3,
            to=301,
            resolution=2,
            orient=tk.HORIZONTAL,
            variable=self.filter_window,
            showvalue=False,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            troughcolor=COLOR_SIDEBAR,
            highlightthickness=0,
            activebackground=COLOR_ACCENT,
            command=self.on_slider_move
        )
        self.slider.pack(fill=tk.X, pady=(5, 0))
        
        # Plot Action Button
        self.plot_btn = tk.Button(
            pad_frame,
            text="📊 Plot Selected",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT,
            fg=COLOR_SIDEBAR,
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground=COLOR_SIDEBAR,
            bd=0,
            padx=10,
            pady=10,
            cursor="hand2",
            command=self.plot_selected_files
        )
        self.plot_btn.pack(fill=tk.X, pady=(0, 8))
        
        # Save Action Button
        self.save_btn = tk.Button(
            pad_frame,
            text="💾 Save Selected Plots",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_SUCCESS,
            fg=COLOR_SIDEBAR,
            activebackground="#C2F0C2",
            activeforeground=COLOR_SIDEBAR,
            bd=0,
            padx=10,
            pady=10,
            cursor="hand2",
            command=self.save_selected_plots
        )
        self.save_btn.pack(fill=tk.X)

    def build_content_area(self):
        """Build the main content window with custom flat tabs."""
        # Top tab navigation bar
        self.tab_bar = tk.Frame(self.content_area, bg=COLOR_SIDEBAR, height=42)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP)
        self.tab_bar.pack_propagate(False)
        
        self.tab1_btn = tk.Button(
            self.tab_bar,
            text="📈 Friction Curves",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_ACCENT,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=20,
            cursor="hand2",
            command=lambda: self.switch_tab(1)
        )
        self.tab1_btn.pack(side=tk.LEFT, fill=tk.Y)
        
        self.tab2_btn = tk.Button(
            self.tab_bar,
            text="📊 Average µ Comparison",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SIDEBAR,
            fg=COLOR_TEXT,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=20,
            cursor="hand2",
            command=lambda: self.switch_tab(2)
        )
        self.tab2_btn.pack(side=tk.LEFT, fill=tk.Y)
        
        # Sub-panel for curve navigation (Previous/Next)
        self.nav_frame = tk.Frame(self.content_area, bg=COLOR_BG, padx=20, pady=10)
        self.nav_frame.pack(fill=tk.X)
        
        self.prev_btn = tk.Button(
            self.nav_frame,
            text="◀ Previous",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.prev_plot
        )
        self.prev_btn.pack(side=tk.LEFT)
        self.prev_btn.pack_forget()
        
        self.plot_info_lbl = tk.Label(
            self.nav_frame,
            text="Select files from the sidebar and click 'Plot Selected' to view.",
            fg=COLOR_TEXT,
            bg=COLOR_BG,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.CENTER
        )
        self.plot_info_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.next_btn = tk.Button(
            self.nav_frame,
            text="Next ▶",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.next_plot
        )
        self.next_btn.pack(side=tk.RIGHT)
        self.next_btn.pack_forget()
        
        # Container for the panels
        self.display_container = tk.Frame(self.content_area, bg=COLOR_BG)
        self.display_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.display_container.rowconfigure(0, weight=1)
        self.display_container.columnconfigure(0, weight=1)
        
        # Panel 1: Curves
        self.graph_panel = tk.Frame(self.display_container, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        self.graph_panel.grid(row=0, column=0, sticky="nsew")
        
        # Placeholder for Curves
        self.placeholder_lbl = tk.Label(
            self.graph_panel,
            text="📈\nNo active plot.\n\nChoose files on the left sidebar and click Plot Selected.",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 13, "italic"),
            justify=tk.CENTER
        )
        self.placeholder_lbl.pack(fill=tk.BOTH, expand=True)
        
        # Panel 2: Bar Chart
        self.bar_panel = tk.Frame(self.display_container, bg=COLOR_CARD, bd=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
        self.bar_panel.grid(row=0, column=0, sticky="nsew")
        
        # Placeholder for Bar Chart
        self.bar_placeholder_lbl = tk.Label(
            self.bar_panel,
            text="📊\nNo average comparison data.\n\nChoose files and click Plot Selected to compile averages.",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 13, "italic"),
            justify=tk.CENTER
        )
        self.bar_placeholder_lbl.pack(fill=tk.BOTH, expand=True)
        
        # Canvas states
        self.current_canvas = None
        self.current_bar_canvas = None
        
        # Default tab show
        self.switch_tab(1)

    def switch_tab(self, tab_num):
        """Switches between the curve panel (tab 1) and average comparison panel (tab 2)."""
        self.active_tab = tab_num
        if tab_num == 1:
            self.tab1_btn.config(bg=COLOR_CARD, fg=COLOR_ACCENT)
            self.tab2_btn.config(bg=COLOR_SIDEBAR, fg=COLOR_TEXT)
            self.graph_panel.tkraise()
            # Restore navigation buttons if applicable
            if self.active_plots and not self.overlay_mode.get() and len(self.active_plots) > 1:
                self.prev_btn.pack(side=tk.LEFT)
                self.next_btn.pack(side=tk.RIGHT)
        else:
            self.tab1_btn.config(bg=COLOR_SIDEBAR, fg=COLOR_TEXT)
            self.tab2_btn.config(bg=COLOR_CARD, fg=COLOR_ACCENT)
            self.bar_panel.tkraise()
            # Hide individual navigation buttons under bar chart view
            self.prev_btn.pack_forget()
            self.next_btn.pack_forget()

    def load_directory(self, path):
        """Scans the directory for .txt files and refreshes the sidebar."""
        self.current_dir = path
        self.folder_lbl.config(text=f"Folder: {self.current_dir}")
        self.update_status(f"Scanning folder: {self.current_dir}")
        
        try:
            # Find all files ending in .txt (ignore case)
            all_files = os.listdir(path)
            self.txt_files = sorted([f for f in all_files if f.lower().endswith('.txt') and os.path.isfile(os.path.join(path, f))])
            
            # Reset cache and active plots when loading a new folder
            self.plotted_data.clear()
            self.active_plots = []
            self.current_plot_index = -1
            
            self.update_file_list()
            self.update_status(f"Found {len(self.txt_files)} text files in directory.")
            
            # Clear existing canvases
            if self.current_canvas:
                self.current_canvas.get_tk_widget().destroy()
                self.current_canvas = None
            if self.current_bar_canvas:
                self.current_bar_canvas.get_tk_widget().destroy()
                self.current_bar_canvas = None
                
            self.placeholder_lbl.pack(fill=tk.BOTH, expand=True)
            self.bar_placeholder_lbl.pack(fill=tk.BOTH, expand=True)
            self.prev_btn.pack_forget()
            self.next_btn.pack_forget()
            self.plot_info_lbl.config(text="Select files from the sidebar and click 'Plot Selected' to view.")
            self.switch_tab(1)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not read directory:\n{str(e)}")
            self.update_status("Error loading directory.")

    def update_file_list(self):
        """Regenerates the list of files in the sidebar with checkboxes."""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        self.file_vars = []
        
        if not self.txt_files:
            no_file_lbl = tk.Label(
                self.scroll_frame, 
                text="No .txt files found.", 
                bg=COLOR_CARD, 
                fg=COLOR_TEXT_MUTED,
                font=("Segoe UI", 10, "italic"),
                pady=20
            )
            no_file_lbl.pack(fill=tk.X)
            return
            
        for file in self.txt_files:
            var = tk.BooleanVar(value=True)  # Default checked
            self.file_vars.append((file, var))
            
            row_frame = tk.Frame(self.scroll_frame, bg=COLOR_CARD, pady=1)
            row_frame.pack(fill=tk.X, anchor=tk.W)
            
            chk = tk.Checkbutton(
                row_frame, 
                text=file, 
                variable=var,
                onvalue=True,
                offvalue=False,
                bg=COLOR_CARD,
                fg=COLOR_TEXT,
                selectcolor=COLOR_SIDEBAR,
                activebackground=COLOR_CARD,
                activeforeground=COLOR_ACCENT,
                font=("Segoe UI", 10),
                anchor=tk.W,
                justify=tk.LEFT
            )
            chk.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=5)
            
            def make_hover_funcs(rf, c):
                return (
                    lambda e: (rf.config(bg="#313244"), c.config(bg="#313244")),
                    lambda e: (rf.config(bg=COLOR_CARD), c.config(bg=COLOR_CARD))
                )
            
            enter, leave = make_hover_funcs(row_frame, chk)
            row_frame.bind("<Enter>", enter)
            row_frame.bind("<Leave>", leave)
            chk.bind("<Enter>", enter)
            chk.bind("<Leave>", leave)
            
            chk.bind("<Double-Button-1>", lambda e, f=file: self.quick_plot_file(f))

    def quick_plot_file(self, filename):
        """Double click file to select and view immediately."""
        for f, var in self.file_vars:
            if f == filename:
                var.set(True)
        self.plot_selected_files(focus_file=filename)

    def browse_folder(self):
        """Prompts the user to select a folder."""
        selected = filedialog.askdirectory(initialdir=self.current_dir, title="Select Tribo Data Folder")
        if selected:
            self.load_directory(selected)

    def select_all_files(self):
        """Checks all files in the list."""
        for _, var in self.file_vars:
            var.set(True)

    def deselect_all_files(self):
        """Unchecks all files in the list."""
        for _, var in self.file_vars:
            var.set(False)

    def on_overlay_toggle(self):
        """Called when overlay mode is toggled."""
        if self.active_plots:
            self.render_active_plots()

    def on_filter_toggle(self):
        """Called when filter checkbox is toggled."""
        if self.filter_enabled.get():
            self.slider.config(state=tk.NORMAL)
        else:
            self.slider.config(state=tk.DISABLED)
            
        if self.active_plots:
            self.render_active_plots()

    def on_slider_move(self, val):
        """Called when filter slider is moved."""
        self.slider_val_lbl.config(text=f"Window Size: {val} points")
        if self.active_plots:
            self.render_active_plots()

    def update_status(self, message, is_success=False):
        """Updates status bar message."""
        color = COLOR_SUCCESS if is_success else COLOR_TEXT_MUTED
        self.status_lbl.config(text=message, fg=color)
        self.root.update_idletasks()

    def parse_tribo_file(self, file_path):
        """Parses data file, skips metadata, handles decimal commas and multiple file encodings."""
        filename = os.path.basename(file_path)
        if filename in self.plotted_data:
            return self.plotted_data[filename]
            
        distances = []
        mus = []
        
        # Read raw bytes first to try multiple encodings cleanly
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            
        encodings_to_try = ['utf-16-le', 'utf-16', 'utf-8-sig', 'utf-8', 'cp1254', 'latin1']
        decoded_text = None
        
        for enc in encodings_to_try:
            try:
                text = raw_data.decode(enc)
                if 'time' in text.lower() and 'distance' in text.lower():
                    decoded_text = text
                    break
                if decoded_text is None:
                    decoded_text = text
            except (UnicodeDecodeError, ValueError):
                continue
                
        if decoded_text is None:
            decoded_text = raw_data.decode('latin1', errors='replace')
            
        lines = decoded_text.splitlines()
            
        header_found = False
        dist_col_idx = 1
        mu_col_idx = 3
        
        for line in lines:
            if not header_found:
                line_lower = line.lower()
                if 'time' in line_lower and 'distance' in line_lower:
                    cols = [c.strip() for c in line.split('\t')]
                    for idx, col in enumerate(cols):
                        col_lower = col.lower()
                        if 'distance' in col_lower:
                            dist_col_idx = idx
                        elif 'µ' in col or 'mu' in col_lower or 'friction' in col_lower or col.strip() == '' or idx == 3:
                            mu_col_idx = idx
                    header_found = True
                continue
            
            parts = line.strip().split('\t')
            if len(parts) > max(dist_col_idx, mu_col_idx):
                try:
                    dist_str = parts[dist_col_idx].strip().replace(',', '.')
                    mu_str = parts[mu_col_idx].strip().replace(',', '.')
                    if dist_str and mu_str:
                        distances.append(float(dist_str))
                        mus.append(float(mu_str))
                except ValueError:
                    continue
                    
        if not header_found:
            raise ValueError("Header containing 'Time' and 'Distance' was not found.")
        if not distances:
            raise ValueError("No numeric data rows could be parsed.")
            
        self.plotted_data[filename] = (distances, mus)
        return distances, mus

    def apply_filter(self, data, window_size):
        """Applies rolling mean filter."""
        if window_size <= 1:
            return data
        return pd.Series(data).rolling(window=window_size, min_periods=1, center=True).mean().tolist()

    def generate_plot(self, filenames, overlay=False, filter_on=False, window_size=51, index_to_show=0):
        """
        Generates the Matplotlib line plot (Distance vs. µ) in academic style.
        Puts legend inside the plot in the bottom-left corner with an opaque background
        so curves/lines do not cross through the legend text.
        """
        fig, ax = plt.subplots(figsize=(8.5, 5))
        
        # Scientific Style Configuration
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.grid(True, color='#e2e8f0', linestyle='--', linewidth=0.5)
        
        for spine in ax.spines.values():
            spine.set_color('black')
            spine.set_linewidth(1.0)
            spine.set_visible(True)
            
        ax.tick_params(colors='black', labelsize=9.5, direction='out', length=5, width=1)
        
        # Academic palette
        colors = ['#0c2461', '#b71540', '#079992', '#e58e26', '#6c5ce7', '#1e3799', '#78e08f', '#f6b93b']
        
        if overlay:
            for i, fname in enumerate(filenames):
                dist, mu = self.plotted_data[fname]
                color = colors[i % len(colors)]
                label_name = os.path.splitext(fname)[0]
                
                if filter_on and window_size > 1:
                    filtered_mu = self.apply_filter(mu, window_size)
                    # Use zorder=1 to keep lines below the legend box (drawn with higher zorder or default)
                    ax.plot(dist, filtered_mu, color=color, linewidth=1.8, label=label_name, zorder=2)
                else:
                    ax.plot(dist, mu, color=color, linewidth=1.0, alpha=0.8, label=label_name, zorder=2)
            
            ax.set_title("Friction Coefficient vs Distance (Overlay)", fontsize=12, fontweight='bold', color='black', pad=15)
            
            # Place legend inside the plot box at the bottom-right
            # framealpha=1.0 (fully opaque) and facecolor='white' ensures lines are hidden behind it
            leg = ax.legend(
                facecolor='white', 
                edgecolor='black', 
                framealpha=1.0, 
                fontsize=9.5, 
                loc='lower right'
            )
            leg.set_zorder(5)
            
            file_names_str = ", ".join([os.path.splitext(f)[0] for f in filenames])
            if len(file_names_str) > 75:
                file_names_str = f"{len(filenames)} files loaded"
            
            filter_info = f"  |  Filter: Moving Average (w={window_size} pts)" if (filter_on and window_size > 1) else ""
            footnote = f"Source: {file_names_str}{filter_info}"
            
        else:
            if index_to_show < len(filenames):
                fname = filenames[index_to_show]
                dist, mu = self.plotted_data[fname]
                label_name = os.path.splitext(fname)[0]
                
                if filter_on and window_size > 1:
                    ax.plot(dist, mu, color='#cbd5e1', alpha=0.5, linewidth=0.8, label='Raw Data', zorder=2)
                    filtered_mu = self.apply_filter(mu, window_size)
                    ax.plot(dist, filtered_mu, color='#b71540', linewidth=1.8, label='Filtered Trend', zorder=3)
                    
                    # Place legend inside the plot box at the bottom-right with opaque background
                    leg = ax.legend(
                        facecolor='white', 
                        edgecolor='black', 
                        framealpha=1.0, 
                        fontsize=9.5, 
                        loc='lower right'
                    )
                    leg.set_zorder(5)
                    footnote = f"Source File: {fname}  |  Filter: Moving Average (w={window_size} pts)"
                else:
                    ax.plot(dist, mu, color='#0c2461', linewidth=1.2, zorder=2)
                    footnote = f"Source File: {fname}"
                    
                ax.set_title(f"Friction Coefficient vs Distance - {label_name}", fontsize=12, fontweight='bold', color='black', pad=15)
            else:
                footnote = ""
        
        ax.set_xlabel('Distance [m]', color='black', fontsize=11, fontweight='semibold', labelpad=6)
        ax.set_ylabel('Friction Coefficient (µ)', color='black', fontsize=11, fontweight='semibold', labelpad=6)
        
        fig.text(0.5, 0.02, footnote, ha='center', va='bottom', color='#475569', fontsize=9, style='italic')
        fig.tight_layout(rect=[0, 0.06, 1, 0.96])
        
        return fig

    def generate_bar_plot(self, filenames):
        """
        Generates a Matplotlib bar plot comparing the average friction coefficient
        of the selected files, styled for academic publications.
        """
        fig, ax = plt.subplots(figsize=(8.5, 5))
        
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.grid(True, color='#e2e8f0', linestyle='--', linewidth=0.5)
        
        for spine in ax.spines.values():
            spine.set_color('black')
            spine.set_linewidth(1.0)
            spine.set_visible(True)
            
        ax.tick_params(colors='black', labelsize=9.5, direction='out', length=5, width=1)
        
        # Calculate average µ
        names = []
        averages = []
        for fname in filenames:
            dist, mu = self.plotted_data[fname]
            names.append(os.path.splitext(fname)[0])
            averages.append(sum(mu) / len(mu) if mu else 0)
            
        colors = ['#0c2461', '#b71540', '#079992', '#e58e26', '#6c5ce7', '#1e3799', '#78e08f', '#f6b93b']
        bar_colors = [colors[i % len(colors)] for i in range(len(filenames))]
        
        # Draw bars
        bars = ax.bar(names, averages, color=bar_colors, edgecolor='black', width=0.5)
        
        # Add value label on top of each bar
        for bar in bars:
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2.0, 
                yval + 0.015 * (max(averages) if averages else 1), 
                f"{yval:.4f}", 
                ha='center', 
                va='bottom', 
                fontsize=9, 
                fontweight='bold',
                color='black'
            )
            
        # Title and Labels
        ax.set_title("Average Friction Coefficient Comparison", fontsize=12, fontweight='bold', color='black', pad=15)
        ax.set_xlabel('Tested Samples', color='black', fontsize=11, fontweight='semibold', labelpad=8)
        ax.set_ylabel('Average Friction Coefficient (Mean µ)', color='black', fontsize=11, fontweight='semibold', labelpad=8)
        
        # Give Y-axis extra headroom for labels on top of bars
        if averages:
            ax.set_ylim(0, max(averages) * 1.15)
            
        footnote = "Average µ values computed over the entire measured distance"
        fig.text(0.5, 0.02, footnote, ha='center', va='bottom', color='#475569', fontsize=9, style='italic')
        fig.tight_layout(rect=[0, 0.06, 1, 0.96])
        
        return fig

    def plot_selected_files(self, focus_file=None):
        """Parses and renders selected files on the canvas."""
        checked_files = [f for f, var in self.file_vars if var.get()]
        
        if not checked_files:
            messagebox.showwarning("No Files Selected", "Please select at least one file to plot.")
            return
            
        self.update_status(f"Parsing {len(checked_files)} files...")
        
        success_count = 0
        failed_files = []
        
        # Parse and cache files
        for filename in checked_files:
            file_path = os.path.join(self.current_dir, filename)
            try:
                self.parse_tribo_file(file_path)
                success_count += 1
            except Exception as e:
                failed_files.append((filename, str(e)))
        
        if success_count > 0:
            self.active_plots = [f for f in checked_files if f in self.plotted_data]
            
            self.placeholder_lbl.pack_forget()
            
            if focus_file and focus_file in self.active_plots:
                self.current_plot_index = self.active_plots.index(focus_file)
            else:
                self.current_plot_index = 0
                
            self.render_active_plots()
            
            # Switch back to the active tab to show the curve immediately
            self.switch_tab(self.active_tab)
            
            msg = f"Plotted {success_count} files."
            if failed_files:
                msg += f" ({len(failed_files)} failed)"
            self.update_status(msg, is_success=True)
            
            if failed_files:
                fail_msg = "\n".join([f"- {f}: {err}" for f, err in failed_files])
                messagebox.showwarning("Some files failed to parse", f"The following files could not be processed:\n\n{fail_msg}")
        else:
            fail_msg = "\n".join([f"- {f}: {err}" for f, err in failed_files])
            messagebox.showerror("Error", f"Failed to plot selected files:\n\n{fail_msg}")
            self.update_status("Plotting failed.")

    def render_active_plots(self):
        """Draws curves and updates the average comparison chart."""
        if not self.active_plots:
            return
            
        # 1. Curve drawing
        if self.overlay_mode.get():
            self.show_overlay_plot()
        else:
            self.show_plot(self.current_plot_index)
            
        # 2. Bar chart drawing
        self.show_bar_plot()

    def show_overlay_plot(self):
        """Renders overlaid curves."""
        if self.current_canvas:
            self.current_canvas.get_tk_widget().destroy()
            self.current_canvas = None
            
        self.prev_btn.pack_forget()
        self.next_btn.pack_forget()
        
        fig = self.generate_plot(
            self.active_plots, 
            overlay=True, 
            filter_on=self.filter_enabled.get(), 
            window_size=self.filter_window.get()
        )
        
        self.current_canvas = FigureCanvasTkAgg(fig, master=self.graph_panel)
        self.current_canvas.draw()
        self.current_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.plot_info_lbl.config(text=f"Viewing: Overlaid plot of {len(self.active_plots)} files")
        plt.close(fig)

    def show_plot(self, index):
        """Renders single curve."""
        if not (0 <= index < len(self.active_plots)):
            return
            
        self.current_plot_index = index
        filename = self.active_plots[index]
        
        if self.current_canvas:
            self.current_canvas.get_tk_widget().destroy()
            self.current_canvas = None
            
        # Re-pack navigation buttons if multiple files exist and tab 1 is active
        if self.active_tab == 1 and len(self.active_plots) > 1:
            self.prev_btn.pack(side=tk.LEFT)
            self.next_btn.pack(side=tk.RIGHT)
        else:
            self.prev_btn.pack_forget()
            self.next_btn.pack_forget()
            
        fig = self.generate_plot(
            self.active_plots, 
            overlay=False, 
            filter_on=self.filter_enabled.get(), 
            window_size=self.filter_window.get(),
            index_to_show=index
        )
        
        self.current_canvas = FigureCanvasTkAgg(fig, master=self.graph_panel)
        self.current_canvas.draw()
        self.current_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.plot_info_lbl.config(text=f"Viewing: {filename}  ({index + 1} of {len(self.active_plots)})")
        
        if index == 0:
            self.prev_btn.config(state=tk.DISABLED, bg=COLOR_BG)
        else:
            self.prev_btn.config(state=tk.NORMAL, bg=COLOR_BUTTON)
            
        if index == len(self.active_plots) - 1:
            self.next_btn.config(state=tk.DISABLED, bg=COLOR_BG)
        else:
            self.next_btn.config(state=tk.NORMAL, bg=COLOR_BUTTON)
            
        plt.close(fig)

    def show_bar_plot(self):
        """Renders the bar comparison chart."""
        if self.current_bar_canvas:
            self.current_bar_canvas.get_tk_widget().destroy()
            self.current_bar_canvas = None
            
        self.bar_placeholder_lbl.pack_forget()
        
        fig = self.generate_bar_plot(self.active_plots)
        
        self.current_bar_canvas = FigureCanvasTkAgg(fig, master=self.bar_panel)
        self.current_bar_canvas.draw()
        self.current_bar_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        plt.close(fig)

    def save_selected_plots(self):
        """Saves current plot curves and compiles comparison bar charts at 300 DPI."""
        checked_files = [f for f, var in self.file_vars if var.get()]
        
        if not checked_files:
            messagebox.showwarning("No Files Selected", "Please select files to save.")
            return
            
        # Compile unparsed cache if saving unchecked items
        unparsed_files = [f for f in checked_files if f not in self.plotted_data]
        if unparsed_files:
            self.update_status("Parsing unchecked files before saving...")
            for filename in unparsed_files:
                file_path = os.path.join(self.current_dir, filename)
                try:
                    self.parse_tribo_file(file_path)
                except Exception as e:
                    messagebox.showerror("Parse Error", f"Could not parse {filename}:\n{str(e)}")
                    return
                    
        valid_files = [f for f in checked_files if f in self.plotted_data]
        if not valid_files:
            return
            
        graphs_dir = os.path.join(self.current_dir, "graphs")
        os.makedirs(graphs_dir, exist_ok=True)
        
        self.update_status("Saving plots to disk...")
        saved_paths = []
        
        # 1. Save curve plot(s)
        if self.overlay_mode.get():
            fig = self.generate_plot(
                valid_files, 
                overlay=True, 
                filter_on=self.filter_enabled.get(), 
                window_size=self.filter_window.get()
            )
            save_path = os.path.join(graphs_dir, "overlaid_plot.png")
            fig.savefig(save_path, dpi=300)
            plt.close(fig)
            saved_paths.append("overlaid_plot.png")
        else:
            for filename in valid_files:
                fig = self.generate_plot(
                    [filename], 
                    overlay=False, 
                    filter_on=self.filter_enabled.get(), 
                    window_size=self.filter_window.get(),
                    index_to_show=0
                )
                name_no_ext = os.path.splitext(filename)[0]
                save_path = os.path.join(graphs_dir, f"{name_no_ext}_plot.png")
                fig.savefig(save_path, dpi=300)
                plt.close(fig)
                saved_paths.append(f"{name_no_ext}_plot.png")
                
        # 2. Save bar plot comparison chart
        bar_fig = self.generate_bar_plot(valid_files)
        bar_save_path = os.path.join(graphs_dir, "average_friction_plot.png")
        bar_fig.savefig(bar_save_path, dpi=300)
        plt.close(bar_fig)
        saved_paths.append("average_friction_plot.png")
        
        paths_str = "\n".join([f"- {p}" for p in saved_paths])
        messagebox.showinfo("Plots Saved Successfully", f"The following scientific plots were saved to your 'graphs' folder at 300 DPI:\n\n{paths_str}")
        self.update_status(f"Saved {len(saved_paths)} plot files successfully.", is_success=True)

    def next_plot(self):
        """Displays next plot."""
        if not self.overlay_mode.get() and self.current_plot_index < len(self.active_plots) - 1:
            self.show_plot(self.current_plot_index + 1)

    def prev_plot(self):
        """Displays previous plot."""
        if not self.overlay_mode.get() and self.current_plot_index > 0:
            self.show_plot(self.current_plot_index - 1)


if __name__ == "__main__":
    root = tk.Tk()
    app = TriboPlotterApp(root)
    root.mainloop()
