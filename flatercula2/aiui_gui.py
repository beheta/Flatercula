#!/usr/bin/env python3
"""
Flatercula GUI – English‑only
"""

import json
import tkinter as tk
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import psutil
import sounddevice as sd
import soundfile as sf
import whisper
import tkinter as tk
import threading
from tkinter import END, Button, Entry, Label, ttk, scrolledtext, messagebox

# Import the agent module
import aiui_agent as aiui_module

# ──────────────────────────────────────────
# GUI class
# ─────────────────────────────────────────────
class AIUIApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Flatercula AI‑UI Agent")
        self.root.geometry("700x650")

        # ── 1. UI ------------------------------------------------------
        self.create_widgets()

        # ── 2. Init ----------------------------------------------------
        self.initialize_system()

        # ── 3. Load Ollama models -------------------------------------
        self.ollama_models = []
        self.load_ollama_models()

        # ── 4. Whisper -----------------------------------------------
        self.whisper_model = None
        self.load_whisper_model()

        # ── 5. Audio -----------------------------------------------
        self.recording = False
        self.audio_data = []
        self.sample_rate = 16000

        self.append_output("AIUI Agent started.\n")
        self.append_output(f"Using model: {aiui_module.MODEL_NAME}\n\n")

    # ── 6. UI helpers -----------------------------------------------
    def create_widgets(self):
        # Output pane
        self.output_text = scrolledtext.ScrolledText(
            self.root, wrap="word", font=("Arial", 10)
        )
        self.output_text.pack(fill="both", expand=True, padx=10, pady=10)

        input_frame = tk.Frame(self.root)
        input_frame.pack(side="bottom", fill="x", pady=10)

        # Model selector
        Label(input_frame, text="Ollama Model:").pack(side="left", padx=5)
        self.model_var = tk.StringVar(value=aiui_module.MODEL_NAME)
        self.model_combo = ttk.Combobox(
            input_frame,
            textvariable=self.model_var,
            values=[],
            state="readonly",
            width=15,
        )
        self.model_combo.pack(side="left", padx=5)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_change)

        Button(
            input_frame,
            text="Refresh Models",
            command=self.refresh_ollama_models,
        ).pack(side="left", padx=5)

        Button(
            input_frame,
            text="Restart Backend",
            command=self.restart_backend,
        ).pack(side="left", padx=5)

        # Mic button
        self.mic_btn = Button(
            input_frame,
            text=" Start Mic",
            command=self.toggle_recording,
            fg="black",
        )
        self.mic_btn.pack(side="left", padx=5)

        # Input entry
        self.input_entry = Entry(input_frame, font=("Arial", 12))
        self.input_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=5)
        self.input_entry.bind("<Return>", self.on_execute)

        # Execute / Clear / Export
        Button(
            input_frame,
            text="Execute",
            command=self.on_execute,
        ).pack(side="right", padx=5)
        Button(
            input_frame,
            text="Clear",
            command=self.clear_output,
        ).pack(side="right", padx=5)
        Button(
            input_frame,
            text="Export Log",
            command=self.export_log,
        ).pack(side="right", padx=5)

    # ── 7. System init -----------------------------------------------
    def initialize_system(self):
        self.append_output("Initializing system...\n")
        self.start_ollama_server()
        self.start_ollama_model()
        self.append_output("System ready.\n")

    # ── 8. Ollama server ------------------------------------------------
    def start_ollama_server(self):
        self.append_output("Starting Ollama server...\n")
        subprocess.run(
            ["pkill", "-f", "ollama serve"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.ollama_process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)  # give it a moment
        self.append_output("Ollama server running.\n")

    # ── 9. Ollama model ------------------------------------------------
    def start_ollama_model(self):
        self.append_output(f"Running model {aiui_module.MODEL_NAME} in background...\n")
        if hasattr(self, "ollama_run_process") and self.ollama_run_process.poll() is None:
            self.ollama_run_process.terminate()
            self.ollama_run_process.wait()
        self.ollama_run_process = subprocess.Popen(
            ["ollama", "run", aiui_module.MODEL_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.append_output(f"Model {aiui_module.MODEL_NAME} started.\n")

    # ──10. Load models list -------------------------------------------
    def load_ollama_models(self):
        try:
            res = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().split("\n")[1:]  # header drop
                self.ollama_models = [line.split()[0] for line in lines if line]
            else:
                self.ollama_models = ["qwen2.5:7b", "mistral:latest", "llama3:8b"]
        except Exception:
            self.ollama_models = ["qwen2.5:7b", "mistral:latest", "llama3:8b"]

        self.model_combo["values"] = self.ollama_models
        self.model_combo.set(aiui_module.MODEL_NAME)

    # ──11. Whisper init -----------------------------------------------
    def load_whisper_model(self):
        try:
            cpu = psutil.cpu_count(logical=False)
            mem_gb = psutil.virtual_memory().total / (1024**3)
            if cpu < 4 or mem_gb < 4:
                sel = "tiny"
                self.append_output("Using Whisper Tiny model.\n")
            elif cpu < 8 or mem_gb < 8:
                sel = "base"
                self.append_output("Using Whisper Base model.\n")
            else:
                sel = "small"
                self.append_output("Using Whisper Small model.\n")
            self.whisper_model = whisper.load_model(sel)
            self.append_output(f"Whisper {sel} loaded.\n")
        except Exception as exc:
            messagebox.showwarning("Whisper", f"Could not load Whisper: {exc}")
            self.whisper_model = None

    # ──12. Mic toggle -----------------------------------------------
    def toggle_recording(self):
        if not self.whisper_model:
            messagebox.showwarning("Whisper", "Whisper model not loaded.")
            return
        if not self.recording:
            self.recording = True
            self.mic_btn.config(text=" Stop Mic", fg="red")
            self.append_output("Recording started...\n")
            self.record_audio()
        else:
            self.recording = False
            self.mic_btn.config(text=" Start Mic", fg="black")
            self.append_output("Recording stopped.\n")

    # ──13. Record audio thread ---------------------------------------
    def record_audio(self):
        def _record():
            try:
                self.audio_data = []
                with sd.InputStream(
                    samplerate=self.sample_rate, channels=1, dtype="float32"
                ) as stream:
                    while self.recording:
                        data, _ = stream.read(1024)
                        self.audio_data.append(data.flatten())
            except Exception as exc:
                self.append_output(f"Recording error: {exc}\n")

        threading.Thread(target=_record, daemon=True).start()

    # ──14. Transcribe -----------------------------------------------
    def transcribe_audio(self):
        if not self.audio_data:
            return ""
        audio = np.concatenate(self.audio_data)
        try:
            res = self.whisper_model.transcribe(audio, language="en")
            return res["text"]
        except Exception as exc:
            self.append_output(f"Transcription error: {exc}\n")
            return ""

    # ──15. Execute -----------------------------------------------
    def on_execute(self, event=None):
        text = self.input_entry.get().strip()
        if not text:
            if self.recording:
                self.toggle_recording()
            text = self.transcribe_audio()
            if not text:
                return
            self.input_entry.delete(0, END)
            self.input_entry.insert(0, text)
        self.input_entry.delete(0, END)
        self.append_output(f"> {text}\n")
        threading.Thread
                # Start the background thread that actually runs the agent
        threading.Thread(
            target=self.run_aiui, args=(text,), daemon=True
        ).start()

    # ── 16. Run the agent in a background thread ─────────────────────────────
    def run_aiui(self, user_input: str):
        try:
            explanation = aiui_module.aiui_agent(user_input)
            # Tkinter calls must happen in the main thread
            self.root.after(0, self.update_output, explanation)
        except Exception as exc:
            self.append_output(f"Agent error: {exc}\n")

    # ── 17. Update output widget ─────────────────────────────────────────────
    def update_output(self, txt: str):
        self.append_output(txt + "\n\n")

    # ── 18. Clear output ───────────────────────────────────────────────────────
    def clear_output(self):
        if self.output_text:
            self.output_text.delete(1.0, END)

    # ── 19. Append text to output (thread‑safe) ────────────────────────────────
    def append_output(self, txt: str):
        if self.output_text:
            self.output_text.insert(END, txt)
            self.output_text.see(END)
        else:
            # fallback to console
            print(txt, end="")

    # ── 20. Export log file ───────────────────────────────────────────────────
    def export_log(self):
        from tkinter import filedialog
        import shutil

        log_file = Path.home() / ".local/share/flatercula/agent.log"
        if not log_file.exists():
            messagebox.showinfo("Log", "No log file found.")
            return

        dest = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if dest:
            try:
                shutil.copy(log_file, dest)
                messagebox.showinfo("Export", f"Log exported to {dest}")
            except Exception as exc:
                messagebox.showerror("Error", f"Could not export log: {exc}")

    # ── 21. Model change handler ───────────────────────────────────────────────
    def on_model_change(self, event):
        new_model = self.model_var.get()
        if new_model != aiui_module.MODEL_NAME:
            aiui_module.MODEL_NAME = new_model
            self.append_output(f"Switched to model {new_model}\n")
            self.start_ollama_model()

    # ── 22. Refresh model list ───────────────────────────────────────────────
    def refresh_ollama_models(self):
        self.append_output("Refreshing model list...\n")
        self.load_ollama_models()
        self.append_output("Model list updated.\n")

    # ── 23. Restart backend ───────────────────────────────────────────────────
    def restart_backend(self):
        def _restart():
            try:
                self.append_output("Restarting backend...\n")
                if hasattr(self, "ollama_process") and self.ollama_process.poll() is None:
                    self.ollama_process.terminate()
                    self.ollama_process.wait()
                if hasattr(self, "ollama_run_process") and self.ollama_run_process.poll() is None:
                    self.ollama_run_process.terminate()
                    self.ollama_run_process.wait()

                self.start_ollama_server()
                self.start_ollama_model()
                self.load_ollama_models()
                self.append_output("Backend restarted.\n")
            except Exception as exc:
                self.append_output(f"Backend restart error: {exc}\n")

        threading.Thread(target=_restart, daemon=True).start()


# ───────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk(className="Flatercula")
    root.title("Flatercula")
    img = tk.PhotoImage(file="logo.png")
    root.iconphoto(False, img)
    app = AIUIApp(root)
    root.mainloop()

    
