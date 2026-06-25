#!/usr/bin/env python3
"""Roue des Élèves — Sélecteur aléatoire pour le tableau (thème doré)"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json, random, math, os
from datetime import datetime

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.json")
HISTORY_FILE  = os.path.join(BASE_DIR, "history.json")

# ── Palette ambrée ────────────────────────────────────────────────────────
RAMP = [
    "#F2CE7E", "#B27A2E", "#E6AE4C", "#8A5C22",
    "#EFDCAB", "#C68C38", "#D99B3A", "#A8702A",
]

def _lighten(hex_col, factor=0.28):
    h = hex_col.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02X}{g:02X}{b:02X}"

RAMP_LT = [_lighten(c) for c in RAMP]

BG         = "#0E1116"
PNL        = "#13171E"
SEP        = "#1F2630"
FIELD      = "#181D25"
MUTED      = "#2A323D"
GOLD       = "#EAB44E"
GOLD_DK    = "#D99B33"
GOLD_LT    = "#F2C964"
GOLD_BADGE = "#211B0E"
TXT        = "#E8ECF2"
TXT_MUT    = "#9AA4B2"
TXT_DIM    = "#6B7480"
CALLED_BG  = "#1C2230"
CALLED_TXT = "#4A5568"
FLASH_COL  = "#FFE09A"
WIN_COL    = "#F4C766"
SUCCESS    = "#5CB85C"


# ── Persistence ───────────────────────────────────────────────────────────

def load_students():
    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {"demi_groupe_1": [], "demi_groupe_2": []}
    save_students(data)
    return data

def save_students(data):
    with open(STUDENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── Application principale ────────────────────────────────────────────────

class WheelApp:
    W        = 520   # taille canvas
    FPS      = 14    # ms par frame
    DECEL    = 0.975 # décélération
    STOP_SPD = 0.08  # seuil d'arrêt (°/frame)
    ACCEL_N  = 16    # frames d'accélération
    FLASH_N  = 8     # cycles de flash
    # Somme sinusoïdale pour la formule v0 (calculée après définition de ACCEL_N)
    _ACCEL_SUM = None  # initialisé après la classe

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Roue des Élèves")
        root.configure(bg=BG)
        root.geometry("1150x760")
        root.minsize(960, 640)

        self.students    = load_students()
        self.history     = load_history()
        self.mode        = tk.StringVar(value="classe_entiere")
        self.spinning    = False
        self.angle       = 0.0
        self.speed       = 0.0
        self.flash_idx   = None
        self.flash_on    = False
        self.flash_cnt   = 0
        self._pending    = None
        self._winner_idx = None
        self._snap_angle = None
        self._accel_v0   = 0.0

        self._build_ui()
        self._refresh()
        root.bind("<space>",  lambda e: self._spin())
        root.bind("<Escape>", lambda e: self._ignore_record())

    # ── helpers ───────────────────────────────────────────────────────────

    def current_students(self):
        m  = self.mode.get()
        g1 = self.students.get("demi_groupe_1", [])
        g2 = self.students.get("demi_groupe_2", [])
        if m == "demi_groupe_1": return list(g1)
        if m == "demi_groupe_2": return list(g2)
        return list(g1) + list(g2)

    def called_set(self, mode=None):
        m = mode if mode is not None else self.mode.get()
        return {e["student"] for e in self.history if e.get("mode") == m}

    def mode_name(self, m=None):
        return {"classe_entiere": "Classe entière",
                "demi_groupe_1":  "Demi-groupe 1",
                "demi_groupe_2":  "Demi-groupe 2"}.get(m or self.mode.get(), "")

    def mode_abbr(self, m):
        return {"classe_entiere": "CE",
                "demi_groupe_1":  "G1",
                "demi_groupe_2":  "G2"}.get(m, "?")

    def _hover(self, btn, bg_on, fg_on, bg_off, fg_off):
        def _enter(e):
            if str(btn.cget("state")) != "disabled":
                btn.config(bg=bg_on, fg=fg_on)
        def _leave(e):
            if str(btn.cget("state")) != "disabled":
                btn.config(bg=bg_off, fg=fg_off)
        btn.bind("<Enter>", _enter)
        btn.bind("<Leave>", _leave)

    # ── construction UI ───────────────────────────────────────────────────

    def _build_ui(self):
        # En-tête ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg="#0A0D12")
        hdr.pack(fill=tk.X)
        hdr_inner = tk.Frame(hdr, bg="#0A0D12")
        hdr_inner.pack(fill=tk.X, padx=22, pady=13)

        logo_c = tk.Canvas(hdr_inner, width=42, height=42, bg="#0A0D12",
                           highlightthickness=0)
        logo_c.pack(side=tk.LEFT)
        logo_c.create_oval(1, 1, 41, 41, fill=GOLD_DK, outline=GOLD_LT, width=2)
        logo_c.create_oval(6, 6, 36, 36, fill="", outline="#0A0D12", width=3)
        logo_c.create_oval(13, 13, 29, 29, fill=GOLD_LT, outline="")
        logo_c.create_oval(18, 18, 24, 24, fill="#0A0D12", outline="")

        title_f = tk.Frame(hdr_inner, bg="#0A0D12")
        title_f.pack(side=tk.LEFT, padx=(12, 0))
        tk.Label(title_f, text="Roue des Élèves",
                 font=("Arial", 19, "bold"), bg="#0A0D12", fg=TXT).pack(anchor=tk.W)
        tk.Label(title_f, text="Sélecteur aléatoire",
                 font=("Arial", 10), bg="#0A0D12", fg=TXT_DIM).pack(anchor=tk.W)

        badge_f = tk.Frame(hdr_inner, bg=FIELD, padx=12, pady=7,
                           highlightthickness=1,
                           highlightbackground=MUTED, highlightcolor=MUTED)
        badge_f.pack(side=tk.RIGHT)
        tk.Label(badge_f, text="●", font=("Arial", 8),
                 bg=FIELD, fg=GOLD).pack(side=tk.LEFT)
        tk.Label(badge_f, text=" Créé par ",
                 font=("Arial", 10), bg=FIELD, fg=TXT_MUT).pack(side=tk.LEFT)
        tk.Label(badge_f, text="Élie",
                 font=("Arial", 10, "bold"), bg=FIELD, fg=GOLD).pack(side=tk.LEFT)

        # Séparateur doré
        tk.Frame(self.root, bg=GOLD_DK, height=2).pack(fill=tk.X)

        # Corps ────────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Panneau gauche ───────────────────────────────────────────────────
        left = tk.Frame(body, bg=PNL,
                        highlightthickness=1,
                        highlightbackground=SEP, highlightcolor=SEP)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)
        left.config(width=226)

        self._section_title(left, "MODE")
        self._hsep(left)

        self.mode_btns = {}
        for lbl, val in [("Classe entière", "classe_entiere"),
                         ("Demi-groupe 1",  "demi_groupe_1"),
                         ("Demi-groupe 2",  "demi_groupe_2")]:
            btn = tk.Button(left, text=lbl,
                            font=("Arial", 11, "bold"), relief=tk.FLAT,
                            cursor="hand2", anchor=tk.W, padx=12, pady=9,
                            activebackground=GOLD_DK, activeforeground="#1A1206",
                            command=lambda v=val: self._set_mode(v))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.mode_btns[val] = btn

        self._hsep(left)
        self._section_title(left, "STATISTIQUES")
        self._hsep(left)

        # 3 cartes statistiques
        stats_row = tk.Frame(left, bg=PNL)
        stats_row.pack(fill=tk.X, padx=10)
        self._stat_cards = {}
        for col, (key, label, color) in enumerate([
            ("total",     "Total",    TXT),
            ("passed",    "Passés",   GOLD),
            ("remaining", "Restants", TXT_MUT),
        ]):
            card = tk.Frame(stats_row, bg=FIELD, padx=6, pady=10)
            card.grid(row=0, column=col, padx=3, sticky="nsew")
            stats_row.columnconfigure(col, weight=1)
            num = tk.Label(card, text="0",
                           font=("Courier", 18, "bold"), bg=FIELD, fg=color)
            num.pack()
            tk.Label(card, text=label,
                     font=("Arial", 9), bg=FIELD, fg=TXT_DIM).pack()
            self._stat_cards[key] = num

        # Barre de progression
        prog_row = tk.Frame(left, bg=PNL)
        prog_row.pack(fill=tk.X, padx=10, pady=(10, 0))
        prog_labels = tk.Frame(prog_row, bg=PNL)
        prog_labels.pack(fill=tk.X)
        self._prog_mode_lbl = tk.Label(prog_labels, font=("Arial", 9),
                                       bg=PNL, fg=TXT_DIM, anchor=tk.W)
        self._prog_mode_lbl.pack(side=tk.LEFT)
        self._prog_pct_lbl = tk.Label(prog_labels, font=("Arial", 9),
                                      bg=PNL, fg=TXT_DIM, anchor=tk.E)
        self._prog_pct_lbl.pack(side=tk.RIGHT)
        self._prog_canvas = tk.Canvas(left, height=8, bg=MUTED,
                                      highlightthickness=0)
        self._prog_canvas.pack(fill=tk.X, padx=10, pady=(4, 0))

        # Bannière "Tous passés !"
        self._all_done_frame = tk.Frame(left, bg=PNL)
        tk.Label(self._all_done_frame,
                 text="Tous les élèves sont passés !",
                 font=("Arial", 9, "bold"), bg=PNL, fg=SUCCESS,
                 wraplength=190, justify=tk.CENTER).pack(pady=(8, 4))
        btn_rd = tk.Button(self._all_done_frame, text="Réinitialiser",
                           bg=GOLD_DK, fg="#1A1206",
                           font=("Arial", 9, "bold"), relief=tk.FLAT,
                           cursor="hand2", padx=10, pady=5,
                           activebackground=GOLD_LT, activeforeground="#0A0800",
                           command=self._reset_history)
        btn_rd.pack(pady=(0, 8))
        self._hover(btn_rd, GOLD_LT, "#0A0800", GOLD_DK, "#1A1206")

        self._hsep(left)

        # Boutons d'action
        for txt, bg_c, fg_c, hbg, hfg, cmd in [
            ("✦  Gérer les élèves",         GOLD_DK, "#1A1206", GOLD_LT, "#0A0800", self._manage_students),
            ("≡  Voir l'historique",        FIELD,   TXT_MUT,  MUTED,   TXT,       self._show_history),
            ("↺  Réinitialiser historique", FIELD,   TXT_DIM,  MUTED,   TXT_MUT,   self._reset_history),
        ]:
            btn = tk.Button(left, text=txt, bg=bg_c, fg=fg_c,
                            font=("Arial", 10, "bold"), relief=tk.FLAT,
                            cursor="hand2", anchor=tk.W, padx=12, pady=9,
                            activebackground=hbg, activeforeground=hfg,
                            command=cmd)
            btn.pack(fill=tk.X, padx=10, pady=2)
            self._hover(btn, hbg, hfg, bg_c, fg_c)

        self._update_mode_buttons()

        # Centre ───────────────────────────────────────────────────────────
        center = tk.Frame(body, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, width=self.W, height=self.W,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        # Zone résultat
        result_area = tk.Frame(center, bg=BG, height=96)
        result_area.pack(fill=tk.X)
        result_area.pack_propagate(False)

        self.result_name_var = tk.StringVar(value="")
        self.result_sub_var  = tk.StringVar(value="Appuyez sur Tourner !")

        self.result_name_lbl = tk.Label(result_area,
                                        textvariable=self.result_name_var,
                                        font=("Arial", 20, "bold"),
                                        bg=BG, fg=GOLD_LT)
        self.result_sub_lbl = tk.Label(result_area,
                                       textvariable=self.result_sub_var,
                                       font=("Arial", 12),
                                       bg=BG, fg=TXT_DIM, wraplength=480)
        self.result_sub_lbl.pack(pady=(10, 0))

        # Boutons de confirmation
        self.confirm_frame = tk.Frame(result_area, bg=BG)
        btn_inner = tk.Frame(self.confirm_frame, bg=BG)
        btn_inner.pack()
        self.btn_confirm = tk.Button(
            btn_inner, text="✓  Noter le passage",
            bg=GOLD_DK, fg="#1A1206",
            font=("Arial", 11, "bold"), relief=tk.FLAT,
            cursor="hand2", padx=16, pady=8,
            activebackground=GOLD_LT, activeforeground="#0A0800",
            command=self._confirm_record)
        self.btn_confirm.pack(side=tk.LEFT, padx=6)
        self._hover(self.btn_confirm, GOLD_LT, "#0A0800", GOLD_DK, "#1A1206")

        btn_ign = tk.Button(
            btn_inner, text="Ignorer  [Échap]",
            bg=FIELD, fg=TXT_MUT,
            font=("Arial", 11), relief=tk.FLAT,
            cursor="hand2", padx=16, pady=8,
            activebackground=MUTED, activeforeground=TXT,
            command=self._ignore_record)
        btn_ign.pack(side=tk.LEFT, padx=6)
        self._hover(btn_ign, MUTED, TXT, FIELD, TXT_MUT)

        self.spin_btn = tk.Button(
            center, text="▶  TOURNER",
            font=("Arial", 15, "bold"),
            bg=GOLD_DK, fg="#1A1206",
            relief=tk.FLAT, cursor="hand2",
            padx=36, pady=13,
            activebackground=GOLD_LT, activeforeground="#0A0800",
            command=self._spin)
        self.spin_btn.pack(pady=6)
        self._hover(self.spin_btn, GOLD_LT, "#0A0800", GOLD_DK, "#1A1206")

        tk.Label(center, text="ou appuyez sur  [Espace]",
                 font=("Arial", 9), bg=BG, fg=TXT_DIM).pack()

        # Panneau droit ────────────────────────────────────────────────────
        right = tk.Frame(body, bg=PNL,
                         highlightthickness=1,
                         highlightbackground=SEP, highlightcolor=SEP)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)
        right.config(width=212)

        self._section_title(right, "DERNIERS PASSAGES")
        self._hsep(right)

        lf = tk.Frame(right, bg=PNL)
        lf.pack(fill=tk.BOTH, expand=True, padx=6)
        sb = tk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_lb = tk.Listbox(
            lf, bg=BG, fg=TXT,
            font=("Courier", 10), yscrollcommand=sb.set,
            selectbackground=GOLD_DK, selectforeground="#1A1206",
            relief=tk.FLAT, highlightthickness=0, activestyle="none")
        self.hist_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.hist_lb.yview)

    # ── mode ──────────────────────────────────────────────────────────────

    def _set_mode(self, val):
        if self.spinning: return
        self.mode.set(val)
        self._update_mode_buttons()
        self._clear_result()
        self._refresh()

    def _update_mode_buttons(self):
        g1     = self.students.get("demi_groupe_1", [])
        g2     = self.students.get("demi_groupe_2", [])
        called = self.called_set()
        counts = {
            "classe_entiere": len(g1) + len(g2),
            "demi_groupe_1":  len(g1),
            "demi_groupe_2":  len(g2),
        }
        called_counts = {
            "classe_entiere": sum(1 for s in g1+g2 if s in self.called_set("classe_entiere")),
            "demi_groupe_1":  sum(1 for s in g1 if s in self.called_set("demi_groupe_1")),
            "demi_groupe_2":  sum(1 for s in g2 if s in self.called_set("demi_groupe_2")),
        }
        labels = {
            "classe_entiere": "Classe entière",
            "demi_groupe_1":  "Demi-groupe 1",
            "demi_groupe_2":  "Demi-groupe 2",
        }
        active = self.mode.get()
        for val, btn in self.mode_btns.items():
            n   = counts[val]
            nc  = called_counts[val]
            lbl = labels[val]
            done = n > 0 and nc == n
            tag  = f"  ✓ {nc}/{n}" if done else f"  {nc}/{n}"
            if val == active:
                btn.config(bg=GOLD_DK, fg="#1A1206", text=f"{lbl}{tag}")
            else:
                btn.config(bg=FIELD,   fg=TXT_MUT,  text=f"{lbl}  ({n})")

    # ── dessin de la roue ─────────────────────────────────────────────────

    def _draw_wheel(self, hl_idx=None, hl_on=False):
        self.canvas.delete("all")
        students = self.current_students()
        called   = self.called_set()
        cx = cy  = self.W // 2
        R        = cx - 20
        R_in     = R - 18    # rayon du liseret intérieur
        HUB      = 28

        if not students:
            # Roue vide
            for r_off, col in [(0, "#1a2235"), (4, FIELD)]:
                self.canvas.create_oval(cx-R+r_off, cy-R+r_off,
                                        cx+R-r_off, cy+R-r_off,
                                        fill=col, outline=MUTED, width=2)
            self.canvas.create_text(cx, cy - 18,
                                    text="Aucun élève",
                                    font=("Arial", 15, "bold"),
                                    fill=TXT_MUT, justify=tk.CENTER)
            self.canvas.create_text(cx, cy + 18,
                                    text="Cliquez sur « Gérer les élèves »",
                                    font=("Arial", 11),
                                    fill=TXT_DIM, justify=tk.CENTER)
            self._draw_arrow(cx, cy, R)
            return

        n     = len(students)
        sweep = 360.0 / n

        # Halo d'ombre externe
        for offset, col, w in [(18, "#030508", 7), (11, "#06091a", 5), (5, "#0a1020", 3)]:
            self.canvas.create_oval(cx-R-offset, cy-R-offset,
                                    cx+R+offset, cy+R+offset,
                                    fill="", outline=col, width=w)

        # Bague externe métallique
        self.canvas.create_oval(cx-R-3, cy-R-3, cx+R+3, cy+R+3,
                                fill="", outline=MUTED, width=5)
        self.canvas.create_oval(cx-R-1, cy-R-1, cx+R+1, cy+R+1,
                                fill="", outline="#3a4555", width=1)

        for i, name in enumerate(students):
            start    = self.angle + i * sweep
            mid_deg  = start + sweep / 2.0
            is_called = name in called
            is_win    = (hl_idx == i)
            flashing  = is_win and hl_on

            if flashing:
                fill   = FLASH_COL
                fill_lt = FLASH_COL
            elif is_win:
                fill   = WIN_COL
                fill_lt = _lighten(WIN_COL, 0.3)
            elif is_called:
                fill   = CALLED_BG
                fill_lt = CALLED_BG
            else:
                fill   = RAMP[i % len(RAMP)]
                fill_lt = RAMP_LT[i % len(RAMP_LT)]

            sep_w = max(1, 3 - n // 10)

            # 1) Secteur clair (liseret intérieur visible au bord)
            if not is_called or is_win:
                self.canvas.create_arc(cx-R_in, cy-R_in, cx+R_in, cy+R_in,
                                       start=start, extent=sweep,
                                       fill=fill_lt, outline="", width=0)

            # 2) Secteur principal (laisse un anneau clair visible)
            inner_mask = R_in - 14
            self.canvas.create_arc(cx-inner_mask, cy-inner_mask,
                                   cx+inner_mask, cy+inner_mask,
                                   start=start, extent=sweep,
                                   fill=fill, outline="", width=0)
            self.canvas.create_arc(cx-R, cy-R, cx+R, cy+R,
                                   start=start, extent=sweep,
                                   fill=fill, outline=BG, width=sep_w)

            # 3) Bordure dorée si gagnant
            if is_win:
                self.canvas.create_arc(cx-R, cy-R, cx+R, cy+R,
                                       start=start, extent=sweep,
                                       fill="", outline=GOLD_LT, width=3)

            # 4) Texte rotatif
            mid_rad = math.radians(mid_deg)
            r_txt   = R * 0.65
            tx = cx + r_txt * math.cos(mid_rad)
            ty = cy - r_txt * math.sin(mid_rad)

            norm    = mid_deg % 360
            t_angle = (norm + 180) if 90 < norm < 270 else norm

            max_c  = max(4, int(13 - n / 5))
            label  = name if len(name) <= max_c else name[:max_c - 1] + "…"
            fsize  = max(6, min(12, int(190 / n)))
            tcolor = (CALLED_TXT if is_called and not (is_win or flashing)
                      else "#241906")

            self.canvas.create_text(tx + 1, ty + 1, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill="#03060c", angle=t_angle)
            self.canvas.create_text(tx, ty, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill=tcolor, angle=t_angle)

        # Bague intérieure de fermeture
        self.canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                                fill="", outline=BG, width=3)

        # Hub — 4 cercles concentriques
        self.canvas.create_oval(cx-HUB-8, cy-HUB-8, cx+HUB+8, cy+HUB+8,
                                fill="#07090E", outline=MUTED, width=2)
        self.canvas.create_oval(cx-HUB, cy-HUB, cx+HUB, cy+HUB,
                                fill="#12161E", outline=GOLD_DK, width=2)
        self.canvas.create_oval(cx-HUB+7, cy-HUB+7, cx+HUB-7, cy+HUB-7,
                                fill=FIELD, outline="")
        self.canvas.create_oval(cx-9, cy-9, cx+9, cy+9,
                                fill=GOLD, outline=GOLD_LT, width=2)
        self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3,
                                fill="#0A0D12", outline="")

        self._draw_arrow(cx, cy, R)

    def _draw_arrow(self, cx, cy, R):
        tip    = cy - R - 2
        base_y = cy - R - 38
        hw     = 16
        # Ombre portée
        self.canvas.create_polygon(cx-hw+3, base_y+3, cx+hw+3, base_y+3,
                                   cx+3, tip+3, fill="#03060C", outline="")
        # Corps principal (doré foncé)
        self.canvas.create_polygon(cx-hw, base_y, cx+hw, base_y, cx, tip,
                                   fill=GOLD_DK, outline=GOLD_LT, width=2)
        # Reflet central (triangle clair)
        self.canvas.create_polygon(cx-hw//2, base_y-1, cx+hw//2, base_y-1,
                                   cx, tip+10, fill=GOLD_LT, outline="")
        # Cercle de fixation
        br = 14
        self.canvas.create_oval(cx-br, base_y-br, cx+br, base_y+br,
                                fill=GOLD_DK, outline=GOLD_LT, width=2)
        self.canvas.create_oval(cx-br+5, base_y-br+5, cx+br-5, base_y+br-5,
                                fill=GOLD_LT, outline="")
        self.canvas.create_oval(cx-5, base_y-5, cx+5, base_y+5,
                                fill="#0A0D12", outline="")

    # ── spin & animation ──────────────────────────────────────────────────

    def _spin(self):
        if self.spinning or self._pending: return
        students = self.current_students()
        if not students:
            messagebox.showwarning(
                "Aucun élève",
                "Ajoutez des élèves via « Gérer les élèves » avant de tourner.")
            return

        # Préférer les élèves non encore passés
        called   = self.called_set()
        uncalled = [i for i, s in enumerate(students) if s not in called]
        pool     = uncalled if uncalled else list(range(len(students)))
        winner_idx = random.choice(pool)

        n     = len(students)
        sweep = 360.0 / n

        # Angle cible : centre du secteur gagnant à 90° (sommet)
        offset = random.uniform(-sweep * 0.32, sweep * 0.32)
        target = (90.0 - winner_idx * sweep - sweep / 2.0 + offset) % 360.0

        # Rotation totale = N tours entiers + delta vers la cible
        current = self.angle % 360.0
        delta   = (target - current) % 360.0
        if delta < sweep:
            delta += 360.0
        n_full = random.randint(5, 9)
        total  = n_full * 360.0 + delta

        # v0 tel que accel_rotation + decel_rotation = total
        # accel_rotation = v0 * _ACCEL_SUM
        # decel_rotation = (v0 - STOP_SPD) / (1 - DECEL)
        decel_factor = 1.0 / (1.0 - self.DECEL)
        v0 = (total + self.STOP_SPD * decel_factor) / (self._ACCEL_SUM + decel_factor)

        self._winner_idx = winner_idx
        self._snap_angle = target
        self._accel_v0   = v0
        self.spinning    = True
        self.flash_idx   = None
        self._pending    = None

        self.spin_btn.config(state=tk.DISABLED, text="⟳  Rotation…",
                             bg=MUTED, fg=TXT_MUT)
        self.confirm_frame.pack_forget()
        self.result_name_lbl.pack_forget()
        self.result_name_var.set("")
        self.result_sub_var.set("…")
        self.result_sub_lbl.config(fg=TXT_DIM)

        self._animate_accel(0)

    def _animate_accel(self, frame):
        # Ease-in sinusoïdal : vitesse 0 → v0 sur ACCEL_N frames
        t = (frame + 1) / self.ACCEL_N
        self.speed = self._accel_v0 * math.sin(t * math.pi / 2)
        self.angle = (self.angle + self.speed) % 360
        self._draw_wheel()
        if frame + 1 < self.ACCEL_N:
            self.root.after(self.FPS, lambda: self._animate_accel(frame + 1))
        else:
            self.speed = self._accel_v0
            self._animate()

    def _animate(self):
        self.angle = (self.angle + self.speed) % 360
        self.speed *= self.DECEL
        self._draw_wheel()
        if self.speed > self.STOP_SPD:
            self.root.after(self.FPS, self._animate)
        else:
            # Snap précis sur l'angle cible
            self.angle    = self._snap_angle
            self.spinning = False
            self._draw_wheel()
            self._on_stop()

    def _on_stop(self):
        students = self.current_students()
        if not students: return
        winner = students[self._winner_idx]
        called = self.called_set()

        self.flash_idx = self._winner_idx
        self.flash_cnt = 0
        self.flash_on  = False

        self.result_name_var.set(winner)
        if winner in called:
            self.result_name_lbl.config(fg=TXT_MUT)
            self.result_sub_var.set("déjà passé·e au tableau")
            self.result_sub_lbl.config(fg=TXT_DIM)
        else:
            self.result_name_lbl.config(fg=GOLD_LT)
            self.result_sub_var.set("passe au tableau !")
            self.result_sub_lbl.config(fg=TXT_MUT)
        self.result_name_lbl.pack(before=self.result_sub_lbl, pady=(8, 0))

        self._flash()

    def _flash(self):
        self.flash_on  = not self.flash_on
        self.flash_cnt += 1
        self._draw_wheel(hl_idx=self.flash_idx, hl_on=self.flash_on)
        if self.flash_cnt < self.FLASH_N * 2:
            self.root.after(110, self._flash)
        else:
            self._draw_wheel(hl_idx=self.flash_idx, hl_on=True)
            self._pending = self.current_students()[self.flash_idx]
            self.confirm_frame.pack(pady=4)

    def _confirm_record(self):
        if self._pending:
            self._record(self._pending)
        self._clear_result()

    def _ignore_record(self):
        if not self._pending: return
        self._clear_result()

    def _clear_result(self):
        if self.spinning: return
        self._pending  = None
        self.flash_idx = None
        self.confirm_frame.pack_forget()
        self.result_name_lbl.pack_forget()
        self.result_name_var.set("")
        self.result_sub_var.set("Appuyez sur Tourner !")
        self.result_sub_lbl.config(fg=TXT_DIM)
        self.spin_btn.config(state=tk.NORMAL, text="▶  TOURNER",
                             bg=GOLD_DK, fg="#1A1206")
        self._draw_wheel()

    def _record(self, name: str):
        self.history.append({
            "student": name,
            "mode":    self.mode.get(),
            "date":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        save_history(self.history)
        self._refresh()

    # ── refresh ───────────────────────────────────────────────────────────

    def _refresh(self):
        self._draw_wheel(hl_idx=self.flash_idx,
                         hl_on=self.flash_on if self.flash_idx is not None else False)
        self._update_stats()
        self._update_hist_list()
        self._update_mode_buttons()

    def _update_stats(self):
        students = self.current_students()
        called   = self.called_set()
        n_total  = len(students)
        n_called = sum(1 for s in students if s in called)
        n_left   = n_total - n_called
        pct      = int(n_called / n_total * 100) if n_total else 0

        self._stat_cards["total"].config(text=str(n_total))
        self._stat_cards["passed"].config(text=str(n_called))
        self._stat_cards["remaining"].config(text=str(n_left))
        self._prog_mode_lbl.config(text=self.mode_name())
        self._prog_pct_lbl.config(text=f"{pct}% passés")

        w = self._prog_canvas.winfo_width() or 196
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(0, 0, w, 8, fill=MUTED, outline="")
        if n_total > 0:
            fw    = int(w * n_called / n_total)
            color = SUCCESS if n_called == n_total else GOLD_DK
            if fw > 0:
                self._prog_canvas.create_rectangle(0, 0, fw, 8,
                                                   fill=color, outline="")

        all_done = n_total > 0 and n_left == 0
        if all_done:
            self._all_done_frame.pack(fill=tk.X, padx=10, pady=4)
        else:
            self._all_done_frame.pack_forget()

    def _update_hist_list(self):
        self.hist_lb.delete(0, tk.END)
        mode_fg = {
            "classe_entiere": TXT,
            "demi_groupe_1":  "#8FBFFF",
            "demi_groupe_2":  "#FFAAB8",
        }
        for i, e in enumerate(reversed(self.history[-30:])):
            m        = e.get("mode", "")
            abbr     = self.mode_abbr(m)
            dt       = e.get("date", "")
            time_str = dt.split(" ")[1] if " " in dt else ""
            self.hist_lb.insert(tk.END,
                                f" {time_str:>5}  [{abbr}]  {e['student']}")
            fg = mode_fg.get(m, TXT)
            if fg != TXT:
                self.hist_lb.itemconfig(i, foreground=fg)

    # ── dialogs ───────────────────────────────────────────────────────────

    def _reset_history(self):
        m = self.mode.get()
        if not messagebox.askyesno(
                "Réinitialisation",
                f"Effacer l'historique pour : {self.mode_name()} ?"):
            return
        self.history = [e for e in self.history if e.get("mode") != m]
        save_history(self.history)
        self._clear_result()
        self._refresh()

    def _show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Historique des passages")
        win.configure(bg=BG)
        win.geometry("640x520")
        win.resizable(True, True)

        hdr = tk.Frame(win, bg="#0A0D12")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Historique des passages au tableau",
                 font=("Arial", 14, "bold"), bg="#0A0D12", fg=TXT,
                 padx=16, pady=12).pack(anchor=tk.W)
        tk.Frame(win, bg=GOLD_DK, height=2).pack(fill=tk.X)

        fr = tk.Frame(win, bg=BG)
        fr.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg=FIELD, fg=TXT,
                        font=("Courier", 11), yscrollcommand=sb.set,
                        selectbackground=GOLD_DK, selectforeground="#1A1206",
                        relief=tk.FLAT, highlightthickness=0, activestyle="none")
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)

        ml = {"demi_groupe_1":  "Demi-groupe 1",
              "demi_groupe_2":  "Demi-groupe 2",
              "classe_entiere": "Classe entière"}
        mode_fg = {"demi_groupe_1": "#8FBFFF", "demi_groupe_2": "#FFAAB8"}
        for i, e in enumerate(reversed(self.history)):
            m = ml.get(e.get("mode", ""), "?")
            lb.insert(tk.END,
                      f"  {e.get('date',''):16}  {e['student']:<22}  [{m}]")
            fg = mode_fg.get(e.get("mode", ""))
            if fg:
                lb.itemconfig(i, foreground=fg)

        btn_f = tk.Frame(win, bg=BG)
        btn_f.pack(pady=10)
        close_btn = tk.Button(btn_f, text="Fermer",
                              bg=GOLD_DK, fg="#1A1206",
                              font=("Arial", 11, "bold"), relief=tk.FLAT,
                              padx=16, pady=7, cursor="hand2",
                              activebackground=GOLD_LT, activeforeground="#0A0800",
                              command=win.destroy)
        close_btn.pack()
        self._hover(close_btn, GOLD_LT, "#0A0800", GOLD_DK, "#1A1206")
        win.bind("<Escape>", lambda e: win.destroy())

    def _manage_students(self):
        win = tk.Toplevel(self.root)
        win.title("Gérer les élèves")
        win.configure(bg=BG)
        win.geometry("650x580")
        win.resizable(True, True)

        hdr = tk.Frame(win, bg="#0A0D12")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Gérer les élèves",
                 font=("Arial", 14, "bold"), bg="#0A0D12", fg=TXT,
                 padx=16, pady=12).pack(anchor=tk.W)
        tk.Frame(win, bg=GOLD_DK, height=2).pack(fill=tk.X)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        style = ttk.Style()
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=PNL, foreground="white",
                        padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", GOLD_BADGE)],
                  foreground=[("selected", GOLD)])

        for gkey, gname in [("demi_groupe_1", "Demi-groupe 1"),
                             ("demi_groupe_2", "Demi-groupe 2")]:
            tab = tk.Frame(nb, bg=PNL)
            nb.add(tab, text=gname)

            count_lbl = tk.Label(tab, font=("Arial", 10),
                                 bg=PNL, fg=TXT_DIM, anchor=tk.W)
            count_lbl.pack(fill=tk.X, padx=14, pady=(10, 0))
            tk.Label(tab, text="★ = déjà passé·e au tableau",
                     font=("Arial", 9), bg=PNL, fg=TXT_DIM).pack(anchor=tk.W, padx=14)

            lb = tk.Listbox(tab, bg=BG, fg=TXT,
                            font=("Arial", 11),
                            selectbackground=GOLD_DK, selectforeground="#1A1206",
                            relief=tk.FLAT, highlightthickness=0,
                            height=12, activestyle="none")
            lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

            def _refresh_lb(lb=lb, gk=gkey, cl=count_lbl):
                lb.delete(0, tk.END)
                c = self.called_set(gk)
                for s in self.students.get(gk, []):
                    lb.insert(tk.END, ("★  " if s in c else "   ") + s)
                    if s in c:
                        lb.itemconfig(lb.size()-1, foreground=TXT_DIM)
                n = lb.size()
                cl.config(text=f"{n} élève{'s' if n != 1 else ''}")
            _refresh_lb()

            def add(lb=lb, gk=gkey, rl=_refresh_lb):
                raw = simpledialog.askstring(
                    "Ajouter des élèves",
                    "Entrez un ou plusieurs noms\n(un par ligne ou séparés par des virgules) :",
                    parent=win)
                if not raw: return
                names = [n.strip() for part in raw.splitlines()
                         for n in part.split(",") if n.strip()]
                existing = set(self.students.get(gk, []))
                for n in names:
                    if n not in existing:
                        self.students.setdefault(gk, []).append(n)
                        existing.add(n)
                save_students(self.students)
                self._refresh()
                rl()

            def remove(lb=lb, gk=gkey, rl=_refresh_lb):
                sel = lb.curselection()
                if not sel: return
                raw  = lb.get(sel[0])
                name = raw.strip().lstrip("★").strip()
                if messagebox.askyesno("Supprimer",
                                       f"Supprimer « {name} » ?", parent=win):
                    lst = self.students.get(gk, [])
                    if name in lst: lst.remove(name)
                    save_students(self.students)
                    self._refresh()
                    rl()

            def rename(lb=lb, gk=gkey, rl=_refresh_lb):
                sel = lb.curselection()
                if not sel: return
                raw = lb.get(sel[0])
                old = raw.strip().lstrip("★").strip()
                new = simpledialog.askstring(
                    "Renommer", f"Nouveau nom pour « {old} » :",
                    initialvalue=old, parent=win)
                if new and new.strip() and new.strip() != old:
                    n   = new.strip()
                    lst = self.students.get(gk, [])
                    try:
                        lst[lst.index(old)] = n
                        save_students(self.students)
                        self._refresh()
                        rl()
                    except ValueError: pass

            bf = tk.Frame(tab, bg=PNL)
            bf.pack(pady=6)
            for txt, col, fg_c, hbg, hfg, fn in [
                ("+ Ajouter",   GOLD_DK, "#1A1206", GOLD_LT, "#0A0800", add),
                ("Renommer",    FIELD,   TXT_MUT,   MUTED,   TXT,       rename),
                ("✕ Supprimer", FIELD,   "#C98B86",  MUTED,   "#E8A8A0", remove),
            ]:
                btn = tk.Button(bf, text=txt, bg=col, fg=fg_c,
                                font=("Arial", 10, "bold"), relief=tk.FLAT,
                                padx=12, pady=8, cursor="hand2",
                                activebackground=hbg, activeforeground=hfg,
                                command=fn)
                btn.pack(side=tk.LEFT, padx=5)
                self._hover(btn, hbg, hfg, col, fg_c)

        btn_f = tk.Frame(win, bg=BG)
        btn_f.pack(pady=10)
        close_btn = tk.Button(btn_f, text="Fermer",
                              bg=GOLD_DK, fg="#1A1206",
                              font=("Arial", 11, "bold"), relief=tk.FLAT,
                              padx=16, pady=7, cursor="hand2",
                              activebackground=GOLD_LT, activeforeground="#0A0800",
                              command=win.destroy)
        close_btn.pack()
        self._hover(close_btn, GOLD_LT, "#0A0800", GOLD_DK, "#1A1206")
        win.bind("<Escape>", lambda e: win.destroy())

    # ── utilitaires UI ────────────────────────────────────────────────────

    def _section_title(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 9, "bold"),
                 bg=PNL, fg=TXT_DIM, anchor=tk.W,
                 padx=12).pack(fill=tk.X, pady=(12, 0))

    def _hsep(self, parent):
        tk.Frame(parent, bg=SEP, height=1).pack(fill=tk.X, padx=10, pady=(4, 8))


# Initialisation de la somme d'accélération après la définition de la classe
WheelApp._ACCEL_SUM = sum(
    math.sin(k * math.pi / (2 * WheelApp.ACCEL_N))
    for k in range(1, WheelApp.ACCEL_N + 1)
)


# ── Entrée ────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    WheelApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
