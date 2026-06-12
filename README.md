⚡ ShortStacker
Siril & SetiAstro Automation: Batch-Stacking und Timelapses für Smart-Teleskope.
Smart-Teleskope wie das Seestar S50 nehmen standardmäßig Einzelbilder im 10-Sekunden-Takt auf. Bei langen Beobachtungsnächten entstehen so Tausende von Dateien. Der ShortStacker löst dieses Problem: Er automatisiert Siril, um diese extrem kurzen Belichtungen in kleine, handliche "Short-Stacks" (z. B. immer 6 Bilder = 1 Minute) zusammenzufassen.
Das spart enorm viel Speicherplatz, erhöht das Signal-Rausch-Verhältnis (SNR) für wissenschaftliche Auswertungen und ist die perfekte Grundlage, um butterweiche Timelapses (Zeitraffer) von wandernden Kometen oder Asteroiden zu erstellen.

✨ Hauptfunktionen
📂 Batch-Stacking: Fasse hunderte 10s-FITS-Dateien vollautomatisch zu Short-Stacks (z.B. 1 Min, 2 Min) zusammen, ohne ein einziges Siril-Skript selbst schreiben zu müssen.
🌈 Flexible Modi: Wähle zwischen Farbe (Debayer) für visuell ansprechende Timelapses, Mono (RAW) oder Grünkanal-Extraktion (Perfekt für präzise Photometrie im VStar Analyzer).
🎞️ Timelapse-Renderer: Erstellt aus deinen Stacks (oder direkt aus den FITS) per Klick ein fertiges, flüssiges MP4-Zeitraffervideo.
🧠 KI Denoise-Integration: Direkte Schnittstelle zur SetiAstro CosmicClarity KI. Entrauscht deine Bilder auf Wunsch vollautomatisch per Grafikkarte, bevor sie zum Timelapse-Video zusammengefügt werden.
🔧 Globale Registrierung: Ein spezieller Modus für die Photometrie, der hunderte Bilder auf ein einziges Referenzbild ausrichtet.
📥 Installation & Download
Für Anwender (Fertige App)
Die einfachste Methode ohne Programmieren:
Gehe auf dieser Seite rechts zum Bereich [Releases].
Lade dir die neueste ShortStacker_vX.X.zip herunter.
Entpacke den Ordner an einen beliebigen Ort auf deinem PC.
Starte die ShortStacker.exe.
Für Entwickler (Python Quellcode)
Wenn du den Code ausführen oder anpassen möchtest:
Klone dieses Repository:
code
Bash
git clone https://github.com/SteffSarek/Short-Stacker.git
Installiere das benötigte UI-Paket:
code
Bash
pip install customtkinter
Starte das Programm:
code
Bash
python short_stacker_gui.py
⚙️ Externe Abhängigkeiten (Wichtig!)
Der ShortStacker ist ein Automatisierungs-Tool und greift "unter der Haube" auf andere Programme zu. Diese müssen installiert sein. Die Pfade zu den .exe-Dateien kannst du in den Einstellungen (⚙️) der App hinterlegen:
Siril: (Zwingend erforderlich!) Wird für das Debayern, Registrieren und Stacken der FITS-Dateien genutzt (siril-cli.exe).
FFmpeg: (Erforderlich für Timelapses) Verwandelt die Bildergalerie in ein echtes .mp4 Video.
SetiAstro CosmicClarity: (Optional) Ein fantastisches, externes KI-Tool zur Rauschminderung. Wird benötigt, wenn du den Haken bei "KI Denoise" setzt.
📝 Lizenz & Credits
Dieses Projekt steht unter der GNU General Public License v3.0.
Entwickelt von Stefan Raphael (2025-2026).
Siril, FFmpeg und SetiAstro sind eingetragene Marken/Projekte ihrer jeweiligen Entwickler.