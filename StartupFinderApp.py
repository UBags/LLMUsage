import os
import json
import tkinter as tk
from tkinter import scrolledtext, PanedWindow, Toplevel, messagebox
from dotenv import load_dotenv
import threading
import re

# Import the functions from your other project files
from GetSeedStartupsv1 import get_top_startups
from InvestmentParametersGenerator import get_investment_parameters
from PopulateData import populate_data


class StartupFinderApp:
    def __init__(self, aRoot):
        self.root = aRoot
        self.root.title("Tool for First-Cut Startup Analysis")

        # Set default model
        self.gemini_model = "gemini-2.0-flash"

        # --- Window Sizing ---
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        app_width = int(screen_width * 0.9)
        app_height = int(screen_height * 0.8)
        self.root.geometry(f"{app_width}x{app_height}")

        # --- Input Frame ---
        input_frame = tk.Frame(aRoot, padx=10, pady=10)
        input_frame.pack(fill="x", padx=10, pady=5)
        input_frame.columnconfigure(1, weight=1) # Make the entry column expandable

        # --- API Key with Placeholder ---
        tk.Label(input_frame, text="Gemini API Key:").grid(row=0, column=0, sticky="w", pady=2)
        api_key_frame = tk.Frame(input_frame)
        api_key_frame.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.api_key_entry = tk.Entry(api_key_frame, width=80)
        self.api_key_entry.pack(side="left", fill="x", expand=True)
        self.api_key_help_button = tk.Button(api_key_frame, text="?", command=self.show_api_key_help, width=3)
        self.api_key_help_button.pack(side="left", padx=(5, 0))

        self.api_key_placeholder = "Get Gemini API Key and populate it here"
        self.add_api_key_placeholder()
        self.api_key_entry.bind('<FocusIn>', self.on_api_key_focus_in)
        self.api_key_entry.bind('<FocusOut>', self.on_api_key_focus_out)

        # --- Gemini Model Selection ---
        tk.Label(input_frame, text="Use Gemini Model:").grid(row=1, column=0, sticky="w", pady=2)
        model_frame = tk.Frame(input_frame)
        model_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        self.gemini_model_var = tk.StringVar(value="Flash")
        model_options = ["Flash", "Pro"]
        model_dropdown = tk.OptionMenu(model_frame, self.gemini_model_var, *model_options, command=self.update_gemini_model)
        model_dropdown.pack(side="left")
        self.model_help_button = tk.Button(model_frame, text="?", command=self.show_model_help, width=3)
        self.model_help_button.pack(side="left", padx=(5, 0))

        # --- Sector (formerly Area) ---
        tk.Label(input_frame, text="Sector:").grid(row=2, column=0, sticky="w", pady=2)
        sector_frame = tk.Frame(input_frame)
        sector_frame.grid(row=2, column=1, columnspan=2, sticky="ew")
        self.sector_entry = tk.Entry(sector_frame)
        self.sector_entry.pack(side="left", fill="x", expand=True)
        self.sector_entry.insert(0, "Supply-Chain Finance")
        self.sector_help_button = tk.Button(sector_frame, text="?", command=self.show_sector_help, width=3)
        self.sector_help_button.pack(side="left", padx=(5,0))

        # --- Geography ---
        tk.Label(input_frame, text="Geography:").grid(row=3, column=0, sticky="w", pady=2)
        self.geo_entry = tk.Entry(input_frame)
        self.geo_entry.grid(row=3, column=1, columnspan=2, pady=2, sticky="ew")
        self.geo_entry.insert(0, "India")

        # --- Spinboxes with descriptive text ---
        tk.Label(input_frame, text="Number of Startups:").grid(row=4, column=0, sticky="w", pady=2)
        startup_spin_frame = tk.Frame(input_frame)
        startup_spin_frame.grid(row=4, column=1, columnspan=2, sticky="w")
        self.n_startups_var = tk.IntVar(value=50)
        self.n_startups_spinbox = tk.Spinbox(startup_spin_frame, from_=3, to=200, textvariable=self.n_startups_var, width=8)
        self.n_startups_spinbox.pack(side="left")
        tk.Label(startup_spin_frame, text="Specify how many startups should be shortlisted. The number can be between 3 and 200").pack(side="left", padx=(5,0))

        tk.Label(input_frame, text="Number of Parameters:").grid(row=5, column=0, sticky="w", pady=2)
        param_spin_frame = tk.Frame(input_frame)
        param_spin_frame.grid(row=5, column=1, columnspan=2, sticky="w")
        self.n_params_var = tk.IntVar(value=40)
        self.n_params_spinbox = tk.Spinbox(param_spin_frame, from_=15, to=75, textvariable=self.n_params_var, width=8)
        self.n_params_spinbox.pack(side="left")
        tk.Label(param_spin_frame, text="Specify how many parameters do you want data on. The number can be between 15 and 75").pack(side="left", padx=(5,0))


        # --- Button Frame ---
        button_frame = tk.Frame(aRoot)
        button_frame.pack(pady=10)
        self.search_button = tk.Button(button_frame, text="Generate Full Report", command=self.start_search_thread, width=30)
        self.search_button.pack(side="left")
        tk.Label(button_frame, text="Created by CosTheta Technologies Pvt Ltd for Merisis Advisors Pvt Ltd", fg="gray").pack(side="left", padx=(10,0))


        # --- Output Paned Window ---
        paned_window = PanedWindow(aRoot, orient="vertical", sashrelief="raised", sashwidth=5)
        paned_window.pack(fill="both", expand=True, padx=10, pady=5)

        # Top pane for startups
        startup_frame = tk.Frame(paned_window)
        tk.Label(startup_frame, text="Startup Results:").pack(anchor="w")
        self.startup_results_text = scrolledtext.ScrolledText(startup_frame, wrap=tk.WORD, height=10)
        self.startup_results_text.pack(fill="both", expand=True)
        paned_window.add(startup_frame)

        # Middle pane for parameters
        param_frame = tk.Frame(paned_window)
        tk.Label(param_frame, text="Investment Parameters:").pack(anchor="w")
        self.parameters_results_text = scrolledtext.ScrolledText(param_frame, wrap=tk.WORD, height=10)
        self.parameters_results_text.pack(fill="both", expand=True)
        paned_window.add(param_frame)

        # Bottom pane for logging
        log_frame = tk.Frame(paned_window)
        tk.Label(log_frame, text="Process Log:").pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, bg="black", fg="lightgray", height=10)
        self.log_text.pack(fill="both", expand=True)
        paned_window.add(log_frame)

        self.load_api_key_from_env()

    def add_api_key_placeholder(self, event=None):
        """Adds placeholder text to the API key entry."""
        if not self.api_key_entry.get():
            self.api_key_entry.insert(0, self.api_key_placeholder)
            self.api_key_entry.config(fg='grey', show='')

    def on_api_key_focus_in(self, event=None):
        """Removes placeholder on focus if it exists."""
        if self.api_key_entry.get() == self.api_key_placeholder:
            self.api_key_entry.delete(0, 'end')
            self.api_key_entry.config(fg='black', show='*')

    def on_api_key_focus_out(self, event=None):
        """Adds placeholder back if entry is empty."""
        self.add_api_key_placeholder()

    def update_gemini_model(self, selection):
        """Updates the instance variable when the dropdown selection changes."""
        if selection == "Pro":
            self.gemini_model = "gemini-2.5-pro"
        else:  # Default to Flash
            self.gemini_model = "gemini-2.0-flash"

    def _create_help_dialog(self, title, help_text):
        dialog = Toplevel(self.root)
        dialog.title(title)

        screen_width = self.root.winfo_screenwidth()
        dialog_width = int(screen_width * 0.6)

        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog_width // 2)
        y = self.root.winfo_y() + 100
        dialog.geometry(f'{dialog_width}x400+{x}+{y}')
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        text_area = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, padx=10, pady=10,
                                              borderwidth=0, highlightthickness=0)
        text_area.pack(expand=True, fill="both")

        text_area.tag_configure("bold", font=("sans-serif", 10, "bold"))

        cleaned_text = "\n".join([line.strip() for line in help_text.strip().split("\n")])
        parts = re.split(r'(\*\*.*?\*\*)', cleaned_text)

        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                text_area.insert(tk.END, part[2:-2], "bold")
            else:
                text_area.insert(tk.END, part)

        text_area.config(state="disabled")

        ok_button = tk.Button(dialog, text="OK", command=dialog.destroy, width=10)
        ok_button.pack(pady=10)

        self.root.wait_window(dialog)

    def show_api_key_help(self):
        help_text = """
        **How to Get a Gemini API Key**

        1. Visit the **Google AI Studio** website.
           (You can copy this link and open it in your browser)
           **Link:** https://aistudio.google.com/

        2. **Sign In** with your Google account.

        3. Look for a button that says **"Get API Key"**. It is usually on the top left or bottom left of the page.

        4. Click on it and follow the on-screen instructions to create a new API key.

        5. **Copy** the generated API key and paste it into a .txt file. Save this file in a well-known location, so that you can fetch this key easily for subsequent runs later.

        6. **Copy** the generated API key and paste it into the text box in this application.

        **Important:** Treat your API key like a password. Do not share it publicly.
        """
        self._create_help_dialog("Gemini API Key Help", help_text)

    def show_sector_help(self):
        help_text = """
        **Enter a specific business sector to get the most relevant results.**

        Here are some examples:

        - **Supply Chain Finance**
        - **Cybersecurity**
        - **HealthTech** (or specific sub-sectors like "Telemedicine")
        - **EdTech** (or "Online Learning Platforms")
        - **FinTech** (or "Digital Lending")
        - **AgriTech**
        - **SaaS for Enterprise**
        - **E-commerce Logistics**
        - **Electric Vehicles (EV) Infrastructure**
        """
        self._create_help_dialog("Sector Examples", help_text)

    def show_model_help(self):
        """Displays a modal dialog with information about the Gemini models."""
        help_text = """
        **About Gemini Models**

        **Flash (gemini-2.0-flash):**
        - A fast and efficient model, great for quick tasks.
        - **It is free to use.**

        **Pro (gemini-2.5-pro):**
        - A more powerful and robust model that can provide higher quality, more detailed responses.
        - This model is more suitable for complex research tasks.
        - **Using the Pro model requires a paid Google Cloud account with billing enabled.**
        """
        self._create_help_dialog("Gemini Model Information", help_text)

    def load_api_key_from_env(self):
        load_dotenv()
        api_key = os.getenv("GEMini_API_KEY")  # Corrected variable name
        if api_key:
            if self.api_key_entry.get() == self.api_key_placeholder:
                self.api_key_entry.delete(0, 'end')
            self.api_key_entry.insert(0, api_key)
            self.api_key_entry.config(fg='black', show='*')

    def start_search_thread(self):
        self.search_button.config(state="disabled")
        self.startup_results_text.delete(1.0, tk.END)
        self.parameters_results_text.delete(1.0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.startup_results_text.insert(tk.END, "Finding startups... Please wait.")

        thread = threading.Thread(target=self.run_search)
        thread.daemon = True
        thread.start()

    def run_search(self):
        api_key_raw = self.api_key_entry.get().strip()
        api_key = "" if api_key_raw == self.api_key_placeholder else api_key_raw

        area = self.sector_entry.get().strip()
        geo = self.geo_entry.get().strip()

        # --- Enforce min/max for spinboxes ---
        try:
            num_startups_raw = self.n_startups_var.get()
            num_startups = max(3, min(num_startups_raw, 200))
            if num_startups != num_startups_raw:
                self.n_startups_var.set(num_startups)

            num_params_raw = self.n_params_var.get()
            num_params = max(15, min(num_params_raw, 75))
            if num_params != num_params_raw:
                self.n_params_var.set(num_params)
        except tk.TclError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for startups and parameters.")
            self.search_button.config(state="normal")
            return

        # Step 1: Get Startups
        startup_success, startup_result = get_top_startups(
            api_key, area, geo, n_startups=num_startups, model_name=self.gemini_model
        )
        self.root.after(0, self.update_startup_results, startup_success, startup_result)
        if not startup_success:
            self.root.after(0, lambda: self.search_button.config(state="normal"))
            return

        # Step 2: Get Parameters
        self.root.after(0, lambda: self.parameters_results_text.insert(tk.END, "Requesting parameters..."))
        param_success, param_result = get_investment_parameters(
            api_key, startup_result, area, geo, nParameters=num_params, model_name=self.gemini_model
        )
        self.root.after(0, self.update_parameter_results, param_success, param_result)
        if not param_success:
            self.root.after(0, lambda: self.search_button.config(state="normal"))
            return

        # Step 3: Populate Data
        self.root.after(0, lambda: self.log_text.insert(tk.END, "--- Starting Final Report Generation ---\n"))
        populate_success, populate_result = populate_data(
            api_key, startup_result, param_result, area, geo,
            model_name=self.gemini_model, log_widget=self.log_text
        )
        self.root.after(0, self.update_log_results, populate_success, populate_result)

    def update_startup_results(self, success, result):
        self.startup_results_text.delete(1.0, tk.END)
        if success:
            self.startup_results_text.insert(tk.END, "--- Top Startups Found ---\n\n")
            self.startup_results_text.insert(tk.END, json.dumps(result, indent=2))
        else:
            self.startup_results_text.insert(tk.END, f"An error occurred:\n\n{result}")
            messagebox.showerror("Startup Search Error", result)

    def update_parameter_results(self, success, result):
        self.parameters_results_text.delete(1.0, tk.END)
        if success:
            self.parameters_results_text.insert(tk.END, "--- Investment Parameters Generated ---\n\n")
            self.parameters_results_text.insert(tk.END, json.dumps(result, indent=2))
        else:
            self.parameters_results_text.insert(tk.END, f"An error occurred:\n\n{result}")
            messagebox.showerror("Parameter Generation Error", result)

    def update_log_results(self, success, result):
        """Finalizes the log and re-enables the button."""
        if success:
            self.log_text.insert(tk.END, "\n--- All tasks completed successfully. ---\n")
            messagebox.showinfo("Success",
                                "The final HTML report has been generated in the 'Output Data' directory. You can open the report using either a browser, or Microsoft Excel.")
        else:
            self.log_text.insert(tk.END, f"\n--- An error occurred during the final step ---\n{result}")
            messagebox.showerror("Report Generation Error", result)

        self.log_text.see(tk.END)  # Scroll to the end
        self.search_button.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = StartupFinderApp(root)
    root.mainloop()

