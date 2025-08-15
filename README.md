\# Nomadachi



A Pwnagotchi plugin that turns roaming into a game. \*\*Nomadachi\*\* tracks the unique places your gotchi discovers and awards XP for exploration. It shows a compact travel title + place count on the UI, e.g.:



```

Trav Homebody (2pl)

```



---



\## ✨ Features



\- \*\*Places counter\*\* — counts unique places discovered (GPS grid cells or band-only fallback)

\- \*\*Travel XP\*\* — awards XP for first‑time encounters (ESSIDs, BSSIDs, OUIs, bands, places)

\- \*\*Titles\*\* — unlock fun titles as XP increases (configurable thresholds)

\- \*\*Minimal UI\*\* — one tidy line: `Trav <title> (<places>pl)`

\- \*\*Persistent\*\* — progress is saved to disk and restored on boot

\- \*\*Migration\*\* — can import travel stats from the Age plugin



---



\## 🛠 Installation



1\. Copy the plugin file to your Pwnagotchi:



```

/usr/local/share/pwnagotchi/custom-plugins/nomadachi.py

```



2\. Enable it in `/etc/pwnagotchi/config.toml`:



```toml

\# --- Nomadachi ---

\[main.plugins.nomadachi]

enabled = true



\# UI position (pixels)

x = 10

y = 118



\# GPS grid (degrees). 0.01 ≈ ~1.1 km cells

travel\_grid = 0.01



\# If no GPS is available, treat each band as a single "place"

\# so one neighborhood doesn't mint dozens of places.

strict\_nogps\_places = true



\# XP tuning for first‑time encounters

xp\_essid = 2

xp\_bssid = 1

xp\_oui   = 1

xp\_band  = 2

xp\_place = 10



\# Optional: UI text format (tokens: {title}, {level}, {places})

format = "{title} ({places}pl)"



\# One‑time migration from Age plugin's /root/age\_strength.json travel fields

migrate\_from\_age = true



\# Optional: override title thresholds (XP → Title). Keys must be strings in TOML:

\# titles."0" = "Homebody"

\# titles."200" = "Wanderling"

\# titles."600" = "City Stroller"

\# titles."1200" = "Road Warrior"

\# titles."2400" = "Jetsetter"

\# titles."4800" = "Globetrotter"

```



3\. Restart Pwnagotchi:



```

sudo systemctl restart pwnagotchi

sudo journalctl -u pwnagotchi -n 120 --no-pager

```



---



\## 🧭 How it works



\*\*Places\*\*



\- With \*\*GPS\*\*: Nomadachi quantizes latitude/longitude to a grid (default `travel\_grid = 0.01°`) and counts new grid cells as new places.

\- Without GPS: the fallback is \*\*band-only\*\* (e.g., `nogps-2.4`, `nogps-5`, `nogps-6`), preventing a dense neighborhood from creating many “places.”



\*\*Travel XP\*\* (first‑time encounters per handshake):



\- +`xp\_essid` for a \*\*new ESSID\*\*

\- +`xp\_bssid` for a \*\*new BSSID\*\*

\- +`xp\_oui` for a \*\*new vendor OUI\*\* (first 3 MAC bytes)

\- +`xp\_band` for a \*\*new band\*\* (2.4/5/6 GHz)

\- +`xp\_place` for a \*\*new place\*\*



Titles change as your \*\*total XP\*\* crosses configured thresholds.



---



\## 🖥 UI



Nomadachi renders a compact line on the display. Default format:



```

Trav <title> (<places>pl)

```



Customize via `format` in the config (available tokens: `{title}`, `{level}`, `{places}`).



---



\## 💾 Persistence



Data is stored at:



```

/root/pwn\_traveler.json

```



Delete this file to reset your progress (Nomadachi will recreate it).



---



\## 🔁 Migrating from the Age plugin



If you previously used an Age plugin variant with travel fields, Nomadachi can import from:



```

/root/age\_strength.json

```



Set `migrate\_from\_age = true` (default) and keep that file present for the first run.



---



\## 🔧 Tips \& Tuning



\- \*\*Make "places" denser:\*\* decrease `travel\_grid` (e.g., `0.005` ≈ \\~550 m).

\- \*\*Slow down rank ups:\*\* reduce XP values and/or raise title thresholds.

\- \*\*Disable fallback liberal places:\*\* keep `strict\_nogps\_places = true`.

\- \*\*Disable Nomadachi travel in Age:\*\* set `main.plugins.age.enable\_travel = false` if your Age plugin also has travel code.



---



\## 🧪 Development



\- Standalone plugin file: `nomadachi.py`

\- Class implements standard Pwnagotchi plugin hooks: `on\_loaded`, `on\_ui\_setup`, `on\_ui\_update`, `on\_handshake`

\- Thread‑safe JSON persistence with a lock

\- Zero network dependencies; works fully offline



---



\## 📄 License



MIT



---



\*\*Author:\*\* Strato (mediacutlet)\\

\*\*Credits:\*\* Age/Travel experiments and tuning with ChatGPT assist





