# Nomadachi

A Pwnagotchi plugin that turns roaming into a game. **Nomadachi** tracks the unique places your gotchi discovers and awards XP for exploration. It shows a compact travel title + place count on the UI, e.g.:

```
Trav Homebody (2pl)
```

---

## ✨ Features

* **Places counter** — counts unique places discovered (GPS grid cells or band-only fallback)
* **Travel XP** — awards XP for first-time encounters (ESSIDs, BSSIDs, OUIs, bands, places)
* **Titles** — unlock fun titles as XP increases (configurable thresholds)
* **Minimal UI** — one tidy line: `Trav <title> (<places>pl)`
* **Persistent** — progress is saved to disk and restored on boot
* **Migration** — can import travel stats from the Age plugin

---

## 🛠 Installation

1. **Copy the plugin file to your Pwnagotchi**

   Place `nomadachi.py` at:

   ```
   /usr/local/share/pwnagotchi/custom-plugins/nomadachi.py
   ```

2. **Enable it in `/etc/pwnagotchi/config.toml`** (flat key style like your other plugins)

   ```toml
   # Nomadachi (minimal)
   main.plugins.nomadachi.enabled = true
   main.plugins.nomadachi.x = 92      # UI X (pixels)
   main.plugins.nomadachi.y = 74      # UI Y (pixels)

   # Optional tuning (safe defaults if omitted)
   main.plugins.nomadachi.strict_nogps_places = true
   main.plugins.nomadachi.travel_grid = 0.01
   # main.plugins.nomadachi.format = "{title} ({places}pl)"
   # main.plugins.nomadachi.xp_essid = 2
   # main.plugins.nomadachi.xp_bssid = 1
   # main.plugins.nomadachi.xp_oui   = 1
   # main.plugins.nomadachi.xp_band  = 2
   # main.plugins.nomadachi.xp_place = 10

   # (Rare) migration from Age plugin (only needed once)
   # main.plugins.nomadachi.migrate_from_age = true

   # (Advanced) override title thresholds (XP → Title)
   # main.plugins.nomadachi.titles."0" = "Homebody"
   # main.plugins.nomadachi.titles."200" = "Wanderling"
   # main.plugins.nomadachi.titles."600" = "City Stroller"
   # main.plugins.nomadachi.titles."1200" = "Road Warrior"
   # main.plugins.nomadachi.titles."2400" = "Jetsetter"
   # main.plugins.nomadachi.titles."4800" = "Globetrotter"
   ```

3. **Restart Pwnagotchi**

   ```bash
   sudo systemctl restart pwnagotchi
   sudo journalctl -u pwnagotchi -n 120 --no-pager
   ```

---

## 🧭 How it works

**Places**

* With **GPS**: Nomadachi quantizes latitude/longitude to a grid (default `travel_grid = 0.01°`) and counts new grid cells as new places.
* Without GPS: the fallback is **band-only** (e.g., `nogps-2.4`, `nogps-5`, `nogps-6`), preventing a dense neighborhood from creating many “places.”

**Travel XP** *(first-time encounters per handshake)*

* +`xp_essid` for a **new ESSID**
* +`xp_bssid` for a **new BSSID**
* +`xp_oui` for a **new vendor OUI** (first 3 MAC bytes)
* +`xp_band` for a **new band** (2.4/5/6 GHz)
* +`xp_place` for a **new place**

Titles change as your **total XP** crosses configured thresholds.

---

## 🖥 UI

Nomadachi renders a compact line on the display. Default format:

```
Trav <title> (<places>pl)
```

Customize via `format` in the config (available tokens: `{title}`, `{level}`, `{places}`).

---

## 💾 Persistence

Data is stored at:

```
/root/pwn_traveler.json
```

Delete this file to reset your progress (Nomadachi will recreate it).

---

## 🔁 Migrating from the Age plugin

If you previously used an Age plugin variant with travel fields, Nomadachi can import from:

```
/root/age_strength.json
```

Set `migrate_from_age = true` (default) and keep that file present for the first run.

---

## 🔧 Tips & Tuning

* **Make "places" denser:** decrease `travel_grid` (e.g., `0.005` ≈ \~550 m).
* **Slow down rank ups:** reduce XP values and/or raise title thresholds.
* **Disable fallback liberal places:** keep `strict_nogps_places = true`.
* **Disable Nomadachi travel in Age:** set `main.plugins.age.enable_travel = false` if your Age plugin also has travel code.

---

## 🧪 Development

* Standalone plugin file: `nomadachi.py`
* Class implements standard Pwnagotchi plugin hooks: `on_loaded`, `on_ui_setup`, `on_ui_update`, `on_handshake`
* Thread-safe JSON persistence with a lock
* Zero network dependencies; works fully offline

---

## 📄 License

MIT License

Copyright (c) 2025 MediaCutlet (Strato Doumanis)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
