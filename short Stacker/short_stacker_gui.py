import os
import glob
import shutil
import subprocess
import threading
import time
import json
import cv2

from PIL import Image, ImageTk
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CropToolWindow(ctk.CTkToplevel):

    def __init__(self, master, image_path, callback):
        super().__init__(master)
        self.title("Bildausschnitt (Crop) festlegen")
        self.geometry("1200x800")
        self.transient(master)
        self.grab_set()

        self.callback = callback
        self.crop_coords = None

        try:
            self.original_image = Image.open(image_path)
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Bild nicht laden:\n{str(e)}")
            self.destroy()
            return

        self.orig_w, self.orig_h = self.original_image.size

        max_disp_w, max_disp_h = 900, 700
        scale = min(max_disp_w / self.orig_w, max_disp_h / self.orig_h)
        
        self.disp_w = int(self.orig_w * scale)
        self.disp_h = int(self.orig_h * scale)
        self.scale_factor = 1 / scale 

        self.disp_image = self.original_image.resize((self.disp_w, self.disp_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.disp_image)

        self.canvas = tk.Canvas(self, width=self.disp_w, height=self.disp_h, cursor="cross", bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(pady=10)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.rect_id = None
        self.start_x = None
        self.start_y = None

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(btn_frame, text="Tipp: Ziehe ein Rechteck über den Bereich, der behalten werden soll.").pack(side="left")
        
        self.btn_apply = ctk.CTkButton(btn_frame, text="Ausschnitt übernehmen", fg_color="#2b7b4a", hover_color="#1e5c36", state="disabled", command=self.apply_crop)
        self.btn_apply.pack(side="right")

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        end_x, end_y = event.x, event.y
        
        x1 = int(min(self.start_x, end_x) * self.scale_factor)
        y1 = int(min(self.start_y, end_y) * self.scale_factor)
        x2 = int(max(self.start_x, end_x) * self.scale_factor)
        y2 = int(max(self.start_y, end_y) * self.scale_factor)
        
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(self.orig_w, x2), min(self.orig_h, y2)

        self.crop_coords = (x1, y1, x2, y2)
        self.btn_apply.configure(state="normal") 

    def apply_crop(self):
        if self.crop_coords:
            self.callback(self.crop_coords) 
            self.destroy()


class TrackerToolWindow(ctk.CTkToplevel):
    def __init__(self, master, first_image_path, last_image_path, callback):
        super().__init__(master)
        self.title("Asteroid markieren (Start & Ende)")
        self.geometry("1200x850") 
        self.transient(master)
        self.grab_set()

        self.callback = callback
        self.first_image_path = first_image_path
        self.last_image_path = last_image_path
        
        self.start_coords = None
        self.end_coords = None
        self.click_state = "START"
        self.current_preview = "START"

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", pady=10)

        self.lbl_info = ctk.CTkLabel(top_frame, text="Schritt 1: Klicke auf den Asteroiden im ERSTEN Bild.", font=ctk.CTkFont(weight="bold", size=16), text_color="#00ff00")
        self.lbl_info.pack(side="left", padx=20)

        self.btn_blink = ctk.CTkButton(top_frame, text="👁️ Blinken (Start/Ende vergleichen)", fg_color="#b87333", hover_color="#8c5827", command=self.toggle_blink)
        self.btn_blink.pack(side="right", padx=20)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10)

        self.canvas = tk.Canvas(main_frame, bg="#1a1a1a", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side="left", pady=5)
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<Motion>", self.update_loupe)

        right_frame = ctk.CTkFrame(main_frame, width=280)
        right_frame.pack(side="right", fill="y", padx=10)

        ctk.CTkLabel(right_frame, text="300% Pixel-Lupe", font=ctk.CTkFont(weight="bold", size=14)).pack(pady=(10, 0))
        ctk.CTkLabel(right_frame, text="Zeigt reine Rohpixel an", font=ctk.CTkFont(size=11), text_color="#888888").pack(pady=(0, 10))
        
        self.loupe_canvas = tk.Canvas(right_frame, width=240, height=240, bg="#000", highlightthickness=1, highlightbackground="#555")
        self.loupe_canvas.pack(pady=5)
        ctk.CTkLabel(right_frame, text="Fahre mit der Maus über das Bild,\num den Asteroiden genau zu treffen.", text_color="#aaaaaa").pack(pady=5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        self.btn_reset = ctk.CTkButton(btn_frame, text="Zurücksetzen", command=self.reset)
        self.btn_reset.pack(side="left")

        self.btn_apply = ctk.CTkButton(btn_frame, text="Markierung übernehmen", fg_color="#2b7b4a", hover_color="#1e5c36", state="disabled", command=self.apply)
        self.btn_apply.pack(side="right")

        self.load_image(self.first_image_path)

    def load_image(self, path):
        self.original_image = Image.open(path).convert("RGB")
        self.orig_w, self.orig_h = self.original_image.size

        max_disp_w, max_disp_h = 880, 700
        scale = min(max_disp_w / self.orig_w, max_disp_h / self.orig_h)
        self.disp_w = int(self.orig_w * scale)
        self.disp_h = int(self.orig_h * scale)
        self.scale_factor = 1 / scale

        self.disp_image = self.original_image.resize((self.disp_w, self.disp_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.disp_image)

        self.canvas.config(width=self.disp_w, height=self.disp_h)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        r = 8
        if self.start_coords:
            sx = self.start_coords[0] / self.scale_factor
            sy = self.start_coords[1] / self.scale_factor
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, outline="#00ff00", width=2)
        if self.end_coords:
            ex = self.end_coords[0] / self.scale_factor
            ey = self.end_coords[1] / self.scale_factor
            self.canvas.create_oval(ex-r, ey-r, ex+r, ey+r, outline="#ff0000", width=2)

    def toggle_blink(self):
        if self.current_preview == "START":
            self.load_image(self.last_image_path)
            self.current_preview = "END"
            if self.click_state == "START":
                self.lbl_info.configure(text="VORSCHAU: LETZTES Bild. (Klicke auf Blinken, um zurückzugehen)", text_color="#aaaaaa")
        else:
            self.load_image(self.first_image_path)
            self.current_preview = "START"
            if self.click_state == "START":
                self.lbl_info.configure(text="Schritt 1: Klicke auf den Asteroiden im ERSTEN Bild.", text_color="#00ff00")

    def update_loupe(self, event):
        if not hasattr(self, 'original_image'): return

        rx = int(event.x * self.scale_factor)
        ry = int(event.y * self.scale_factor)
        
        box_size = 80 
        left = rx - box_size // 2
        upper = ry - box_size // 2
        right = rx + box_size // 2
        lower = ry + box_size // 2
        
        if left < 0: left = 0; right = box_size
        if upper < 0: upper = 0; lower = box_size
        if right > self.orig_w: right = self.orig_w; left = self.orig_w - box_size
        if lower > self.orig_h: lower = self.orig_h; upper = self.orig_h - box_size
        
        crop = self.original_image.crop((left, upper, right, lower))
        zoomed = crop.resize((240, 240), Image.Resampling.NEAREST) 
        
        self.loupe_tk_image = ImageTk.PhotoImage(zoomed)
        self.loupe_canvas.delete("all")
        self.loupe_canvas.create_image(0, 0, anchor="nw", image=self.loupe_tk_image)
        
        self.loupe_canvas.create_line(120, 100, 120, 140, fill="#ffff00", width=1)
        self.loupe_canvas.create_line(100, 120, 140, 120, fill="#ffff00", width=1)

    def on_click(self, event):
        if self.click_state == "START" and self.current_preview == "END":
            self.load_image(self.first_image_path)
            self.current_preview = "START"

        real_x = int(event.x * self.scale_factor)
        real_y = int(event.y * self.scale_factor)
        r = 8 

        if self.click_state == "START":
            self.start_coords = (real_x, real_y)
            self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, outline="#00ff00", width=2)
            self.click_state = "END"
            
            self.lbl_info.configure(text="Lade letztes Bild...", text_color="#ffffff")
            self.after(200, lambda: self.load_image(self.last_image_path))
            self.after(200, lambda: self.set_end_state())

        elif self.click_state == "END":
            self.end_coords = (real_x, real_y)
            self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, outline="#ff0000", width=2)
            self.click_state = "DONE"
            
            self.lbl_info.configure(text="Fertig! Klicke auf 'Blinken' zum Prüfen oder auf 'Übernehmen'.", text_color="#ffffff")
            self.btn_apply.configure(state="normal")
            
    def set_end_state(self):
        self.current_preview = "END"
        self.lbl_info.configure(text="Schritt 2: Klicke auf den Asteroiden im LETZTEN Bild.", text_color="#ff0000")

    def reset(self):
        self.click_state = "START"
        self.current_preview = "START"
        self.start_coords = None
        self.end_coords = None
        self.btn_apply.configure(state="disabled")
        self.lbl_info.configure(text="Schritt 1: Klicke auf den Asteroiden im ERSTEN Bild.", text_color="#00ff00")
        self.load_image(self.first_image_path)

    def apply(self):
        self.callback(self.start_coords, self.end_coords)
        self.destroy()


class ShortStackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Astro Short-Stacker (Siril & SetiAstro Automation) v1.7.5")
        self.geometry("1400x680")
        try:
            if os.path.exists("shortstacker.ico"): 
                self.wm_iconbitmap("shortstacker.ico")
        except Exception: 
            pass
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1) 

        self.settings_file = "shortstacker_settings.json"
        
        self.input_folder = ctk.StringVar()
        self.output_folder = ctk.StringVar()
        self.siril_path = ctk.StringVar()
        self.ffmpeg_path = ctk.StringVar()
        self.setiastro_path = ctk.StringVar()
        
        self.batch_size = ctk.StringVar(value="6")
        self.stop_requested = False 
        
        self.use_denoise = ctk.BooleanVar(value=False)
        self.use_denoise_lite = ctk.BooleanVar(value=True)
        self.use_rmgreen = ctk.BooleanVar(value=True) # Standardmäßig an
        
        # NEU: Asteroiden-Markierung Einstellungen
        self.marker_style = ctk.StringVar(value="Pfeil")
        self.marker_size = ctk.IntVar(value=40)
        
        self.load_settings()

        self._build_gui()
        
        self.crop_coordinates = None
        self.asteroid_coordinates = None
        self.last_custom_folder = ""

    def load_settings(self):
        default_siril = r"C:\Program Files\Siril\bin\siril-cli.exe"
        default_ffmpeg = "ffmpeg"
        default_seti = r"C:\Program Files\SetiAstro\SetiAstroSuitePro.exe"
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    self.input_folder.set(data.get("input_folder", ""))
                    self.output_folder.set(data.get("output_folder", ""))
                    self.siril_path.set(data.get("siril_path", default_siril))
                    self.ffmpeg_path.set(data.get("ffmpeg_path", default_ffmpeg))
                    self.setiastro_path.set(data.get("setiastro_path", default_seti))
            except Exception:
                pass
        else:
            self.siril_path.set(default_siril)
            self.ffmpeg_path.set(default_ffmpeg)
            self.setiastro_path.set(default_seti)

    def save_settings(self):
        data = {
            "input_folder": self.input_folder.get(),
            "output_folder": self.output_folder.get(),
            "siril_path": self.siril_path.get(),
            "ffmpeg_path": self.ffmpeg_path.get(),
            "setiastro_path": self.setiastro_path.get()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
            
    def _build_gui(self):
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="ew")
        ctk.CTkLabel(top_frame, text="Astro Short-Stacker v1.7.5", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top_frame, text="⚙️ Einstellungen", width=120, fg_color="#454545", hover_color="#2b2b2b", command=self.open_settings).pack(side="right")

        frame_paths = ctk.CTkFrame(self)
        frame_paths.grid(row=1, column=0, padx=20, pady=(15, 10), sticky="ew")
        
        self.lbl_input = ctk.CTkLabel(frame_paths, text="1. Input-Ordner:", width=220, anchor="w")
        self.lbl_input.grid(row=0, column=0, padx=10, pady=(10, 5))
        ctk.CTkEntry(frame_paths, textvariable=self.input_folder, state="readonly", width=400).grid(row=0, column=1, padx=10, pady=(10, 5), sticky="ew")
        self.btn_input = ctk.CTkButton(frame_paths, text="Ordner wählen", command=self.select_input, width=120)
        self.btn_input.grid(row=0, column=2, padx=10, pady=(10, 5))
        
        self.lbl_output = ctk.CTkLabel(frame_paths, text="2. Output-Ordner:", width=220, anchor="w")
        self.lbl_output.grid(row=1, column=0, padx=10, pady=(0, 10))
        ctk.CTkEntry(frame_paths, textvariable=self.output_folder, state="readonly", width=400).grid(row=1, column=1, padx=10, pady=(0, 10), sticky="ew")
        self.btn_output = ctk.CTkButton(frame_paths, text="Ordner wählen", command=self.select_output, width=120)
        self.btn_output.grid(row=1, column=2, padx=10, pady=(0, 10))
        frame_paths.grid_columnconfigure(1, weight=1)

        self.stack_mode = ctk.StringVar(value="")
        self.export_format = ctk.StringVar(value="JPEG (Schnell & Klein)")
        self.video_source = ctk.StringVar(value="A: FITS aus Input-Ordner ➡️ Video in Output")

        self.tabview = ctk.CTkTabview(self, height=240, command=self.update_path_states)
        self.tabview.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        tab_stacking = self.tabview.add("Schritt 1: FITS Aufbereitung")
        tab_video = self.tabview.add("Schritt 2: Video Builder & Effekte")
        tab_tools = self.tabview.add("Extras: Tools & Konverter")

        self._build_tab_stacking(tab_stacking)
        self._build_tab_video(tab_video)
        self._build_tab_tools(tab_tools)

        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="ew")
        
        self.btn_stop = ctk.CTkButton(progress_frame, text="⏹ Stop / Abbruch", fg_color="#9e3e3e", hover_color="#7a2f2f", font=ctk.CTkFont(weight="bold"), state="disabled", command=self.request_stop, width=150)
        self.btn_stop.pack(side="right", padx=(10, 0))
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(side="left", fill="x", expand=True, pady=5)
        self.progress_bar.set(0.0) 

        ctk.CTkLabel(self, text="Log-Ausgabe:", anchor="w", text_color="gray").grid(row=6, column=0, padx=20, pady=(5, 0), sticky="ew")
        self.log_box = ctk.CTkTextbox(self)
        self.log_box.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_box.insert("0.0", "Bereit. v1.7.0\n")
        
        self.update_path_states()
        
    def update_path_states(self, *args):
        current_tab = self.tabview.get()

        if "FITS Aufbereitung" in current_tab or "Tools" in current_tab:
            self._set_path_state("input", True, "1. Input (Originale 10s FITS):")
            self._set_path_state("output", True, "2. Output (Fertige Dateien):")
            
        elif "Video Builder" in current_tab:
            src = self.video_source.get()
            if "Input-Ordner" in src:
                self._set_path_state("input", True, "1. Input (Hier liegen die FITS):")
                self._set_path_state("output", True, "2. Output (Hierhin wird das Video gespeichert):")
            elif "Output-Ordner" in src:
                self._set_path_state("input", False, "1. Input (Wird hier ignoriert)")
                self._set_path_state("output", True, "2. Output (Quelle für FITS UND Ziel für Video):")
            else:
                self._set_path_state("input", False, "1. Input (Wird hier ignoriert)")
                self._set_path_state("output", False, "2. Output (Dialog fragt gleich nach dem Ordner)")

    def _set_path_state(self, path_type, is_active, custom_text=""):
        state = "normal" if is_active else "disabled"
        text_color = ["gray10", "#DCE4EE"] if is_active else "gray50"

        if path_type == "input":
            self.btn_input.configure(state=state)
            self.lbl_input.configure(text_color=text_color)
            if custom_text: self.lbl_input.configure(text=custom_text)
        elif path_type == "output":
            self.btn_output.configure(state=state)
            self.lbl_output.configure(text_color=text_color)
            if custom_text: self.lbl_output.configure(text=custom_text)

    # --- TAB 1: STACKING & REGISTRIERUNG ---
    def _build_tab_stacking(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1)
        
        frame_stack = ctk.CTkFrame(parent)
        frame_stack.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(frame_stack, text="Option A: Short-Stacking", font=ctk.CTkFont(weight="bold")).pack(pady=(10,0))
        ctk.CTkLabel(frame_stack, text="Reduziert Rauschen durch Batch-Stacking.\nIdeal für Deep-Sky Timelapse & Photometrie.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(5,10))
        
        b_frame = ctk.CTkFrame(frame_stack, fg_color="transparent")
        b_frame.pack(pady=5)
        ctk.CTkLabel(b_frame, text="Bilder pro Stack:").pack(side="left", padx=5)
        ctk.CTkEntry(b_frame, textvariable=self.batch_size, width=50, justify="center").pack(side="left")
        
        btn_frame1 = ctk.CTkFrame(frame_stack, fg_color="transparent")
        btn_frame1.pack(pady=10)
        
        # Zeile 1: Die normalen Buttons
        self.btn_stack_color = ctk.CTkButton(btn_frame1, text="▶ Farbe (Debayer)", width=130, fg_color="#2b7b4a", hover_color="#1e5c36", command=lambda: self._trigger_stacking("Farbe (Debayer) für Timelapse"))
        self.btn_stack_color.grid(row=0, column=0, padx=5, pady=5)
        
        self.btn_stack_green = ctk.CTkButton(btn_frame1, text="▶ Nur Grünkanal", width=130, fg_color="#2b7b4a", hover_color="#1e5c36", command=lambda: self._trigger_stacking("Nur Grünkanal"))
        self.btn_stack_green.grid(row=0, column=1, padx=5, pady=5)

        # Zeile 2: Der neue "Super-Button" (Zusammengeführter Prozess)
        self.btn_stack_green_reg = ctk.CTkButton(btn_frame1, text="▶ Grünkanal Stacking + Globale Registrierung", width=270, fg_color="#2b6b8a", hover_color="#1a4c66", command=lambda: self._trigger_stacking("Grünkanal + Global Reg"))
        self.btn_stack_green_reg.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        frame_reg = ctk.CTkFrame(parent)
        frame_reg.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(frame_reg, text="Option B: Globale Registrierung", font=ctk.CTkFont(weight="bold")).pack(pady=(10,0))
        ctk.CTkLabel(frame_reg, text="Richtet alle Bilder an einem Referenzbild aus.\nZwingend erforderlich für Asteroiden-Timelapses!", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(5,15))
        
        # NEU: Zwei separate Buttons für Farbe (Video) und Mono (Wissenschaft)
        self.btn_stack_reg_color = ctk.CTkButton(frame_reg, text="▶ Registrieren (FARBE für Timelapse)", fg_color="#b87333", hover_color="#8c5827", command=lambda: self._trigger_stacking("➡️ Nur registrieren (Farbe)"))
        self.btn_stack_reg_color.pack(pady=(0, 10))
        
        self.btn_stack_reg = ctk.CTkButton(frame_reg, text="▶ Registrieren (MONO für Photometrie)", fg_color="#2b6b8a", hover_color="#1a4c66", command=lambda: self._trigger_stacking("➡️ Nur registrieren (Photometrie)"))
        self.btn_stack_reg.pack(pady=5)

    # --- TAB 2: VIDEO BUILDER & EFFEKTE ---
    def _build_tab_video(self, parent):
        parent.grid_columnconfigure((0, 1, 2), weight=1)
        
        frame_src = ctk.CTkFrame(parent)
        frame_src.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(frame_src, text="1. Quelle & Format", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        ctk.CTkOptionMenu(frame_src, variable=self.video_source, values=[
            "A: FITS aus Input-Ordner ➡️ Video in Output", 
            "B: FITS aus Output-Ordner ➡️ Video in Output", 
            "C: Beliebiger Ordner mit Bildern (JPG/PNG/TIF)"
        ], width=260, command=self.update_path_states).pack(pady=(5, 10))
        
        ctk.CTkOptionMenu(frame_src, variable=self.export_format, values=[
            "JPEG (Schnell & Klein)", 
            "PNG (Verlustfrei & Groß)",
            "TIFF (16-bit unkomprimiert)"
        ], width=180).pack(pady=5)
        
        # NEU: Checkbox für rmgreen
        self.chk_rmgreen = ctk.CTkCheckBox(frame_src, text="Grünstich entfernen (nur bei Farbe!)", variable=self.use_rmgreen)
        self.chk_rmgreen.pack(pady=(15, 5))

        frame_fx = ctk.CTkFrame(parent)
        frame_fx.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(frame_fx, text="2. Effekte & Tools", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        btn_fx = ctk.CTkFrame(frame_fx, fg_color="transparent")
        btn_fx.pack(pady=5)
        ctk.CTkButton(btn_fx, text="✂️ Bildausschnitt", width=100, command=self.open_crop_tool).pack(side="left", padx=2)
        ctk.CTkButton(btn_fx, text="☄️ Asteroid markieren", width=120, command=self.open_tracker_tool).pack(side="left", padx=2)
        
        # NEU: Markierungs-Einstellungen (Dropdown + Slider)
        marker_frame = ctk.CTkFrame(frame_fx, fg_color="transparent")
        marker_frame.pack(pady=(0, 10))
        ctk.CTkOptionMenu(marker_frame, variable=self.marker_style, values=["Pfeil", "Kreis", "Fadenkreuz"], width=100).pack(side="left", padx=2)
        ctk.CTkSlider(marker_frame, variable=self.marker_size, from_=15, to=150, width=120).pack(side="left", padx=2)
        
        self.chk_denoise = ctk.CTkCheckBox(frame_fx, text="KI Denoise (SetiAstro)", variable=self.use_denoise, command=self._toggle_denoise_lite)
        self.chk_denoise.pack(pady=(5, 2))
        self.chk_lite = ctk.CTkCheckBox(frame_fx, text="Denoise Lite Mode", variable=self.use_denoise_lite, state="disabled")
        self.chk_lite.pack(pady=2)

        frame_render = ctk.CTkFrame(parent)
        frame_render.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(frame_render, text="3. Fertigstellen", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 15))
        ctk.CTkLabel(frame_render, text="Wendet ggf. Siril-Stretch an,\n entrauscht und rendert das MP4.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(0, 15))
        
        self.btn_timelapse = ctk.CTkButton(frame_render, text="🎞️ Timelapse rendern", fg_color="#b87333", hover_color="#8c5827", font=ctk.CTkFont(weight="bold"), command=self.start_timelapse_thread)
        self.btn_timelapse.pack(pady=5)

    # --- TAB 3: TOOLS ---
    def _build_tab_tools(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        
        frame_conv = ctk.CTkFrame(parent)
        frame_conv.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(frame_conv, text="FITS direkt zu JPG/PNG/TIF konvertieren", font=ctk.CTkFont(weight="bold")).pack(pady=(10,0))
        ctk.CTkLabel(frame_conv, text="Kein Stacking. Wandelt alle Input-FITS direkt in das in Tab 2 gewählte Format um.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(5,15))
        
        self.btn_tool_conv = ctk.CTkButton(frame_conv, text="▶ Direkt-Konvertierung starten", fg_color="#2b6b8a", hover_color="#1a4c66", command=lambda: self._trigger_stacking("➡️ Nur Konvertieren (Input direkt zu JPG/PNG)"))
        self.btn_tool_conv.pack(pady=15)


    # =================================================================
    # FITS ON-THE-FLY PREVIEW GENERATOR
    # =================================================================
    def _find_fits_files(self, directory):
        """Hilfsmethode, um zuverlässig alle FITS (auch großgeschrieben) zu finden."""
        if not directory or not os.path.exists(directory):
            return []
        patterns = ['*.fit', '*.fits', '*.FIT', '*.FITS']
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(directory, p)))
        return sorted(list(set(files))) # Gibt eine eindeutige, sortierte Liste zurück

    def _generate_fits_preview(self, fits_path):
        """Erzeugt über Siril blitzschnell ein gestretchtes JPG aus einer FITS-Datei zur Vorschau."""
        temp_dir = os.path.join(os.path.dirname(fits_path), "siril_temp_preview")
        os.makedirs(temp_dir, exist_ok=True)
        
        out_jpg_base = os.path.join(temp_dir, "preview")
        out_jpg_full = out_jpg_base + ".jpg"
        
        # Altes Bild löschen, falls vorhanden
        if os.path.exists(out_jpg_full):
            try:
                os.remove(out_jpg_full)
            except Exception:
                pass
            
        # Pfad in Siril-freundliches Format umwandeln
        fits_dir = os.path.dirname(fits_path).replace("\\", "/")
        fits_name = os.path.basename(fits_path)
        out_jpg_base_siril = out_jpg_base.replace("\\", "/")
            
        script_path = os.path.join(temp_dir, "preview.ssf")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("requires 1.2.0\n")
            f.write(f'cd "{fits_dir}"\n')       # 1. Sicher in den Ordner navigieren
            f.write(f'load "{fits_name}"\n')    # 2. Nur den reinen Dateinamen laden
            f.write("autostretch\n")            # 3. Nur stretchen, keine Farbbefehle (vermeidet Abstürze)
            f.write(f'savejpg "{out_jpg_base_siril}"\n')
            f.write("close\n")

        # Siril starten und Konsolenausgabe abfangen (capture_output=True)
        try:
            process = subprocess.run(
                [self.siril_path.get(), "-s", script_path], 
                capture_output=True, text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        except Exception as e:
            self.log(f"Siril konnte nicht gestartet werden: {str(e)}")
            return None

        # Dem Dateisystem kurz Zeit geben
        time.sleep(0.1)

        if os.path.exists(out_jpg_full):
            return out_jpg_full
        else:
            # WENN ES FEHLSCHLÄGT: Siril Fehlermeldung ins Log schreiben!
            self.log("\n--- SIRIL KONNTE VORSCHAU NICHT ERSTELLEN ---")
            self.log("Siril Logausgabe:")
            if process.stdout: self.log(process.stdout.strip())
            if process.stderr: self.log(process.stderr.strip())
            self.log("---------------------------------------------")
            return None

    # =================================================================
    # CROP & TRACKING LOGIK (VEREINFACHT & FITS-KOMPATIBEL)
    # =================================================================
    def open_crop_tool(self):
        source_choice = self.video_source.get()
        is_fits = "FITS" in source_choice
        
        if is_fits:
            target_dir = self.input_folder.get() if "Input" in source_choice else self.output_folder.get()
            if not target_dir:
                messagebox.showerror("Fehler", "Bitte den entsprechenden Ordner (Input/Output) auswählen!")
                return
                
            # NEU: Nutzt die sichere Suchfunktion
            fits_files = self._find_fits_files(target_dir)
            
            if not fits_files:
                messagebox.showerror("Fehler", f"Keine FITS Dateien im Ordner gefunden:\n{target_dir}")
                return
                
            self.log("Erstelle Vorschau-Bild aus FITS... Bitte kurz warten.")
            self.update_idletasks() # UI aktualisieren
            
            preview_img = self._generate_fits_preview(fits_files[0])
            if preview_img:
                CropToolWindow(self, preview_img, self.save_crop_coords)
            else:
                messagebox.showerror("Fehler", "Konnte Vorschau nicht generieren. Ist der Siril-Pfad korrekt?")
        else:
            frames_dir = filedialog.askdirectory(title="Ordner mit Bildern (JPG/PNG) wählen")
            if not frames_dir: return  
            
            valid_exts = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff')
            images = []
            for ext_pattern in valid_exts:
                images.extend(glob.glob(os.path.join(frames_dir, ext_pattern)))
                images.extend(glob.glob(os.path.join(frames_dir, ext_pattern.upper())))

            images = sorted(list(set(images)))
            if not images:
                messagebox.showerror("Fehler", f"Keine Bilder für die Vorschau im Ordner gefunden:\n{frames_dir}")
                return

            self.last_custom_folder = frames_dir  
            CropToolWindow(self, images[0], self.save_crop_coords)

    def save_crop_coords(self, coords):
        self.crop_coordinates = coords
        x1, y1, x2, y2 = coords
        self.log(f"-> Crop-Rahmen gesetzt: X({x1} bis {x2}), Y({y1} bis {y2})")        

    def open_tracker_tool(self):
        source_choice = self.video_source.get()
        is_fits = "FITS" in source_choice
        
        if is_fits:
            target_dir = self.input_folder.get() if "Input" in source_choice else self.output_folder.get()
            if not target_dir:
                messagebox.showerror("Fehler", "Bitte den entsprechenden Ordner (Input/Output) auswählen!")
                return
                
            # NEU: Nutzt die sichere Suchfunktion
            fits_files = self._find_fits_files(target_dir)
            
            if not fits_files:
                messagebox.showerror("Fehler", f"Keine FITS Dateien im Ordner gefunden:\n{target_dir}")
                return
                
            fits_files.sort(key=self._get_fits_timestamp)
            
            self.log("Erstelle Start- und End-Vorschau aus FITS... Bitte kurz warten.")
            self.update_idletasks()
            
            first_preview = self._generate_fits_preview(fits_files[0])
            last_preview = self._generate_fits_preview(fits_files[-1])
            
            if first_preview and last_preview:
                TrackerToolWindow(self, first_preview, last_preview, self.save_tracker_coords)
            else:
                messagebox.showerror("Fehler", "Konnte Vorschau nicht generieren.")
        else:
            frames_dir = filedialog.askdirectory(title="Ordner mit Bildern (JPG/PNG) wählen")
            if not frames_dir: return
            
            valid_exts = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff')
            images = []
            for ext_pattern in valid_exts:
                images.extend(glob.glob(os.path.join(frames_dir, ext_pattern)))
                images.extend(glob.glob(os.path.join(frames_dir, ext_pattern.upper())))

            images = sorted(list(set(images)))
            if not images:
                messagebox.showerror("Fehler", "Keine Bilder gefunden.")
                return

            self.last_custom_folder = frames_dir
            TrackerToolWindow(self, images[0], images[-1], self.save_tracker_coords)

    def save_tracker_coords(self, start_coords, end_coords):
        self.asteroid_coordinates = (start_coords, end_coords)
        self.log(f"-> Asteroid markiert: Start {start_coords} -> Ende {end_coords}")


    # --- BRÜCKEN-METHODEN ---
    def _trigger_stacking(self, mode_string):
        self.stack_mode.set(mode_string)
        self.start_stacking_thread()

    def _toggle_denoise_lite(self):
        if self.use_denoise.get():
            self.chk_lite.configure(state="normal")
        else:
            self.chk_lite.configure(state="disabled")

    # --- EINSTELLUNGEN FENSTER ---
    def open_settings(self):
        if hasattr(self, "settings_window") and self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return
            
        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("Pfade konfigurieren")
        self.settings_window.geometry("600x320")
        self.settings_window.transient(self) 
        self.settings_window.grab_set() 
        
        ctk.CTkLabel(self.settings_window, text="Siril CLI Pfad (siril-cli.exe):", anchor="w").pack(padx=20, pady=(20,5), fill="x")
        f1 = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        f1.pack(padx=20, fill="x")
        ctk.CTkEntry(f1, textvariable=self.siril_path).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(f1, text="Suchen", width=80, command=self._search_siril).pack(side="left", padx=(10,0))
        
        ctk.CTkLabel(self.settings_window, text="FFmpeg Pfad (ffmpeg.exe oder 'ffmpeg'):", anchor="w").pack(padx=20, pady=(10,5), fill="x")
        f2 = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        f2.pack(padx=20, fill="x")
        ctk.CTkEntry(f2, textvariable=self.ffmpeg_path).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(f2, text="Suchen", width=80, command=self._search_ffmpeg).pack(side="left", padx=(10,0))

        ctk.CTkLabel(self.settings_window, text="SetiAstro Suite Pro Pfad:", anchor="w").pack(padx=20, pady=(10,5), fill="x")
        f3 = ctk.CTkFrame(self.settings_window, fg_color="transparent")
        f3.pack(padx=20, fill="x")
        ctk.CTkEntry(f3, textvariable=self.setiastro_path).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(f3, text="Suchen", width=80, command=self._search_setiastro).pack(side="left", padx=(10,0))
        
        ctk.CTkButton(self.settings_window, text="Speichern & Schließen", fg_color="#2b7b4a", hover_color="#1e5c36", command=self._close_settings).pack(pady=30)
        
    def _search_siril(self):
        filepath = filedialog.askopenfilename(title="siril-cli.exe suchen", filetypes=[("Executable", "*.exe")])
        if filepath: self.siril_path.set(filepath)
        
    def _search_ffmpeg(self):
        filepath = filedialog.askopenfilename(title="ffmpeg.exe suchen", filetypes=[("Executable", "*.exe")])
        if filepath: self.ffmpeg_path.set(filepath)

    def _search_setiastro(self):
        filepath = filedialog.askopenfilename(title="SetiAstroSuitePro.exe suchen", filetypes=[("Executable", "*.exe")])
        if filepath: self.setiastro_path.set(filepath)
        
    def _close_settings(self):
        self.save_settings()
        self.settings_window.destroy()

    def select_input(self):
        folder = filedialog.askdirectory(title="Input Ordner wählen")
        if folder: 
            self.input_folder.set(folder)
            self.save_settings()

    def select_output(self):
        folder = filedialog.askdirectory(title="Output Ordner wählen")
        if folder: 
            self.output_folder.set(folder)
            self.save_settings()

    def log(self, message):
        self.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def update_progress(self, value):
        self.progress_bar.set(value)

    def request_stop(self):
        self.stop_requested = True
        self.btn_stop.configure(state="disabled", text="Stoppe nach aktuellem Batch...")
        self.log("\n[!] Abbruch angefordert... Bitte warten, bis Siril den aktuellen Batch beendet hat.")

    def _get_fits_timestamp(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                header_data = f.read(2880 * 4).decode('ascii', errors='ignore')
                for i in range(0, len(header_data), 80):
                    card = header_data[i:i+80]
                    if card.startswith('DATE-OBS'):
                        return card.split('=')[1].split('/')[0].strip(" '")
        except Exception:
            pass
        return os.path.getmtime(filepath)
    
    # --- STACKING LOGIK ---
    def start_stacking_thread(self):
        in_dir = self.input_folder.get()
        out_dir = self.output_folder.get()
        siril_exe = self.siril_path.get()
        
        if not in_dir or not out_dir:
            messagebox.showerror("Fehler", "Bitte Input- und Output-Ordner auswählen!")
            return
            
        try:
            b_size = int(self.batch_size.get())
            if b_size < 1:
                messagebox.showerror("Fehler", "Die Batch-Größe muss mindestens 1 sein!")
                return
        except ValueError:
            messagebox.showerror("Fehler", "Bitte eine gültige Zahl für die Batch-Größe eingeben!")
            return

        if hasattr(self, 'btn_stack_color'): self.btn_stack_color.configure(state="disabled")
        if hasattr(self, 'btn_stack_green'): self.btn_stack_green.configure(state="disabled")
        if hasattr(self, 'btn_stack_reg'): self.btn_stack_reg.configure(state="disabled")
        if hasattr(self, 'btn_tool_conv'): self.btn_tool_conv.configure(state="disabled")
        
        self.btn_stop.configure(state="normal", text="⏹ Stop")
        self.stop_requested = False
        self.progress_bar.set(0.0) 
        
        self.log_box.delete("0.0", "end")
        
        modus_text = self.stack_mode.get()
        self.log(f"=== Prozess gestartet | Modus: {modus_text} ===")

        t = threading.Thread(target=self.run_stacker_process, args=(in_dir, out_dir, siril_exe, b_size, modus_text))
        t.daemon = True
        t.start()

    def run_stacker_process(self, in_dir, out_dir, siril_exe, batch_size, modus_text):
        try:
            dateien = self._find_fits_files(in_dir)
            
            dateien.sort(key=self._get_fits_timestamp)
            
            total_files = len(dateien)
            if total_files == 0:
                self.log("FEHLER: Keine .fit oder .fits Dateien im Input-Ordner gefunden!")
                return

            self.log(f"[{total_files}] Dateien gefunden. Paketgröße: {batch_size} Bilder...\n")

            temp_dir = os.path.join(in_dir, "siril_temp_workdir")
            script_path = os.path.join(in_dir, "temp_script.ssf")

            is_direct_export = "Nur Konvertieren" in modus_text
            is_photometry_reg = "Nur registrieren" in modus_text 
            is_color_reg = "Farbe" in modus_text # <--- NEU: Prüft ob der Farb-Button geklickt wurde
            
            export_ext = ""
            export_cmd = ""
            frames_dir_siril = ""
            global_frame_idx = 1 

            if is_direct_export:
                format_choice = self.export_format.get()
                if "PNG" in format_choice:
                    export_ext = "png"
                    export_cmd = "savepng"
                elif "TIFF" in format_choice:
                    export_ext = "tif"
                    export_cmd = "savetif"
                else:
                    export_ext = "jpg"
                    export_cmd = "savejpg"

                frames_dir = os.path.join(out_dir, "timelapse_unstacked_frames")
                if not os.path.exists(frames_dir):
                    os.makedirs(frames_dir)
                frames_dir_siril = frames_dir.replace('\\', '/')
            
            if is_photometry_reg:
                self.log("\nStarte globale Registrierung für Photometrie...")
                self.log("Batch-Größe wird ignoriert. Verarbeite alle Bilder in einem Durchgang.")

                temp_reg_dir = os.path.join(out_dir, "temp_photometry_reg")
                if os.path.exists(temp_reg_dir):
                    shutil.rmtree(temp_reg_dir, ignore_errors=True)
                os.makedirs(temp_reg_dir)

                self.log("Kopiere Dateien in den Arbeitsordner...")
                for idx, datei in enumerate(dateien):
                    if self.stop_requested: return
                    shutil.copy(datei, os.path.join(temp_reg_dir, f"light_{idx+1:05d}.fit"))
                    if idx % 10 == 0: 
                        self.after(0, self.update_progress, (idx / total_files) * 0.2)

                temp_dir_siril = temp_reg_dir.replace('\\', '/')
                script_path = os.path.join(temp_reg_dir, "reg_script.ssf")

                siril_script_content = f"requires 1.2.0\nsetext fit\ncd \"{temp_dir_siril}\"\n"
                
                # NEU: Wenn Farbe gewählt wurde, wird hier debayered!
                if is_color_reg:
                    siril_script_content += "convert light -debayer\n"
                else:
                    siril_script_content += "convert light\n"
                    
                siril_script_content += "setref light 1\n"
                siril_script_content += "register light\n"
                siril_script_content += "close\n"

                with open(script_path, "w") as f:
                    f.write(siril_script_content)

                self.log("Siril registriert global (ohne Farb/Grünkanal Extraktion)... Bitte warten.")
                self.after(0, self.update_progress, 0.5) 
                try:
                    process = subprocess.run([siril_exe, "-s", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                except FileNotFoundError:
                    self.log("FEHLER: siril-cli.exe nicht gefunden.")
                    return

                if process.returncode == 0:
                    r_files = sorted(glob.glob(os.path.join(temp_reg_dir, "r_light_*.fit")))
                    for idx, r_file in enumerate(r_files):
                        orig_name = os.path.basename(dateien[idx])
                        shutil.move(r_file, os.path.join(out_dir, f"r_{orig_name}"))
                        
                    self.after(0, self.update_progress, 1.0)
                    self.log("\n===========================================")
                    self.log(f"FERTIG! {len(r_files)} Bilder wurden global vor-registriert.")
                    self.log("===========================================")
                else:
                    self.log("\nFEHLER bei der Registrierung:")
                    error_output = process.stdout.strip() if process.stdout else ""
                    for line in error_output.split('\n')[-10:]:
                        if line: self.log(f"    Siril: {line}")

                shutil.rmtree(temp_reg_dir, ignore_errors=True)
                self.after(0, self._reset_buttons)
                return

            batch_nummer = 1
            erfolgreich = 0

            for i in range(0, total_files, batch_size):
                if self.stop_requested:
                    self.log("\n!!! VORGANG VOM BENUTZER ABGEBROCHEN !!!")
                    break

                batch = dateien[i : i + batch_size]
                if len(batch) < 1:
                    break

                aktueller_fortschritt = i / total_files
                self.after(0, self.update_progress, aktueller_fortschritt)
                self.log(f"Bearbeite Batch {batch_nummer} (Bilder {i+1} bis {i+len(batch)})...")

                if os.path.exists(temp_dir):
                    for _ in range(10): 
                        try:
                            shutil.rmtree(temp_dir)
                            break 
                        except PermissionError:
                            time.sleep(0.5) 

                os.makedirs(temp_dir)

                for idx, datei in enumerate(batch):
                    safe_name = f"img_{idx+1:04d}.fit" 
                    shutil.copy(datei, os.path.join(temp_dir, safe_name))

                out_filename = f"shortstack_{batch_nummer:04d}.fit"
                out_filepath = os.path.join(out_dir, out_filename)
                temp_dir_siril = temp_dir.replace('\\', '/')

                siril_script_content = f"requires 1.2.0\nsetext fit\ncd \"{temp_dir_siril}\"\n"
                
                if is_direct_export:
                    siril_script_content += "convert light -debayer\n"
                    for b_idx in range(len(batch)):
                        siril_script_content += f'load "light_{b_idx+1:05d}.fit"\n'
                        siril_script_content += "rmgreen\nautostretch\nmirrorx\n"
                        siril_script_content += f'{export_cmd} "{frames_dir_siril}/frame_{global_frame_idx:04d}"\n'
                        global_frame_idx += 1
                elif len(batch) == 1:
                    if "Grün" in modus_text:
                        siril_script_content += "convert light\nseqextract_Green light\nload Green_light_00001.fit\nsave result\n"
                    elif "Farbe" in modus_text:
                        siril_script_content += "convert light -debayer\nload light_00001.fit\nsave result\n"
                    else: 
                        siril_script_content += "convert light\nload light_00001.fit\nsave result\n"
                else:
                    if "Grün" in modus_text:
                        siril_script_content += "convert light\n"
                        siril_script_content += "seqextract_Green light\n"
                        siril_script_content += "setfindstar -sigma=0.5 -roundness=0.0\n" 
                        siril_script_content += "register Green_light\n"
                        siril_script_content += "stack r_Green_light sum -nonorm -out=result\n"
                    elif "Farbe" in modus_text:
                        siril_script_content += "convert light -debayer\nregister light\nstack r_light sum -nonorm -out=result\n"
                    else: 
                        siril_script_content += "convert light\nregister light\nstack r_light sum -nonorm -out=result\n"
                
                siril_script_content += "close\n"

                with open(script_path, "w") as f:
                    f.write(siril_script_content)

                try:
                    process = subprocess.run([siril_exe, "-s", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                except FileNotFoundError:
                    self.log("FEHLER: siril-cli.exe nicht gefunden. Bitte Pfad in den Einstellungen prüfen!")
                    break
                
                expected_result_path = os.path.join(temp_dir, "result.fit")
                
                if process.returncode == 0:
                    if is_direct_export:
                        self.log(f" -> Batch {batch_nummer}: {len(batch)} Bilder als {export_ext.upper()} exportiert.")
                        erfolgreich += len(batch)
                    else:
                        if os.path.exists(expected_result_path):
                            moved = False
                            for _ in range(10):
                                try:
                                    shutil.move(expected_result_path, out_filepath)
                                    moved = True
                                    break
                                except PermissionError:
                                    time.sleep(0.5)
                            if moved:
                                self.log(f" -> Gespeichert: {out_filename}")
                                erfolgreich += 1
                            else:
                                self.log(f" -> FEHLER bei Batch {batch_nummer}! Datei war dauerhaft blockiert.")
                        else:
                            self.log(f" -> FEHLER bei Batch {batch_nummer}! Stack wurde nicht erstellt.")
                else:
                    self.log(f" -> FEHLER bei Batch {batch_nummer}! Prozess fehlgeschlagen.")
                    error_output = process.stdout.strip() if process.stdout else ""
                    for line in error_output.split('\n')[-10:]:
                        if line: self.log(f"    Siril: {line}")

                batch_nummer += 1

            # --- AUFRÄUMEN NACH DEM STACKING ---
            if os.path.exists(temp_dir):
                for _ in range(10):
                    try:
                        shutil.rmtree(temp_dir)
                        break
                    except PermissionError:
                        time.sleep(0.5)
            
            if os.path.exists(script_path): 
                try: os.remove(script_path)
                except PermissionError: pass

            # =================================================================
            # NEU: AUTOMATISCHE GLOBALE REGISTRIERUNG FÜR GRÜNKANAL-STACKS
            # =================================================================
            is_green_global = "Global Reg" in modus_text
            
            if is_green_global and not self.stop_requested and erfolgreich > 0:
                self.log("\nStarte Phase 2: Globale Registrierung der fertigen Stacks...")
                self.btn_stop.configure(state="disabled") # Stoppen jetzt verhindern, da es schnell geht
                
                script_path_global = os.path.join(out_dir, "global_reg.ssf")
                out_dir_siril = out_dir.replace('\\', '/')
                
                # Wir weisen Siril an, die frisch erzeugte Sequenz "shortstack" zu laden und global auszurichten
                with open(script_path_global, "w", encoding="utf-8") as f:
                    f.write("requires 1.2.0\n")
                    f.write(f'cd "{out_dir_siril}"\n')
                    f.write("setext fit\n")
                    f.write("setref shortstack 1\n") 
                    f.write("register shortstack\n")
                    f.write("close\n")
                    
                self.log("Siril richtet die Stacks aneinander aus. Bitte warten...")
                process = subprocess.run([siril_exe, "-s", script_path_global], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                
                if process.returncode == 0:
                    self.log("-> Globale Ausrichtung erfolgreich!")
                    # Aufräumen: Die wackeligen Zwischen-Stacks löschen, damit nur die r_shortstacks übrig bleiben
                    unaligned = glob.glob(os.path.join(out_dir, "shortstack_*.fit"))
                    for f in unaligned:
                        try: os.remove(f)
                        except Exception: pass
                else:
                    self.log("-> FEHLER bei der finalen Registrierung! (Sind genug Sterne sichtbar?)")
                    
                if os.path.exists(script_path_global):
                    try: os.remove(script_path_global)
                    except Exception: pass
            # =================================================================

            self.after(0, self.update_progress, 1.0)
            
            self.log("\n===========================================")
            if is_direct_export:
                self.log(f"FERTIG! {erfolgreich} Bilder wurden im Ordner 'timelapse_unstacked_frames' gespeichert.")
            else:
                farbe = "grüne " if "Grün" in modus_text else ""
                self.log(f"FERTIG! {erfolgreich} {farbe}Short-Stacks wurden erstellt.")
            self.log("===========================================")

        except Exception as e:
            self.log(f"\nKRITISCHER FEHLER:\n{str(e)}")
        finally:
            self.after(0, self._reset_buttons)

    def _reset_buttons(self):
        self.btn_stop.configure(state="disabled", text="⏹ Stop / Abbruch")
        
        if hasattr(self, 'btn_stack_color'): self.btn_stack_color.configure(state="normal")
        if hasattr(self, 'btn_stack_green'): self.btn_stack_green.configure(state="normal")
        if hasattr(self, 'btn_stack_reg'): self.btn_stack_reg.configure(state="normal")
        if hasattr(self, 'btn_tool_conv'): self.btn_tool_conv.configure(state="normal")
        
    # --- TIMELAPSE LOGIK ---
    def start_timelapse_thread(self):
        self.btn_timelapse.configure(state="disabled", text="Arbeite...")
        self.progress_bar.set(0.0)
        self.log_box.delete("0.0", "end")
        self.log("=== Flexibler Timelapse-Export gestartet ===")
        
        t = threading.Thread(target=self.run_timelapse_process)
        t.daemon = True
        t.start()

    def run_timelapse_process(self):
        try:
            siril_exe = self.siril_path.get()
            ffmpeg_exe = self.ffmpeg_path.get()
            seti_exe = self.setiastro_path.get() 
            
            source_choice = self.video_source.get()
            is_fits_source = "FITS" in source_choice
            
            # --- 1. QUELL- UND ZIELORDNER BESTIMMEN ---
            if is_fits_source:
                if "Input" in source_choice:
                    src_dir = self.input_folder.get()
                    out_dir = self.output_folder.get()
                else:
                    src_dir = self.output_folder.get()
                    out_dir = self.output_folder.get()
                    
                if not src_dir or not out_dir:
                    self.log("FEHLER: Bitte wähle die entsprechenden Input/Output Ordner!")
                    return
                frames_dir = os.path.join(out_dir, "timelapse_frames")
            else:
                custom_folder = filedialog.askdirectory(title="Beliebigen Ordner mit JPG/PNG/TIF Bildern wählen")
                if not custom_folder: return
                src_dir = custom_folder
                out_dir = custom_folder
                frames_dir = custom_folder

            format_choice = self.export_format.get()
            if "PNG" in format_choice: ext = "png"; save_cmd = "savepng"
            elif "TIFF" in format_choice: ext = "tif"; save_cmd = "savetif"
            else: ext = "jpg"; save_cmd = "savejpg"

            # --- 2. SIRIL STRETCH (FÜR ALLE FITS) ---
            if is_fits_source:
                # Nimm einfach ALLE FITS aus dem Ordner, egal wie sie heißen!
                dateien = self._find_fits_files(src_dir)
                dateien.sort(key=self._get_fits_timestamp) # Chronologisch sortieren
                
                total_fits = len(dateien)
                if total_fits == 0:
                    self.log(f"FEHLER: Keine FITS im Ordner gefunden:\n{src_dir}")
                    return
                    
                self.log(f"[{total_fits}] FITS-Dateien zur Videokonvertierung gefunden.")
                if not os.path.exists(frames_dir):
                    os.makedirs(frames_dir)
                    
                script_path = os.path.join(out_dir, "timelapse_script.ssf")
                frames_dir_siril = frames_dir.replace('\\', '/')
                
                self.log(f"Generiere Siril-Skript für {ext.upper()}-Export...")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write("requires 1.2.0\n")
                    f.write(f'cd "{src_dir.replace(chr(92), "/")}"\n')
                    for idx, datei in enumerate(dateien):
                        filename = os.path.basename(datei)
                        f.write(f'load "{filename}"\n')
                        # NEU: rmgreen flexibel wieder da!
                        if self.use_rmgreen.get():
                            f.write("rmgreen\n")
                        f.write("autostretch\n")
                        f.write(f'{save_cmd} "{frames_dir_siril}/frame_{idx+1:04d}"\n')
                    
                self.log("Siril konvertiert und wendet Autostretch an. Bitte warten...")
                try:
                    process = subprocess.Popen(
                        [siril_exe, "-s", script_path], 
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                        text=True, encoding="utf-8", errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    frames_done = 0
                    last_log_lines = [] # Speichert die letzten Ausgaben für die Fehlersuche
                    
                    for line in iter(process.stdout.readline, ''):
                        if not line: break
                        
                        clean_line = line.strip()
                        if clean_line:
                            last_log_lines.append(clean_line)
                            if len(last_log_lines) > 10:
                                last_log_lines.pop(0) # Nur die letzten 10 Zeilen merken
                                
                        if "saving" in clean_line.lower() or "saved" in clean_line.lower():
                            frames_done += 1
                            self.after(0, self.update_progress, min((frames_done / total_fits) * 0.8, 0.8))
                            
                    process.wait()
                    
                    if process.returncode == 0:
                        self.log(f"-> Alle {total_fits} Bilder erfolgreich als {ext.upper()} exportiert!")
                    else:
                        self.log("-> FEHLER beim Exportieren in Siril!")
                        self.log("Letzte Meldungen von Siril:")
                        for err_line in last_log_lines:
                            self.log(f"   {err_line}")
                        return
                        
                except FileNotFoundError:
                    self.log("FEHLER: siril-cli.exe nicht gefunden. Pfad in den Einstellungen prüfen!")
                    return
                finally:
                    if os.path.exists(script_path): 
                        try: os.remove(script_path)
                        except Exception: pass
            else:
                self.log("Quelle sind bereits fertige Bilder. Überspringe Siril...")
                self.after(0, self.update_progress, 0.8)

            # --- 2.5 KI-ENTRAUSCHEN (SETIASTRO) ---
            if self.use_denoise.get():
                self.log("\nStarte KI-Entrauschen mit SetiAstro CosmicClarity...")
                denoised_dir = os.path.join(out_dir, "timelapse_denoised")
                if not os.path.exists(denoised_dir):
                    os.makedirs(denoised_dir)
                
                raw_frames = []
                for ext_pattern in ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff'):
                    raw_frames.extend(glob.glob(os.path.join(frames_dir, ext_pattern)))
                    raw_frames.extend(glob.glob(os.path.join(frames_dir, ext_pattern.upper())))
                raw_frames = sorted(list(set(raw_frames)))
                
                total_denoise = len(raw_frames)
                if total_denoise == 0:
                    self.log("FEHLER: Keine Bilder zum Entrauschen gefunden!")
                    return
                
                for idx, fpath in enumerate(raw_frames):
                    out_f = os.path.join(denoised_dir, os.path.basename(fpath))
                    
                    cmd = [
                        seti_exe, "cc", "denoise", 
                        "-i", fpath, "-o", out_f, 
                        "--gpu", 
                        "--denoise-luma", "0.8", 
                        "--denoise-color", "0.8"
                    ]
                    if self.use_denoise_lite.get(): 
                        cmd.append("--denoise-lite")
                    
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    except FileNotFoundError:
                        self.log("FEHLER: SetiAstroSuitePro.exe nicht gefunden. Pfad in den Einstellungen prüfen!")
                        return
                        
                    if idx % 5 == 0 or idx == total_denoise - 1:
                        self.log(f"Entrausche Bild {idx+1}/{total_denoise}...")
                        
                frames_dir = denoised_dir
                self.log(f"-> {total_denoise} Bilder erfolgreich entrauscht.")

            # --- 3. FLEXIBLE FFMPEG VORBEREITUNG (HARDLINKS) ---
            self.log("\nBereite Bilder für FFmpeg vor...")
            valid_exts = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff')
            image_files = []
            for ext_pattern in valid_exts:
                image_files.extend(glob.glob(os.path.join(frames_dir, ext_pattern)))
                image_files.extend(glob.glob(os.path.join(frames_dir, ext_pattern.upper())))
            
            image_files = sorted(list(set(image_files)))
            total_video_frames = len(image_files)
            
            if total_video_frames == 0:
                self.log(f"FEHLER: Keine passenden Bilder (JPG/PNG/TIF) im Ordner gefunden:\n{frames_dir}")
                return
                
            self.log(f"-> {total_video_frames} Bilder gefunden. Erstelle temporäre Render-Links...")
            
            temp_ffmpeg_dir = os.path.join(out_dir, "temp_ffmpeg_render")
            if os.path.exists(temp_ffmpeg_dir):
                shutil.rmtree(temp_ffmpeg_dir)
            os.makedirs(temp_ffmpeg_dir)
            
            first_ext = os.path.splitext(image_files[0])[1]
            
            N_frames = len(image_files)

            for idx, file_path in enumerate(image_files):
                dst = os.path.join(temp_ffmpeg_dir, f"frame_{idx+1:05d}{first_ext}")
                
                img = cv2.imread(file_path)
                
                if self.crop_coordinates:
                    x1, y1, x2, y2 = self.crop_coordinates
                    w = x2 - x1
                    h = y2 - y1
                    if w % 2 != 0: x2 -= 1
                    if h % 2 != 0: y2 -= 1
                    
                    img_cropped = img[y1:y2, x1:x2]
                else:
                    img_cropped = img  
                    x1, y1 = 0, 0      

                if hasattr(self, 'asteroid_coordinates') and self.asteroid_coordinates:
                    (start_x_orig, start_y_orig), (end_x_orig, end_y_orig) = self.asteroid_coordinates
                    
                    ast_x_start = start_x_orig - x1
                    ast_y_start = start_y_orig - y1
                    ast_x_end = end_x_orig - x1
                    ast_y_end = end_y_orig - y1
                    
                    # Berechnet die exakte Position für das aktuelle Bild (auch wenn es nur 1 Bild gibt)
                    cur_x = int(ast_x_start + (idx / (N_frames - 1)) * (ast_x_end - ast_x_start)) if N_frames > 1 else ast_x_start
                    cur_y = int(ast_y_start + (idx / (N_frames - 1)) * (ast_y_end - ast_y_start)) if N_frames > 1 else ast_y_start
                    
                    # Variablen aus der GUI holen
                    m_style = self.marker_style.get()
                    m_size = int(self.marker_size.get())
                    m_color = (0, 0, 200) # Rot in BGR
                    m_thick = 2
                    
                    if m_style == "Pfeil":
                        gap = 8 # Abstand der Pfeilspitze zum Objekt
                        if m_size <= gap: m_size = gap + 10 # Verhindert Fehler, wenn Regler zu klein
                        arrow_start = (cur_x - m_size, cur_y - m_size)
                        arrow_end = (cur_x - gap, cur_y - gap)
                        cv2.arrowedLine(img_cropped, arrow_start, arrow_end, m_color, m_thick, cv2.LINE_AA, 0, 0.2)
                        
                    elif m_style == "Kreis":
                        # Zieht einen sauberen Kreis
                        cv2.circle(img_cropped, (cur_x, cur_y), m_size, m_color, m_thick, cv2.LINE_AA)
                        
                    elif m_style == "Fadenkreuz":
                        # Zeichnet 4 Linien mit Lücke in der Mitte, damit der Asteroid sichtbar bleibt
                        gap = 8 
                        # Oben
                        cv2.line(img_cropped, (cur_x, cur_y - gap), (cur_x, cur_y - gap - m_size), m_color, m_thick, cv2.LINE_AA)
                        # Unten
                        cv2.line(img_cropped, (cur_x, cur_y + gap), (cur_x, cur_y + gap + m_size), m_color, m_thick, cv2.LINE_AA)
                        # Links
                        cv2.line(img_cropped, (cur_x - gap, cur_y), (cur_x - gap - m_size, cur_y), m_color, m_thick, cv2.LINE_AA)
                        # Rechts
                        cv2.line(img_cropped, (cur_x + gap, cur_y), (cur_x + gap + m_size, cur_y), m_color, m_thick, cv2.LINE_AA)

                if self.crop_coordinates or (hasattr(self, 'asteroid_coordinates') and self.asteroid_coordinates):
                    cv2.imwrite(dst, img_cropped)
                else:
                    try:
                        os.link(file_path, dst) 
                    except OSError:
                        shutil.copy2(file_path, dst)
                    
            # --- 4. FFMPEG RENDERING ---
            self.log("Versuche Video mit FFmpeg zu rendern...")
            video_out = os.path.join(out_dir, "timelapse_v1.7.mp4")
            
            ffmpeg_cmd = [
                ffmpeg_exe, "-y", "-framerate", "24", 
                "-i", os.path.join(temp_ffmpeg_dir, f"frame_%05d{first_ext}"), 
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", video_out
            ]
            
            try:
                ff_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                
                for line in iter(ff_process.stdout.readline, ''):
                    if not line: break
                    if "frame=" in line:
                        try:
                            parts = line.split("frame=")[1].strip().split()
                            current_frame = int(parts[0])
                            ff_fortschritt = 0.8 + ((current_frame / total_video_frames) * 0.2)
                            self.after(0, self.update_progress, min(ff_fortschritt, 1.0))
                        except (IndexError, ValueError):
                            pass
                
                ff_process.wait()
                
                if ff_process.returncode == 0:
                    self.log(f"-> ERFOLG! Video gespeichert unter:\n{video_out}")
                else:
                    self.log("-> FFmpeg hat mit einem Fehler abgebrochen.")
                    
            except FileNotFoundError:
                self.log("-> HINWEIS: FFmpeg (ffmpeg.exe) wurde nicht gefunden.")
                self.log("-> Bitte installiere FFmpeg oder korrigiere den Pfad in den Einstellungen (⚙️)!")
                
            finally:
                if os.path.exists(temp_ffmpeg_dir):
                    try:
                        shutil.rmtree(temp_ffmpeg_dir)
                    except Exception:
                        pass
                
            self.after(0, self.update_progress, 1.0)
            self.log("\n===========================================")
            self.log("TIMELAPSE EXPORT ABGESCHLOSSEN!")
                
        except Exception as e:
            self.log(f"\nKRITISCHER FEHLER:\n{str(e)}")
        finally:
            self.after(0, lambda: self.btn_timelapse.configure(state="normal", text="🎞️ Timelapse rendern"))

if __name__ == "__main__":
    app = ShortStackerApp()
    app.mainloop()