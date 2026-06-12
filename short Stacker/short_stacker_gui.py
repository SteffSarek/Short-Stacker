import os
import glob
import shutil
import subprocess
import threading
import time
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ShortStackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Astro Short-Stacker (Siril & SetiAstro Automation) v1.6.1")
        self.geometry("1050x680")
        try:
            if os.path.exists("shortstacker.ico"): 
                self.wm_iconbitmap("shortstacker.ico")
        except Exception: 
            pass
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1) 

        # --- VARIABLEN & EINSTELLUNGEN ---
        self.settings_file = "shortstacker_settings.json"
        
        self.input_folder = ctk.StringVar()
        self.output_folder = ctk.StringVar()
        self.siril_path = ctk.StringVar()
        self.ffmpeg_path = ctk.StringVar()
        self.setiastro_path = ctk.StringVar()
        
        self.batch_size = ctk.StringVar(value="6")
        self.stop_requested = False 
        
        # Denoise Variablen
        self.use_denoise = ctk.BooleanVar(value=False)
        self.use_denoise_lite = ctk.BooleanVar(value=True) # Standardmäßig an, aber erst aktiv wenn Haupt-Haken gesetzt
        
        self.load_settings()

        self._build_gui()

    # --- SETTINGS SPEICHERN/LADEN ---
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
        # 0. Top Bar (Titel & Einstellungen)
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="ew")
        ctk.CTkLabel(top_frame, text="Astro Short-Stacker v1.6.1", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top_frame, text="⚙️ Einstellungen", width=120, fg_color="#454545", hover_color="#2b2b2b", command=self.open_settings).pack(side="right")

        # 1. Input Ordner
        frame_in = ctk.CTkFrame(self)
        frame_in.grid(row=1, column=0, padx=20, pady=(15, 10), sticky="ew")
        ctk.CTkLabel(frame_in, text="1. Input (Originale 10s FITS):", width=180, anchor="w").pack(side="left", padx=10, pady=10)
        ctk.CTkEntry(frame_in, textvariable=self.input_folder, state="readonly", width=300).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(frame_in, text="Ordner wählen", command=self.select_input, width=120).pack(side="right", padx=10)

        # 2. Output Ordner
        frame_out = ctk.CTkFrame(self)
        frame_out.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_out, text="2. Output (Fertige Stacks):", width=180, anchor="w").pack(side="left", padx=10, pady=10)
        ctk.CTkEntry(frame_out, textvariable=self.output_folder, state="readonly", width=300).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(frame_out, text="Ordner wählen", command=self.select_output, width=120).pack(side="right", padx=10)

        # 3. Optionen & Buttons (STACKING)
        frame_run = ctk.CTkFrame(self, fg_color="transparent")
        frame_run.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_run, text="Bilder pro Batch:").pack(side="left", padx=(0, 10))
        ctk.CTkEntry(frame_run, textvariable=self.batch_size, width=50, justify="center").pack(side="left")
        
        self.stack_mode = ctk.StringVar(value="Farbe (Debayer) für Timelapse")
        self.opt_mode = ctk.CTkOptionMenu(
            frame_run, 
            variable=self.stack_mode, 
            values=[
                "Farbe (Debayer) für Timelapse", 
                "Original Mono (RAW)", 
                "Nur Grünkanal (Photometrie)",
                "➡️ Nur registrieren (Für Photometrie / Global)",
                "➡️ Nur Konvertieren (Input direkt zu JPG/PNG)"
            ],
            width=280
        )
        self.opt_mode.pack(side="left", padx=20)
        
        self.btn_stop = ctk.CTkButton(frame_run, text="⏹ Stop", fg_color="#9e3e3e", hover_color="#7a2f2f", font=ctk.CTkFont(weight="bold"), state="disabled", command=self.request_stop)
        self.btn_stop.pack(side="right", padx=(10, 0))

        self.btn_start = ctk.CTkButton(frame_run, text="▶ Starten", fg_color="#2b7b4a", hover_color="#1e5c36", font=ctk.CTkFont(weight="bold"), command=self.start_stacking_thread)
        self.btn_start.pack(side="right")
        
        # 4. Timelapse Bereich
        frame_timelapse = ctk.CTkFrame(self, fg_color="transparent")
        frame_timelapse.grid(row=4, column=0, padx=20, pady=(10, 10), sticky="ew")
        ctk.CTkLabel(frame_timelapse, text="Video-Export:").pack(side="left", padx=(0, 10))
        
        self.video_source = ctk.StringVar(value="Quelle: FITS Stacks")
        self.opt_vid_source = ctk.CTkOptionMenu(
            frame_timelapse, 
            variable=self.video_source, 
            values=["Quelle: FITS Stacks", "Quelle: Einzelbilder (Unstacked)", "Quelle: Beliebiger Ordner (StarStax etc.)"],
            width=230
        )
        self.opt_vid_source.pack(side="left", padx=(0, 10))

        self.export_format = ctk.StringVar(value="JPEG (Schnell & Klein)")
        self.opt_format = ctk.CTkOptionMenu(
            frame_timelapse, 
            variable=self.export_format, 
            values=["JPEG (Schnell & Klein)", "PNG (Verlustfrei & Groß)"],
            width=180
        )
        self.opt_format.pack(side="left", padx=(0, 10))

        # Denoise Checkboxen (angepasst)
        mid_denoise = ctk.CTkFrame(frame_timelapse, fg_color="transparent")
        mid_denoise.pack(side="left", padx=(0, 10))
        
        # Haupt-Haken löst _toggle_denoise_lite aus
        self.chk_denoise = ctk.CTkCheckBox(mid_denoise, text="KI Denoise (SetiAstro) Rechenintensiv!", variable=self.use_denoise, command=self._toggle_denoise_lite)
        self.chk_denoise.pack(side="top", anchor="w")
        
        # Lite-Haken ist eingerückt und standardmäßig deaktiviert
        self.chk_lite = ctk.CTkCheckBox(mid_denoise, text="Denoise Lite Mode", variable=self.use_denoise_lite, state="disabled")
        self.chk_lite.pack(side="top", anchor="w", pady=(5,0), padx=(20, 0))

        self.btn_timelapse = ctk.CTkButton(frame_timelapse, text="🎞️ Timelapse rendern", fg_color="#b87333", hover_color="#8c5827", font=ctk.CTkFont(weight="bold"), command=self.start_timelapse_thread)
        self.btn_timelapse.pack(side="right")

        # 5. FORTSCHRITTSBALKEN
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="ew")
        self.progress_bar.set(0.0) 

        # 6. Log Box
        ctk.CTkLabel(self, text="Log-Ausgabe:", anchor="w").grid(row=6, column=0, padx=20, pady=(10, 0), sticky="ew")
        self.log_box = ctk.CTkTextbox(self)
        self.log_box.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_box.insert("0.0", "Bereit. v1.6.1 mit SetiAstro-Support. Bitte Ordner auswählen...\n")

    # --- HILFSMETHODEN FÜR GUI ---
    def _toggle_denoise_lite(self):
        """Aktiviert oder deaktiviert die Lite-Checkbox basierend auf dem Haupt-Haken."""
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

    # --- GUI INTERAKTIONEN ---
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

        self.btn_start.configure(state="disabled", text="Arbeite...")
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
            search1 = os.path.join(in_dir, "*.fit")
            search2 = os.path.join(in_dir, "*.fits")
            dateien = sorted(glob.glob(search1) + glob.glob(search2))
            
            total_files = len(dateien)
            if total_files == 0:
                self.log("FEHLER: Keine .fit oder .fits Dateien im Input-Ordner gefunden!")
                return

            self.log(f"[{total_files}] Dateien gefunden. Paketgröße: {batch_size} Bilder...\n")

            temp_dir = os.path.join(in_dir, "siril_temp_workdir")
            script_path = os.path.join(in_dir, "temp_script.ssf")

            # --- ZUERST DIE VARIABLEN DEFINIEREN ---
            is_direct_export = "Nur Konvertieren" in modus_text
            is_photometry_reg = "Nur registrieren (Für Photometrie / Global)" in modus_text 
            
            export_ext = ""
            export_cmd = ""
            frames_dir_siril = ""
            global_frame_idx = 1 

            # --- DANN ERST DIE ABFRAGEN ---
            if is_direct_export:
                format_choice = self.export_format.get()
                is_png = "PNG" in format_choice
                export_ext = "png" if is_png else "jpg"
                export_cmd = "savepng" if is_png else "savejpg"

                frames_dir = os.path.join(out_dir, "timelapse_unstacked_frames")
                if not os.path.exists(frames_dir):
                    os.makedirs(frames_dir)
                frames_dir_siril = frames_dir.replace('\\', '/')
            
            # --- NEUER VORGANG: Globale Photometrie-Registrierung ---
            if is_photometry_reg:
                self.log("\nStarte globale Registrierung für Photometrie...")
                self.log("Batch-Größe wird ignoriert. Verarbeite alle Bilder in einem Durchgang.")

                # Temp-Ordner im Output erstellen
                temp_reg_dir = os.path.join(out_dir, "temp_photometry_reg")
                if os.path.exists(temp_reg_dir):
                    shutil.rmtree(temp_reg_dir, ignore_errors=True)
                os.makedirs(temp_reg_dir)

                # 1. Alle Bilder in den Temp-Ordner kopieren
                self.log("Kopiere Dateien in den Arbeitsordner...")
                for idx, datei in enumerate(dateien):
                    if self.stop_requested: return
                    shutil.copy(datei, os.path.join(temp_reg_dir, f"light_{idx+1:05d}.fit"))
                    if idx % 10 == 0: 
                        self.after(0, self.update_progress, (idx / total_files) * 0.2)

                temp_dir_siril = temp_reg_dir.replace('\\', '/')
                script_path = os.path.join(temp_reg_dir, "reg_script.ssf")

                # 2. Siril Skript: Konvertieren -> setref 1 -> Global registrieren
                siril_script_content = f"requires 1.2.0\nsetext fit\ncd \"{temp_dir_siril}\"\n"
                siril_script_content += "convert light\n"
                siril_script_content += "setref light 1\n"  # <--- DER MAGISCHE BEFEHL
                siril_script_content += "register light\n"
                siril_script_content += "close\n"

                with open(script_path, "w") as f:
                    f.write(siril_script_content)

                # 3. Siril ausführen
                self.log("Siril registriert global (ohne Farb/Grünkanal Extraktion)... Bitte warten.")
                self.after(0, self.update_progress, 0.5) 
                try:
                    process = subprocess.run([siril_exe, "-s", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                except FileNotFoundError:
                    self.log("FEHLER: siril-cli.exe nicht gefunden.")
                    return

                # 4. Dateien zurückschieben und umbenennen
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

                # 5. Aufräumen
                shutil.rmtree(temp_reg_dir, ignore_errors=True)
                self.after(0, self._reset_buttons)
                return
            # --------------------------------------------------------

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
                        # Zwingt Siril, auch winzige (sigma) und unrunde (roundness) Sterne auf dem halbierten Bild zu erkennen
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
        self.btn_start.configure(state="normal", text="▶ Starten")
        self.btn_stop.configure(state="disabled", text="⏹ Stop")
        
    # --- TIMELAPSE LOGIK ---
    def start_timelapse_thread(self):
        source_choice = self.video_source.get()
        is_custom = "Beliebiger Ordner" in source_choice
        out_dir = self.output_folder.get()
        
        if not is_custom and not out_dir:
            messagebox.showerror("Fehler", "Bitte den Output-Ordner auswählen!")
            return
            
        custom_folder = ""
        if is_custom:
            custom_folder = filedialog.askdirectory(title="Beliebigen Ordner mit JPG/PNG/TIF Bildern wählen")
            if not custom_folder:
                return 
            
        self.btn_timelapse.configure(state="disabled", text="Arbeite...")
        self.progress_bar.set(0.0)
        self.log_box.delete("0.0", "end")
        self.log("=== Flexibler Timelapse-Export gestartet ===")
        
        t = threading.Thread(target=self.run_timelapse_process, args=(out_dir, custom_folder))
        t.daemon = True
        t.start()

    def run_timelapse_process(self, out_dir, custom_folder):
        try:
            siril_exe = self.siril_path.get()
            ffmpeg_exe = self.ffmpeg_path.get()
            seti_exe = self.setiastro_path.get() 
            
            source_choice = self.video_source.get()
            is_unstacked = "Einzelbilder" in source_choice
            is_custom = "Beliebiger" in source_choice
            
            format_choice = self.export_format.get()
            is_png = "PNG" in format_choice
            ext = "png" if is_png else "jpg"
            save_cmd = "savepng" if is_png else "savejpg"

            # --- 1. ORDNER WEICHE ---
            if is_custom:
                frames_dir = custom_folder
                out_dir = custom_folder 
            elif is_unstacked:
                frames_dir = os.path.join(out_dir, "timelapse_unstacked_frames")
            else:
                frames_dir = os.path.join(out_dir, "timelapse_frames")
                
            # --- 2. SIRIL STRETCH (NUR FÜR FITS STACKS) ---
            if not is_custom and not is_unstacked:
                search_pattern = os.path.join(out_dir, "shortstack_*.fit")
                dateien = sorted(glob.glob(search_pattern))
                total_fits = len(dateien)
                
                if total_fits == 0:
                    self.log("FEHLER: Keine 'shortstack_*.fit' Dateien im Ordner gefunden!")
                    return
                    
                self.log(f"[{total_fits}] fertige Stacks für Timelapse gefunden.")
                if not os.path.exists(frames_dir):
                    os.makedirs(frames_dir)
                    
                script_path = os.path.join(out_dir, "timelapse_script.ssf")
                frames_dir_siril = frames_dir.replace('\\', '/')
                
                self.log(f"Generiere Siril-Skript für {ext.upper()}-Export...")
                with open(script_path, "w") as f:
                    f.write("requires 1.2.0\n")
                    f.write(f'cd "{out_dir.replace("\\", "/")}"\n')
                    for idx, datei in enumerate(dateien):
                        filename = os.path.basename(datei)
                        f.write(f'load "{filename}"\nrmgreen\nautostretch\nmirrorx\n')
                        f.write(f'{save_cmd} "{frames_dir_siril}/frame_{idx+1:04d}"\n')
                    f.write("close\n")
                    
                self.log("Siril wendet Autostretch an. Bitte warten...")
                try:
                    process = subprocess.Popen([siril_exe, "-s", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    frames_done = 0
                    for line in iter(process.stdout.readline, ''):
                        if not line: break
                        if "Saving" in line or "saving" in line.lower():
                            frames_done += 1
                            self.after(0, self.update_progress, min((frames_done / total_fits) * 0.8, 0.8))
                    process.wait()
                    
                    if process.returncode == 0:
                        self.log(f"-> Alle Stacks erfolgreich als {ext.upper()} exportiert!")
                    else:
                        self.log("-> FEHLER beim Exportieren in Siril!")
                        return
                except FileNotFoundError:
                    self.log("FEHLER: siril-cli.exe nicht gefunden. Pfad in den Einstellungen prüfen!")
                    return
                finally:
                    if os.path.exists(script_path): os.remove(script_path)
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
            
            for idx, file_path in enumerate(image_files):
                dst = os.path.join(temp_ffmpeg_dir, f"frame_{idx+1:05d}{first_ext}")
                try:
                    os.link(file_path, dst) 
                except OSError:
                    shutil.copy2(file_path, dst) 
                    
            # --- 4. FFMPEG RENDERING ---
            self.log("Versuche Video mit FFmpeg zu rendern...")
            video_out = os.path.join(out_dir, "timelapse_v1.6.mp4")
            
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