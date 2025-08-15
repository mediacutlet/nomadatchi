"""
Nomadachi (Traveler plugin, standalone)
======================================
Version: 1.1.1
Author: MediaCutlet (Strato)
License: MIT

Purpose
-------
A lightweight, standalone plugin that gamifies *travel/novelty* separately
from Age/Strength. It awards Traveler XP for first‑time encounters (ESSIDs,
BSSIDs, OUIs, bands) and discovering new "places". It renders a compact UI
line that defaults to:

  Trav <title> (<places>pl)

This version adds an optional **progress bar** for the next Traveler title.

Install
-------
Save as:
  /usr/local/share/pwnagotchi/custom-plugins/nomadachi.py

Then:
  sudo systemctl restart pwnagotchi
  journalctl -u pwnagotchi -n 120 --no-pager

Flat-key Config (add to /etc/pwnagotchi/config.toml)
---------------------------------------------------
# Enable plugin
main.plugins.nomadachi.enabled = true

# UI position
main.plugins.nomadachi.x = 92
main.plugins.nomadachi.y = 74

# GPS grid size in degrees (0.01 ≈ 1.1 km)
main.plugins.nomadachi.travel_grid = 0.01

# Without GPS, collapse places by band only (nogps-2.4 / nogps-5 / nogps-6)
# This prevents a dense neighborhood from minting many "places".
main.plugins.nomadachi.strict_nogps_places = true

# XP tuning (defaults shown)
main.plugins.nomadachi.xp_essid = 2
main.plugins.nomadachi.xp_bssid = 1
main.plugins.nomadachi.xp_oui   = 1
main.plugins.nomadachi.xp_band  = 2
main.plugins.nomadachi.xp_place = 10

# UI format: default "{title} ({places}pl)"
# Available tokens: {title}, {level}, {places}
main.plugins.nomadachi.format = "{title} ({places}pl)"

# Progress bar (optional)
main.plugins.nomadachi.show_progress = true
main.plugins.nomadachi.progress_x = 0      # defaults to x
main.plugins.nomadachi.progress_y = 74      # defaults to y-10
main.plugins.nomadachi.progress_len = 5     # bar cells
main.plugins.nomadachi.progress_fill = "▥"  # one character

# One‑time migration from Age plugin's /root/age_strength.json travel fields
main.plugins.nomadachi.migrate_from_age = true

Notes
-----
- This plugin is independent of Age: you can disable the Age plugin's travel
  code (if you merged it there) by setting `main.plugins.age.enable_travel = false`.
- Persistence lives at /root/pwn_traveler.json.
- No decay. Safe to run alongside Age.
"""

import os
import json
import logging
import threading

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK


class Traveler(plugins.Plugin):
    __author__ = 'MediaCutlet (Strato)'
    __version__ = '1.1.1'
    __license__ = 'MIT'
    __description__ = (
        'Standalone travel/novelty progression. Tracks places and awards XP for firsts '
        '(ESSID/BSSID/OUI/band/place). Compact UI: "Nomad <title> (<places>pl)" '
        'plus an optional progress bar toward the next Traveler title.'
    )

    DEFAULT_TITLES = {
        0: "Homebody",
        200: "Wanderling",
        600: "City Stroller",
        1200: "Road Warrior",
        2400: "Jetsetter",
        4800: "Globetrotter",
    }

    def __init__(self):
        # State & persistence
        self.data_path = '/root/pwn_traveler.json'
        self.data_lock = threading.Lock()

        # XP and novelty sets
        self.travel_xp = 0
        self.travel_level = 0
        self.titles = dict(self.DEFAULT_TITLES)
        self.unique_essids = set()
        self.unique_bssids = set()
        self.unique_ouis = set()
        self.unique_bands = set()
        self.place_hashes = set()
        self.last_place_hash = None

        # XP tuning
        self.xp_essid = 2
        self.xp_bssid = 1
        self.xp_oui = 1
        self.xp_band = 2
        self.xp_place = 10

        # GPS/places
        self.travel_grid = 0.01
        self.strict_nogps_places = True
        self.gps_candidate_paths = [
            "/tmp/pwnagotchi-gps.json",
            "/tmp/gps.json",
            "/root/.pwnagotchi-gps.json",
            "/var/run/pwnagotchi/gps.json",
        ]

        # UI
        self.ui_x = 10
        self.ui_y = 118
        self.ui_format = "{title} ({places}pl)"  # tokens: {title},{level},{places}

        # Progress bar UI (new)
        self.show_progress = True
        self.progress_x = None
        self.progress_y = None
        self.progress_len = 5
        self.progress_fill = '▥'

        # Migration
        self.migrate_from_age = True

    # --------------------------- Lifecycle ---------------------------
    def on_loaded(self):
        # Read config
        # Support aliases traveler_x/y for consistency with Age if desired
        self.ui_x = int(self.options.get('x', self.options.get('traveler_x', self.ui_x)))
        self.ui_y = int(self.options.get('y', self.options.get('traveler_y', self.ui_y)))
        self.travel_grid = float(self.options.get('travel_grid', self.travel_grid))
        self.strict_nogps_places = bool(self.options.get('strict_nogps_places', self.strict_nogps_places))
        self.xp_essid = int(self.options.get('xp_essid', self.xp_essid))
        self.xp_bssid = int(self.options.get('xp_bssid', self.xp_bssid))
        self.xp_oui = int(self.options.get('xp_oui', self.xp_oui))
        self.xp_band = int(self.options.get('xp_band', self.xp_band))
        self.xp_place = int(self.options.get('xp_place', self.xp_place))
        self.ui_format = str(self.options.get('format', self.ui_format))
        self.migrate_from_age = bool(self.options.get('migrate_from_age', self.migrate_from_age))

        # Progress bar options (defaults: one row above the Trav line)
        self.show_progress = bool(self.options.get('show_progress', self.show_progress))
        self.progress_x = int(self.options.get('progress_x', self.ui_x))
        self.progress_y = int(self.options.get('progress_y', max(0, self.ui_y - 10)))
        self.progress_len = int(self.options.get('progress_len', self.progress_len))
        self.progress_fill = str(self.options.get('progress_fill', self.progress_fill))[:1]

        # Titles override from TOML table
        titles_opt = self.options.get('titles')
        if isinstance(titles_opt, dict):
            try:
                # keys are strings in TOML, convert to int
                self.titles = {int(k): str(v) for k, v in titles_opt.items()}
            except Exception as e:
                logging.error(f"[Nomadachi] invalid titles in config: {e}")

        self.load()

        if self.migrate_from_age:
            self._try_migrate_from_age_json()

    def on_ui_setup(self, ui):
        ui.add_element('TravelStat', LabeledValue(
            color=BLACK,
            label='Nomad',
            value="",
            position=(self.ui_x, self.ui_y),
            label_font=fonts.Bold,
            text_font=fonts.Medium,
        ))

        if self.show_progress:
            ui.add_element('TravelProg', LabeledValue(
                color=BLACK,
                label='Trav ',
                value='|     |',
                position=(self.progress_x, self.progress_y),
                label_font=fonts.Bold,
                text_font=fonts.Medium,
            ))

    def on_ui_update(self, ui):
        title = self.get_title()
        places = len(self.place_hashes)
        level = self.travel_level
        try:
            text = self.ui_format.format(title=title, places=places, level=level)
        except Exception:
            text = f"{title} ({places}pl)"
        ui.set('TravelStat', text)

        if self.show_progress:
            prev_t, next_t = self._prev_next_thresholds()
            if next_t is None:
                ui.set('TravelProg', '[MAX]')
            else:
                base = 0 if prev_t is None else prev_t
                span = max(1, next_t - base)
                prog = max(0.0, min(1.0, (self.travel_xp - base) / span))
                filled = int(prog * self.progress_len)
                bar = '|' + (self.progress_fill * filled) + (' ' * (self.progress_len - filled)) + '|'
                ui.set('TravelProg', bar)

    # ---------------------------- Events ----------------------------
    def on_handshake(self, agent, *args):
        try:
            if len(args) < 3:
                return
            ap = args[2]
            if not isinstance(ap, dict):
                return

            essid = ap.get('essid', 'unknown')
            bssid = (ap.get('bssid') or '').lower()
            oui = ':'.join(bssid.split(':')[:3]) if bssid and ':' in bssid else None
            channel = ap.get('channel', '0')
            band = self._channel_to_band(channel)

            gained = 0
            # firsts only
            if essid not in self.unique_essids:
                self.unique_essids.add(essid)
                gained += self.xp_essid
            if bssid and bssid not in self.unique_bssids:
                self.unique_bssids.add(bssid)
                gained += self.xp_bssid
            if oui and oui not in self.unique_ouis:
                self.unique_ouis.add(oui)
                gained += self.xp_oui
            if band and band not in self.unique_bands:
                self.unique_bands.add(band)
                gained += self.xp_band

            place = self._compute_place_hash(ap)
            if place not in self.place_hashes:
                self.place_hashes.add(place)
                self.last_place_hash = place
                gained += self.xp_place
                try:
                    agent.view().set('status', "New place discovered!")
                except Exception:
                    pass

            if gained > 0:
                self._add_xp(gained)
                self.save()
        except Exception as e:
            logging.error(f"[Nomadachi] on_handshake error: {e}")

    # ------------------------- Persistence -------------------------
    def load(self):
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as f:
                    d = json.load(f)
                self.travel_xp = int(d.get('travel_xp', 0))
                self.travel_level = int(d.get('travel_level', 0))
                self.unique_essids = set(d.get('unique_essids', []))
                self.unique_bssids = set(d.get('unique_bssids', []))
                self.unique_ouis = set(d.get('unique_ouis', []))
                self.unique_bands = set(d.get('unique_bands', []))
                self.place_hashes = set(d.get('place_hashes', []))
                self.last_place_hash = d.get('last_place_hash', None)
        except Exception as e:
            logging.error(f"[Nomadachi] load error: {e}")

    def save(self):
        payload = {
            'travel_xp': self.travel_xp,
            'travel_level': self.travel_level,
            'unique_essids': list(self.unique_essids),
            'unique_bssids': list(self.unique_bssids),
            'unique_ouis': list(self.unique_ouis),
            'unique_bands': list(self.unique_bands),
            'place_hashes': list(self.place_hashes),
            'last_place_hash': self.last_place_hash,
        }
        with self.data_lock:
            try:
                with open(self.data_path, 'w') as f:
                    json.dump(payload, f, indent=2)
            except Exception as e:
                logging.error(f"[Nomadachi] save error: {e}")

    # --------------------------- Helpers ---------------------------
    def _add_xp(self, xp):
        if xp <= 0:
            return
        self.travel_xp += int(xp)
        old = self.travel_level
        self._recalc_level()
        if self.travel_level > old:
            logging.info(f"[Nomadachi] Level up → {self.get_title()} (L{self.travel_level}, XP={self.travel_xp})")

    def _recalc_level(self):
        lvl = 0
        for t in sorted(self.titles.keys()):
            if self.travel_xp >= t:
                lvl += 1
        self.travel_level = max(0, lvl - 1)

    def get_title(self):
        for t in sorted(self.titles.keys(), reverse=True):
            if self.travel_xp >= t:
                return self.titles[t]
        return self.titles.get(0, "Homebody")

    def _prev_next_thresholds(self):
        """Return (prev_threshold, next_threshold) surrounding current XP."""
        keys = sorted(self.titles.keys())
        prev_t = None
        for t in keys:
            if self.travel_xp < t:
                return (prev_t, t)
            prev_t = t
        return (prev_t, None)  # at/above max tier

    def _channel_to_band(self, channel):
        try:
            ch = int(channel)
        except Exception:
            return 'unk'
        if 1 <= ch <= 14:
            return '2.4'
        if (32 <= ch <= 173) or ch in (36, 40, 44, 48, 149, 153, 157, 161, 165):
            return '5'
        if 1 <= ch - 191 <= 59:
            return '6'
        return 'unk'

    def _try_read_gps(self):
        for p in self.gps_candidate_paths:
            try:
                if os.path.exists(p):
                    with open(p, 'r') as f:
                        j = json.load(f)
                        lat = j.get('lat', None)
                        lon = j.get('lon', None)
                        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                            return (lat, lon)
            except Exception:
                continue
        return None

    def _quantize_ll(self, lat, lon):
        g = self.travel_grid
        qlat = round(lat / g) * g
        qlon = round(lon / g) * g
        return f"{qlat:.4f}:{qlon:.4f}"

    def _compute_place_hash(self, ap):
        gps = self._try_read_gps()
        if gps is not None:
            return self._quantize_ll(gps[0], gps[1])

        # Fallback: strict band-only or legacy OUI+band+channel
        ch = ap.get('channel', '0')
        band = self._channel_to_band(ch)
        if self.strict_nogps_places:
            return f"nogps-{band}"
        else:
            bssid = (ap.get('bssid') or '').lower()
            oui = ':'.join(bssid.split(':')[:3]) if bssid and ':' in bssid else 'no:ou:i'
            return f"{oui}-{band}-{ch}"

    # -------------------------- Migration --------------------------
    def _try_migrate_from_age_json(self):
        """Copy travel fields from /root/age_strength.json if present (non-destructive)."""
        src = '/root/age_strength.json'
        if not os.path.exists(src):
            return
        try:
            with open(src, 'r') as f:
                d = json.load(f)
        except Exception:
            return

        mutated = False
        # Map known keys from the merged Age plugin
        key_map = {
            'travel_xp': 'travel_xp',
            'travel_level': 'travel_level',
            'unique_essids': 'unique_essids',
            'unique_bssids': 'unique_bssids',
            'unique_ouis': 'unique_ouis',
            'unique_channels': None,  # not used here
            'unique_bands': 'unique_bands',
            'place_hashes': 'place_hashes',
            'last_place_hash': 'last_place_hash',
        }
        for src_k, dst_k in key_map.items():
            if dst_k is None:
                continue
            if src_k in d and not getattr(self, dst_k):
                val = d[src_k]
                if isinstance(getattr(self, dst_k), set):
                    try:
                        getattr(self, dst_k).update(set(val))
                    except Exception:
                        pass
                else:
                    setattr(self, dst_k, val)
                mutated = True

        if mutated:
            logging.info("[Nomadachi] Migrated travel data from age_strength.json")
            self.save()
