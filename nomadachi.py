"""
Traveler Plugin (Standalone)
===========================
Version: 1.0.0
Author: MediaCutlet (Strato) with ChatGPT assist
License: MIT

Purpose
-------
A lightweight, standalone plugin that gamifies *travel/novelty* separately
from Age/Strength. It awards Traveler XP for first‑time encounters (ESSIDs,
BSSIDs, OUIs, bands) and discovering new "places". It renders a compact UI
line that defaults to:

  Trav <title> (<places>pl)

Install
-------
Save as:
  /usr/local/share/pwnagotchi/custom-plugins/traveler.py

Then:
  sudo systemctl restart pwnagotchi
  journalctl -u pwnagotchi -n 120 --no-pager

Config (add to /etc/pwnagotchi/config.toml)
-------------------------------------------
# Enable plugin
main.plugins.traveler.enabled = true

# UI position
main.plugins.traveler.x = 10
main.plugins.traveler.y = 118

# GPS grid size in degrees (0.01 ≈ 1.1 km)
main.plugins.traveler.travel_grid = 0.01

# Without GPS, collapse places by band only (nogps-2.4 / nogps-5 / nogps-6)
# This prevents a dense neighborhood from minting many "places".
main.plugins.traveler.strict_nogps_places = true

# XP tuning (defaults shown)
main.plugins.traveler.xp_essid = 2
main.plugins.traveler.xp_bssid = 1
main.plugins.traveler.xp_oui   = 1
main.plugins.traveler.xp_band  = 2
main.plugins.traveler.xp_place = 10

# Title thresholds (XP → Title)
# You can override this whole table; keys must be strings in TOML
# e.g., main.plugins.traveler.titles."0" = "Homebody"
#       main.plugins.traveler.titles."200" = "Wanderling"

# UI format: default "{title} ({places}pl)"
# Available tokens: {title}, {level}, {places}
main.plugins.traveler.format = "{title} ({places}pl)"

# One‑time migration from Age plugin's /root/age_strength.json travel fields
main.plugins.traveler.migrate_from_age = true

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
    __version__ = '1.0.0'
    __license__ = 'MIT'
    __description__ = (
        'Standalone travel/novelty progression. Tracks places and awards XP for firsts '
        '(ESSID/BSSID/OUI/band/place). Compact UI: "Trav <title> (<places>pl)".'
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

        # Migration
        self.migrate_from_age = True

    # --------------------------- Lifecycle ---------------------------
    def on_loaded(self):
        # Read config
        self.ui_x = int(self.options.get('x', self.ui_x))
        self.ui_y = int(self.options.get('y', self.ui_y))
        self.travel_grid = float(self.options.get('travel_grid', self.travel_grid))
        self.strict_nogps_places = bool(self.options.get('strict_nogps_places', self.strict_nogps_places))
        self.xp_essid = int(self.options.get('xp_essid', self.xp_essid))
        self.xp_bssid = int(self.options.get('xp_bssid', self.xp_bssid))
        self.xp_oui = int(self.options.get('xp_oui', self.xp_oui))
        self.xp_band = int(self.options.get('xp_band', self.xp_band))
        self.xp_place = int(self.options.get('xp_place', self.xp_place))
        self.ui_format = str(self.options.get('format', self.ui_format))
        self.migrate_from_age = bool(self.options.get('migrate_from_age', self.migrate_from_age))

        # Titles override from TOML table
        titles_opt = self.options.get('titles')
        if isinstance(titles_opt, dict):
            try:
                # keys are strings in TOML, convert to int
                self.titles = {int(k): str(v) for k, v in titles_opt.items()}
            except Exception as e:
                logging.error(f"[Traveler] invalid titles in config: {e}")

        self.load()

        if self.migrate_from_age:
            self._try_migrate_from_age_json()

    def on_ui_setup(self, ui):
        ui.add_element('TravelStat', LabeledValue(
            color=BLACK,
            label='Trav',
            value="",
            position=(self.ui_x, self.ui_y),
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
            logging.error(f"[Traveler] on_handshake error: {e}")

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
            logging.error(f"[Traveler] load error: {e}")

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
                logging.error(f"[Traveler] save error: {e}")

    # --------------------------- Helpers ---------------------------
    def _add_xp(self, xp):
        if xp <= 0:
            return
        self.travel_xp += int(xp)
        old = self.travel_level
        self._recalc_level()
        if self.travel_level > old:
            logging.info(f"[Traveler] Level up → {self.get_title()} (L{self.travel_level}, XP={self.travel_xp})")

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
            logging.info("[Traveler] Migrated travel data from age_strength.json")
            self.save()
