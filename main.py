import os
import sys
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

# Dark theme color palette (Catppuccin Mocha inspired for premium look)
COLOR_BG = "#1E1E2E"         # Deep charcoal/navy background
COLOR_SIDEBAR = "#11111B"    # Darker header/sidebar background
COLOR_CARD = "#181825"       # Sub-panel/Card background
COLOR_ACCENT_BLUE = "#89B4FA"# Vibrant blue accent
COLOR_ACCENT_GREEN = "#A6E3A1"# Vibrant green accent
COLOR_ACCENT_PURPLE = "#CBA6F7"# Vibrant purple accent
COLOR_HIGHLIGHT = "#F5C2E7"  # Pink accent
COLOR_TEXT = "#CDD6F4"       # Primary light text
COLOR_TEXT_MUTED = "#A6ADC8" # Muted text
COLOR_BORDER = "#313244"     # Panel borders
COLOR_BUTTON = "#313244"     # Default button background
COLOR_BUTTON_HOVER = "#45475A" # Button hover background
COLOR_WARN = "#F9E2AF"       # Amber accent

CONTACT_EMAIL = "gmehmetay@gmail.com"


class TriboAnalistLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Tribo-Analist — Test & Analysis Hub")
        self.root.geometry("1000x750")
        self.root.minsize(850, 650)
        self.root.configure(bg=COLOR_BG)

        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        self.build_ui()

    def build_ui(self):
        # 1. Top Header Bar
        header_frame = tk.Frame(self.root, bg=COLOR_SIDEBAR, height=80, bd=0, highlightthickness=0)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        header_title = tk.Label(
            header_frame,
            text="🔬 TRIBO-ANALİST",
            fg=COLOR_ACCENT_BLUE,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 20, "bold"),
            padx=25
        )
        header_title.pack(side=tk.LEFT, pady=15)

        header_subtitle = tk.Label(
            header_frame,
            text="Tribological Data & Profilometry Analysis Hub",
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_SIDEBAR,
            font=("Segoe UI", 11, "italic"),
            padx=10
        )
        header_subtitle.pack(side=tk.LEFT, pady=20)

        # 2. Main Container
        main_container = tk.Frame(self.root, bg=COLOR_BG, padx=30, pady=25)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Info Box / Header Banner
        info_card = tk.Frame(
            main_container,
            bg=COLOR_CARD,
            bd=1,
            relief=tk.SOLID,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=20,
            pady=15
        )
        info_card.pack(fill=tk.X, pady=(0, 20))

        info_title = tk.Label(
            info_card,
            text="ℹ️ Supported Testing Devices & File Formats",
            fg=COLOR_ACCENT_PURPLE,
            bg=COLOR_CARD,
            font=("Segoe UI", 13, "bold"),
            anchor="w"
        )
        info_title.pack(fill=tk.X, pady=(0, 6))

        info_desc = tk.Label(
            info_card,
            text=(
                "This software suite is specially developed for processing, plotting, and reporting raw data "
                "obtained from laboratory wear and friction tests:\n"
                "• CSM Instruments Tribometer (.txt output files containing friction coefficient vs. sliding distance)\n"
                "• Mitutoyo Contact Profilometer (.xls output files containing contact roughness profiles and wear tracks)"
            ),
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            font=("Segoe UI", 10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=880
        )
        info_desc.pack(fill=tk.X)

        # 3. Two Main Tool Launch Cards Container
        cards_frame = tk.Frame(main_container, bg=COLOR_BG)
        cards_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Grid configuration for equal 2 columns
        cards_frame.columnconfigure(0, weight=1, uniform="card_col")
        cards_frame.columnconfigure(1, weight=1, uniform="card_col")
        cards_frame.rowconfigure(0, weight=1)

        # --- Card 1: CSM Tribometer ---
        card1 = tk.Frame(
            cards_frame,
            bg=COLOR_CARD,
            bd=1,
            relief=tk.SOLID,
            highlightbackground=COLOR_ACCENT_BLUE,
            highlightthickness=1,
            padx=20,
            pady=20
        )
        card1.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        c1_icon = tk.Label(card1, text="📈", fg=COLOR_ACCENT_BLUE, bg=COLOR_CARD, font=("Segoe UI", 32))
        c1_icon.pack(anchor="w")

        c1_title = tk.Label(
            card1,
            text="CSM Tribometer Analyser",
            fg=COLOR_ACCENT_BLUE,
            bg=COLOR_CARD,
            font=("Segoe UI", 15, "bold"),
            anchor="w"
        )
        c1_title.pack(fill=tk.X, pady=(8, 4))

        c1_subtitle = tk.Label(
            card1,
            text="Friction Coefficient (µ) & Distance Analysis",
            fg=COLOR_WARN,
            bg=COLOR_CARD,
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        c1_subtitle.pack(fill=tk.X, pady=(0, 10))

        c1_desc = tk.Label(
            card1,
            text=(
                "• Auto-parses CSM Tribometer .txt output files.\n"
                "• Offers Moving Average smoothing for noise reduction.\n"
                "• Multi-file overlay mode to compare multiple tests on a single chart.\n"
                "• Generates average friction coefficient bar charts and exports 300 DPI figures."
            ),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=380
        )
        c1_desc.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        btn_c1 = tk.Button(
            card1,
            text="📊 Launch CSM Tribometer Analyser",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT_BLUE,
            fg=COLOR_BG,
            activebackground=COLOR_HIGHLIGHT,
            activeforeground=COLOR_BG,
            bd=0,
            pady=12,
            cursor="hand2",
            command=self.launch_tribo_plotter
        )
        btn_c1.pack(fill=tk.X, side=tk.BOTTOM)

        # --- Card 2: Mitutoyo Contact Profilometer ---
        card2 = tk.Frame(
            cards_frame,
            bg=COLOR_CARD,
            bd=1,
            relief=tk.SOLID,
            highlightbackground=COLOR_ACCENT_GREEN,
            highlightthickness=1,
            padx=20,
            pady=20
        )
        card2.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        c2_icon = tk.Label(card2, text="📏", fg=COLOR_ACCENT_GREEN, bg=COLOR_CARD, font=("Segoe UI", 32))
        c2_icon.pack(anchor="w")

        c2_title = tk.Label(
            card2,
            text="Mitutoyo Contact Profilometer",
            fg=COLOR_ACCENT_GREEN,
            bg=COLOR_CARD,
            font=("Segoe UI", 15, "bold"),
            anchor="w"
        )
        c2_title.pack(fill=tk.X, pady=(8, 4))

        c2_subtitle = tk.Label(
            card2,
            text="Roughness, Wear Track & Volume Analysis",
            fg=COLOR_WARN,
            bg=COLOR_CARD,
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        c2_subtitle.pack(fill=tk.X, pady=(0, 10))

        c2_desc = tk.Label(
            card2,
            text=(
                "• Reads Mitutoyo .xls profile data (Raw / Filtered).\n"
                "• Automatic wear-track detection and baseline correction.\n"
                "• Interactive calculation of cross-sectional area, wear volume, and specific wear rate [mm³/(N·m)].\n"
                "• Batch scan & automated reporting mode across all samples."
            ),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=380
        )
        c2_desc.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        btn_c2 = tk.Button(
            card2,
            text="📏 Launch Mitutoyo Profilometer Analyser",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT_GREEN,
            fg=COLOR_BG,
            activebackground=COLOR_HIGHLIGHT,
            activeforeground=COLOR_BG,
            bd=0,
            pady=12,
            cursor="hand2",
            command=self.launch_roughness_analyser
        )
        btn_c2.pack(fill=tk.X, side=tk.BOTTOM)

        # 4. Custom Device Integration / Development Request Banner
        custom_card = tk.Frame(
            main_container,
            bg=COLOR_CARD,
            bd=1,
            relief=tk.SOLID,
            highlightbackground=COLOR_ACCENT_PURPLE,
            highlightthickness=1,
            padx=20,
            pady=15
        )
        custom_card.pack(fill=tk.X, side=tk.BOTTOM)

        cc_left = tk.Frame(custom_card, bg=COLOR_CARD)
        cc_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cc_title = tk.Label(
            cc_left,
            text="🛠️ Custom Device Integration & Development Request",
            fg=COLOR_ACCENT_PURPLE,
            bg=COLOR_CARD,
            font=("Segoe UI", 12, "bold"),
            anchor="w"
        )
        cc_title.pack(fill=tk.X)

        cc_desc = tk.Label(
            cc_left,
            text=(
                "Do you use a different tribometer or profilometer brand (Anton Paar, Rtec, Bruker, Taylor Hobson, etc.) "
                "and need a custom module developed to parse and analyze your specific file format?"
            ),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
            font=("Segoe UI", 10),
            anchor="w",
            justify=tk.LEFT,
            wraplength=580
        )
        cc_desc.pack(fill=tk.X, pady=(2, 0))

        btn_contact = tk.Button(
            custom_card,
            text="✉️ Send Email to Developer\n(gmehmetay@gmail.com)",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            activeforeground=COLOR_ACCENT_PURPLE,
            bd=1,
            relief=tk.SOLID,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self.open_contact_dialog
        )
        btn_contact.pack(side=tk.RIGHT, padx=(15, 0))

    def launch_tribo_plotter(self):
        """Launches tribo_plotter.py as a separate subprocess."""
        script_path = os.path.join(self.script_dir, "tribo_plotter.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path], cwd=self.script_dir)
        else:
            messagebox.showerror("Error", f"Script not found:\n{script_path}")

    def launch_roughness_analyser(self):
        """Launches roughness_analyser.py as a separate subprocess."""
        script_path = os.path.join(self.script_dir, "roughness_analyser.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path], cwd=self.script_dir)
        else:
            messagebox.showerror("Error", f"Script not found:\n{script_path}")

    def open_contact_dialog(self):
        """Opens default mail client and shows a custom contact dialog with email details."""
        subject = "Tribo-Analist Custom Device Integration Request"
        body = (
            "Hello Mehmet,\n\n"
            "We would like to request custom integration/support for our testing device in Tribo-Analist.\n\n"
            "Device Brand/Model:\n"
            "Output File Format (.txt / .csv / .xls etc.):\n\n"
            "Best regards."
        )
        mailto_url = f"mailto:{CONTACT_EMAIL}?subject={webbrowser.quote(subject)}&body={webbrowser.quote(body)}"
        
        try:
            webbrowser.open(mailto_url)
        except Exception:
            pass

        # Also open modal dialog for direct visibility
        dlg = tk.Toplevel(self.root)
        dlg.title("Custom Device Integration & Development Request")
        dlg.geometry("540x360")
        dlg.resizable(False, False)
        dlg.configure(bg=COLOR_CARD)
        dlg.transient(self.root)
        dlg.grab_set()

        # Center dialog
        dlg.update_idletasks()
        dx = self.root.winfo_x() + (self.root.winfo_width() // 2) - (270)
        dy = self.root.winfo_y() + (self.root.winfo_height() // 2) - (180)
        dlg.geometry(f"+{dx}+{dy}")

        dlg_title = tk.Label(
            dlg,
            text="📧 Contact & Development Request",
            fg=COLOR_ACCENT_PURPLE,
            bg=COLOR_CARD,
            font=("Segoe UI", 14, "bold"),
            pady=15
        )
        dlg_title.pack(fill=tk.X)

        dlg_msg = tk.Label(
            dlg,
            text=(
                "Your default email client has been launched.\n\n"
                "To request custom file parsers, automated reporting, or interface development for your "
                "tribometer or profilometer devices, you can reach out directly via the email address below:"
            ),
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            font=("Segoe UI", 10),
            wraplength=480,
            justify=tk.CENTER
        )
        dlg_msg.pack(pady=(0, 15), padx=20)

        email_frame = tk.Frame(dlg, bg=COLOR_BG, bd=1, relief=tk.SOLID, padx=15, pady=10)
        email_frame.pack(fill=tk.X, padx=40, pady=(0, 20))

        email_lbl = tk.Label(
            email_frame,
            text=CONTACT_EMAIL,
            fg=COLOR_ACCENT_BLUE,
            bg=COLOR_BG,
            font=("Segoe UI", 13, "bold")
        )
        email_lbl.pack(side=tk.LEFT)

        def copy_email():
            self.root.clipboard_clear()
            self.root.clipboard_append(CONTACT_EMAIL)
            copy_btn.config(text="✅ Copied!", fg=COLOR_ACCENT_GREEN)
            self.root.after(2000, lambda: copy_btn.config(text="📋 Copy", fg=COLOR_TEXT))

        copy_btn = tk.Button(
            email_frame,
            text="📋 Copy",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=copy_email
        )
        copy_btn.pack(side=tk.RIGHT)

        close_btn = tk.Button(
            dlg,
            text="Close",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_HOVER,
            bd=0,
            padx=25,
            pady=8,
            cursor="hand2",
            command=dlg.destroy
        )
        close_btn.pack(side=tk.BOTTOM, pady=(0, 20))


if __name__ == "__main__":
    root = tk.Tk()
    app = TriboAnalistLauncher(root)
    root.mainloop()
