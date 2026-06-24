#!/usr/bin/env python3
"""Roue des Élèves — Sélecteur aléatoire pour le tableau (thème doré)"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json, random, math, os
from datetime import datetime

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.json")
HISTORY_FILE  = os.path.join(BASE_DIR, "history.json")

# ── Palette ambrée (identique à la version web) ───────────────────────────
RAMP = [
    "#F2CE7E", "#B27A2E", "#E6AE4C", "#8A5C22",
    "#EFDCAB", "#C68C38", "#D99B3A", "#A8702A",
]

BG         = "#0E1116"   # fond application
PNL        = "#13171E"   # fond panneaux
SEP        = "#1F2630"   # séparateurs
FIELD      = "#181D25"   # cartes / inputs
MUTED      = "#2A323D"   # bordures atténuées
GOLD       = "#EAB44E"   # or principal
GOLD_DK    = "#D99B33"   # or foncé
GOLD_LT    = "#F2C964"   # or clair
GOLD_BADGE = "#211B0E"   # fond badge or
TXT        = "#E8ECF2"   # texte principal
TXT_MUT    = "#9AA4B2"   # texte atténué
TXT_DIM    = "#6B7480"   # texte très discret
CALLED_BG  = "#222831"   # secteur déjà passé
CALLED_TXT = "#5A636F"   # texte secteur passé
FLASH_COL  = "#FFD27A"   # flash gagnant
WIN_COL    = "#F4C766"   # gagnant stable


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
    W       = 520    # taille du canvas (px)
    FPS     = 14     # ms par frame (~70 fps)
    DECEL   = 0.975  # décélération par frame (≈6-8 tours)
    FLASH_N = 7      # cycles de flash

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Roue des Élèves")
        root.configure(bg=BG)
        root.geometry("1120x730")
        root.minsize(960, 640)

        self.students       = load_students()
        self.history        = load_history()
        self.mode           = tk.StringVar(value="classe_entiere")
        self.spinning       = False
        self.angle          = 0.0
        self.speed          = 0.0
        self.flash_idx      = None
        self.flash_on       = False
        self.flash_cnt      = 0
        self._pending       = None   # nom du gagnant en attente de confirmation

        self._build_ui()
        self._refresh()
        # raccourci Espace = tourner
        root.bind("<space>", lambda e: self._spin())

    # ── helpers ───────────────────────────────────────────────────────────

    def current_students(self):
        m  = self.mode.get()
        g1 = self.students.get("demi_groupe_1", [])
        g2 = self.students.get("demi_groupe_2", [])
        if m == "demi_groupe_1": return list(g1)
        if m == "demi_groupe_2": return list(g2)
        return list(g1) + list(g2)

    def called_set(self):
        return {e["student"] for e in self.history}

    def mode_name(self, m=None):
        return {"classe_entiere": "Classe entière",
                "demi_groupe_1":  "Demi-groupe 1",
                "demi_groupe_2":  "Demi-groupe 2"}.get(m or self.mode.get(), "")

    def mode_abbr(self, m):
        return {"classe_entiere": "CE", "demi_groupe_1": "G1", "demi_groupe_2": "G2"}.get(m, "?")

    # ── construction UI ───────────────────────────────────────────────────

    def _build_ui(self):
        # ── En-tête ──
        hdr = tk.Frame(self.root, bg="#11151B", pady=0)
        hdr.pack(fill=tk.X)

        hdr_inner = tk.Frame(hdr, bg="#11151B")
        hdr_inner.pack(fill=tk.X, padx=22, pady=12)

        # Logo cercle doré
        logo_c = tk.Canvas(hdr_inner, width=36, height=36, bg="#11151B",
                           highlightthickness=0)
        logo_c.pack(side=tk.LEFT)
        logo_c.create_oval(2, 2, 34, 34, fill=GOLD_DK, outline=GOLD_LT, width=1)
        logo_c.create_oval(10, 10, 26, 26, fill="", outline="#14100A", width=2)

        title_f = tk.Frame(hdr_inner, bg="#11151B")
        title_f.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(title_f, text="Roue des Élèves",
                 font=("Arial", 18, "bold"), bg="#11151B", fg=TXT).pack(anchor=tk.W)
        tk.Label(title_f, text="Sélecteur aléatoire",
                 font=("Arial", 10), bg="#11151B", fg=TXT_DIM).pack(anchor=tk.W)

        badge_f = tk.Frame(hdr_inner, bg=FIELD, padx=10, pady=5)
        badge_f.pack(side=tk.RIGHT)
        tk.Label(badge_f, text="●", font=("Arial", 8), bg=FIELD, fg=GOLD).pack(side=tk.LEFT)
        tk.Label(badge_f, text=" Créé par ", font=("Arial", 10), bg=FIELD, fg=TXT_MUT).pack(side=tk.LEFT)
        tk.Label(badge_f, text="Élie", font=("Arial", 10, "bold"), bg=FIELD, fg=GOLD).pack(side=tk.LEFT)

        tk.Frame(self.root, bg=SEP, height=1).pack(fill=tk.X)

        # ── Corps principal ──
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # ── Panneau gauche ──
        left = tk.Frame(body, bg=PNL)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        left.config(width=218)

        self._section_title(left, "MODE")
        self._hsep(left)

        self.mode_btns = {}
        for lbl, val in [("Classe entière", "classe_entiere"),
                         ("Demi-groupe 1",  "demi_groupe_1"),
                         ("Demi-groupe 2",  "demi_groupe_2")]:
            btn = tk.Button(left, text=lbl,
                            font=("Arial", 11, "bold"), relief=tk.FLAT,
                            cursor="hand2", anchor=tk.W, padx=10, pady=8,
                            command=lambda v=val: self._set_mode(v))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.mode_btns[val] = btn

        self._hsep(left)
        self._section_title(left, "STATISTIQUES")
        self._hsep(left)

        # 3 stat-cards
        stats_row = tk.Frame(left, bg=PNL)
        stats_row.pack(fill=tk.X, padx=10)
        self._stat_cards = {}
        for col, (key, label, color) in enumerate([
            ("total",     "Total",    TXT),
            ("passed",    "Passés",   GOLD),
            ("remaining", "Restants", TXT_MUT),
        ]):
            card = tk.Frame(stats_row, bg=FIELD, padx=6, pady=8)
            card.grid(row=0, column=col, padx=3, sticky="nsew")
            stats_row.columnconfigure(col, weight=1)
            num = tk.Label(card, text="0", font=("Courier", 18, "bold"),
                           bg=FIELD, fg=color)
            num.pack()
            tk.Label(card, text=label, font=("Arial", 9),
                     bg=FIELD, fg=TXT_DIM).pack()
            self._stat_cards[key] = num

        # Barre de progression
        prog_row = tk.Frame(left, bg=PNL)
        prog_row.pack(fill=tk.X, padx=10, pady=(8, 0))
        prog_labels = tk.Frame(prog_row, bg=PNL)
        prog_labels.pack(fill=tk.X)
        self._prog_mode_lbl = tk.Label(prog_labels, font=("Arial", 9),
                                       bg=PNL, fg=TXT_DIM, anchor=tk.W)
        self._prog_mode_lbl.pack(side=tk.LEFT)
        self._prog_pct_lbl  = tk.Label(prog_labels, font=("Arial", 9),
                                       bg=PNL, fg=TXT_DIM, anchor=tk.E)
        self._prog_pct_lbl.pack(side=tk.RIGHT)

        self._prog_canvas = tk.Canvas(left, height=8, bg=FIELD,
                                      highlightthickness=0)
        self._prog_canvas.pack(fill=tk.X, padx=10, pady=(4, 0))

        self._hsep(left)

        # Boutons d'action
        for txt, bg_c, fg_c, cmd in [
            ("✦  Gérer les élèves",         GOLD_DK,  "#1A1206", self._manage_students),
            ("≡  Voir l'historique",        FIELD,    TXT_MUT,   self._show_history),
            ("↺  Réinitialiser historique", FIELD,    TXT_DIM,   self._reset_history),
        ]:
            tk.Button(left, text=txt, bg=bg_c, fg=fg_c,
                      font=("Arial", 10, "bold"), relief=tk.FLAT,
                      cursor="hand2", anchor=tk.W, padx=10, pady=8,
                      command=cmd).pack(fill=tk.X, padx=10, pady=2)

        self._update_mode_buttons()

        # ── Centre ──
        center = tk.Frame(body, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, width=self.W, height=self.W,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        # Zone résultat (hauteur fixe pour éviter les sauts)
        result_area = tk.Frame(center, bg=BG, height=90)
        result_area.pack(fill=tk.X)
        result_area.pack_propagate(False)

        self.result_var = tk.StringVar(value="Appuyez sur Tourner !")
        self.result_lbl = tk.Label(result_area, textvariable=self.result_var,
                                   font=("Arial", 14, "bold"),
                                   bg=BG, fg=TXT_DIM, wraplength=460)
        self.result_lbl.pack(pady=(8, 0))

        # Boutons de confirmation (inline, cachés par défaut)
        self.confirm_frame = tk.Frame(result_area, bg=BG)
        # Ne pas packer maintenant — affiché après le flash

        btn_inner = tk.Frame(self.confirm_frame, bg=BG)
        btn_inner.pack()
        self.btn_confirm = tk.Button(btn_inner, text="✓ Noter le passage",
                                     bg=GOLD_DK, fg="#1A1206",
                                     font=("Arial", 11, "bold"), relief=tk.FLAT,
                                     cursor="hand2", padx=14, pady=7,
                                     command=self._confirm_record)
        self.btn_confirm.pack(side=tk.LEFT, padx=5)
        tk.Button(btn_inner, text="Ignorer",
                  bg=FIELD, fg=TXT_MUT,
                  font=("Arial", 11), relief=tk.FLAT,
                  cursor="hand2", padx=14, pady=7,
                  command=self._ignore_record).pack(side=tk.LEFT, padx=5)

        self.spin_btn = tk.Button(center, text="TOURNER",
                                  font=("Arial", 15, "bold"),
                                  bg=GOLD_DK, fg="#1A1206",
                                  relief=tk.FLAT, cursor="hand2",
                                  padx=32, pady=12,
                                  command=self._spin)
        self.spin_btn.pack(pady=6)

        # ── Panneau droit ──
        right = tk.Frame(body, bg=PNL)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)
        right.config(width=200)

        self._section_title(right, "DERNIERS PASSAGES")
        self._hsep(right)

        lf = tk.Frame(right, bg=PNL)
        lf.pack(fill=tk.BOTH, expand=True, padx=5)
        sb = tk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_lb = tk.Listbox(lf, bg=BG, fg=TXT,
                                  font=("Courier", 10), yscrollcommand=sb.set,
                                  selectbackground=GOLD_DK, selectforeground="#1A1206",
                                  relief=tk.FLAT, highlightthickness=0)
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
        g1 = self.students.get("demi_groupe_1", [])
        g2 = self.students.get("demi_groupe_2", [])
        counts = {
            "classe_entiere": len(g1) + len(g2),
            "demi_groupe_1":  len(g1),
            "demi_groupe_2":  len(g2),
        }
        labels = {
            "classe_entiere": "Classe entière",
            "demi_groupe_1":  "Demi-groupe 1",
            "demi_groupe_2":  "Demi-groupe 2",
        }
        active = self.mode.get()
        for val, btn in self.mode_btns.items():
            n = counts[val]
            lbl = labels[val]
            if val == active:
                btn.config(bg=GOLD_DK, fg="#1A1206",
                           text=f"{lbl}   ({n})")
            else:
                btn.config(bg=FIELD, fg=TXT_MUT,
                           text=f"{lbl}   ({n})")

    # ── dessin de la roue ─────────────────────────────────────────────────

    def _draw_wheel(self, hl_idx=None, hl_on=False):
        self.canvas.delete("all")
        students = self.current_students()
        called   = self.called_set()
        cx = cy  = self.W // 2
        R        = cx - 24
        HUB      = 30

        if not students:
            self.canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                                    fill=FIELD, outline=SEP, width=3)
            self.canvas.create_text(cx, cy,
                                    text="Aucun élève\n\nCliquez sur\n« Gérer les élèves »",
                                    font=("Arial", 13), fill=TXT_DIM, justify=tk.CENTER)
            self._draw_arrow(cx, cy, R)
            return

        n     = len(students)
        sweep = 360.0 / n

        # halo externe
        for offset, col in [(12, "#050810"), (8, "#080d18"), (4, "#0c1320")]:
            self.canvas.create_oval(cx-R-offset, cy-R-offset,
                                    cx+R+offset, cy+R+offset,
                                    fill="", outline=col, width=offset)

        for i, name in enumerate(students):
            start    = self.angle + i * sweep
            mid_deg  = start + sweep / 2
            is_called = name in called
            is_win    = (hl_idx == i)
            flashing  = is_win and hl_on

            fill = FLASH_COL if flashing else (WIN_COL if is_win else
                   (CALLED_BG if is_called else RAMP[i % len(RAMP)]))
            bw   = 3 if is_win else 1
            bc   = GOLD_LT if is_win else BG

            self.canvas.create_arc(cx-R, cy-R, cx+R, cy+R,
                                   start=start, extent=sweep,
                                   fill=fill, outline=bc, width=bw)

            # texte rotatif
            mid_rad = math.radians(mid_deg)
            tx = cx + R * 0.64 * math.cos(mid_rad)
            ty = cy - R * 0.64 * math.sin(mid_rad)

            norm    = mid_deg % 360
            t_angle = (norm + 180) if 90 < norm < 270 else norm

            max_c = max(5, int(14 - n / 6))
            label = name if len(name) <= max_c else name[:max_c-1] + "…"
            fsize = max(6, min(12, int(200 / n)))
            tcolor = CALLED_TXT if is_called and not flashing else "#241906"

            # ombre texte
            self.canvas.create_text(tx+1, ty+1, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill="#06090f", angle=t_angle)
            self.canvas.create_text(tx, ty, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill=tcolor, angle=t_angle)

        # rebords
        self.canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                                fill="", outline=BG, width=2)
        self.canvas.create_oval(cx-R+4, cy-R+4, cx+R-4, cy+R-4,
                                fill="", outline="#2a3040", width=1)

        # hub
        self.canvas.create_oval(cx-HUB-4, cy-HUB-4, cx+HUB+4, cy+HUB+4,
                                fill="#11151B", outline=MUTED, width=2)
        self.canvas.create_oval(cx-HUB+3, cy-HUB+3, cx+HUB-3, cy+HUB-3,
                                fill=FIELD, outline="")
        # point doré central
        self.canvas.create_oval(cx-7, cy-7, cx+7, cy+7,
                                fill=GOLD, outline=GOLD_LT, width=1)

        self._draw_arrow(cx, cy, R)

    def _draw_arrow(self, cx, cy, R):
        ax    = cx
        tip   = cy - R + 2
        base_y = cy - R - 26
        hw    = 14
        # ombre
        self.canvas.create_polygon(ax-hw+2, base_y+2, ax+hw+2, base_y+2,
                                   ax+2, tip+2, fill="#06090f", outline="")
        # corps doré
        self.canvas.create_polygon(ax-hw, base_y, ax+hw, base_y, ax, tip,
                                   fill=GOLD, outline=GOLD_LT, width=2)
        # cercle de fixation
        br = 11
        self.canvas.create_oval(ax-br, base_y-br, ax+br, base_y+br,
                                fill=GOLD, outline=GOLD_LT, width=2)
        # point intérieur sombre
        self.canvas.create_oval(ax-4, base_y-4, ax+4, base_y+4,
                                fill="#11151B", outline="")

    # ── secteur sous la flèche ────────────────────────────────────────────

    def _top_sector(self):
        students = self.current_students()
        if not students: return None
        n   = len(students)
        adj = (90.0 - self.angle) % 360.0
        return int(adj / (360.0 / n)) % n

    # ── spin ──────────────────────────────────────────────────────────────

    def _spin(self):
        if self.spinning: return
        students = self.current_students()
        if not students:
            messagebox.showwarning(
                "Aucun élève",
                "Ajoutez des élèves via « Gérer les élèves » avant de tourner.")
            return
        self.spinning  = True
        self.flash_idx = None
        self._pending  = None
        self.spin_btn.config(state=tk.DISABLED)
        self.result_var.set("…")
        self.result_lbl.config(fg=TXT_DIM)
        # vitesse initiale : ~6-10 tours complets avant arrêt
        self.speed = random.uniform(55, 85)
        self._animate()

    def _animate(self):
        self.angle = (self.angle + self.speed) % 360
        self.speed *= self.DECEL
        self._draw_wheel()
        if self.speed > 0.25:
            self.root.after(self.FPS, self._animate)
        else:
            self.spinning = False
            # spin_btn reste désactivé jusqu'à confirm / ignore
            self._on_stop()

    def _on_stop(self):
        students = self.current_students()
        if not students: return
        idx    = self._top_sector()
        winner = students[idx]
        called = self.called_set()

        if winner in called:
            self.result_var.set(f"{winner}  ·  déjà passé·e au tableau")
            self.result_lbl.config(fg=TXT_MUT)
        else:
            self.result_var.set(f"★  {winner}  passe au tableau !")
            self.result_lbl.config(fg=GOLD_LT)

        self.flash_idx = idx
        self.flash_cnt = 0
        self.flash_on  = False
        self._flash()

    def _flash(self):
        self.flash_on  = not self.flash_on
        self.flash_cnt += 1
        self._draw_wheel(hl_idx=self.flash_idx, hl_on=self.flash_on)
        if self.flash_cnt < self.FLASH_N * 2:
            self.root.after(115, self._flash)
        else:
            self._draw_wheel(hl_idx=self.flash_idx, hl_on=True)
            winner = self.current_students()[self.flash_idx]
            self._pending = winner
            # Afficher les boutons de confirmation inline
            self.confirm_frame.pack(pady=4)

    def _confirm_record(self):
        if self._pending:
            self._record(self._pending)
        self._clear_result()

    def _ignore_record(self):
        self._clear_result()

    def _clear_result(self):
        self._pending  = None
        self.flash_idx = None
        self.confirm_frame.pack_forget()
        self.spin_btn.config(state=tk.NORMAL)
        self.result_var.set("Appuyez sur Tourner !")
        self.result_lbl.config(fg=TXT_DIM)
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

        w = self._prog_canvas.winfo_width() or 190
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(0, 0, w, 8, fill=FIELD, outline="")
        if n_total > 0:
            fw    = int(w * n_called / n_total)
            color = GOLD if n_called == n_total else GOLD_DK
            self._prog_canvas.create_rectangle(0, 0, fw, 8, fill=color, outline="")

    def _update_hist_list(self):
        self.hist_lb.delete(0, tk.END)
        for e in reversed(self.history[-30:]):
            abbr = self.mode_abbr(e.get("mode", ""))
            self.hist_lb.insert(tk.END, f" [{abbr}]  {e['student']}")

    # ── dialogs ───────────────────────────────────────────────────────────

    def _reset_history(self):
        m = self.mode.get()
        if not messagebox.askyesno(
                "Réinitialisation",
                f"Effacer l'historique pour : {self.mode_name()} ?"):
            return
        if m == "classe_entiere":
            self.history = []
        else:
            group = set(self.students.get(m, []))
            self.history = [e for e in self.history if e["student"] not in group]
        save_history(self.history)
        self._refresh()

    def _show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Historique des passages")
        win.configure(bg=BG)
        win.geometry("580x460")

        tk.Label(win, text="Historique des passages au tableau",
                 font=("Arial", 13, "bold"), bg=BG, fg=TXT).pack(pady=10)

        fr = tk.Frame(win, bg=BG)
        fr.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg=FIELD, fg=TXT,
                        font=("Courier", 11), yscrollcommand=sb.set,
                        selectbackground=GOLD_DK, selectforeground="#1A1206",
                        relief=tk.FLAT, highlightthickness=0)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)

        ml = {"demi_groupe_1": "Demi-groupe 1",
              "demi_groupe_2": "Demi-groupe 2",
              "classe_entiere": "Classe entière"}
        for e in reversed(self.history):
            m = ml.get(e.get("mode", ""), "?")
            lb.insert(tk.END, f"  {e.get('date',''):16}  {e['student']:<22}  [{m}]")

        tk.Button(win, text="Fermer", bg=GOLD_DK, fg="#1A1206",
                  font=("Arial", 11, "bold"), relief=tk.FLAT,
                  padx=14, pady=6, command=win.destroy).pack(pady=10)

    def _manage_students(self):
        win = tk.Toplevel(self.root)
        win.title("Gérer les élèves")
        win.configure(bg=BG)
        win.geometry("620x540")

        tk.Label(win, text="Gérer les élèves",
                 font=("Arial", 13, "bold"), bg=BG, fg=TXT).pack(pady=10)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        style = ttk.Style()
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=PNL, foreground="white",
                        padding=[12, 5])
        style.map("TNotebook.Tab",
                  background=[("selected", GOLD_BADGE)],
                  foreground=[("selected", GOLD)])

        for gkey, gname in [("demi_groupe_1", "Demi-groupe 1"),
                             ("demi_groupe_2", "Demi-groupe 2")]:
            tab = tk.Frame(nb, bg=PNL)
            nb.add(tab, text=gname)

            count_lbl = tk.Label(tab, font=("Arial", 10), bg=PNL, fg=TXT_DIM, anchor=tk.W)
            count_lbl.pack(fill=tk.X, padx=12, pady=(8, 2))

            lb = tk.Listbox(tab, bg=BG, fg=TXT,
                            font=("Arial", 11),
                            selectbackground=GOLD_DK, selectforeground="#1A1206",
                            relief=tk.FLAT, highlightthickness=0, height=14)
            lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

            for s in self.students.get(gkey, []):
                lb.insert(tk.END, s)

            def _rc(lb=lb, cl=count_lbl):
                n = lb.size()
                cl.config(text=f"{n} élève{'s' if n != 1 else ''}")
            _rc()

            def add(lb=lb, gk=gkey, rc=_rc):
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
                        lb.insert(tk.END, n)
                        existing.add(n)
                save_students(self.students)
                self._refresh(); rc()

            def remove(lb=lb, gk=gkey, rc=_rc):
                sel = lb.curselection()
                if not sel: return
                n = lb.get(sel[0])
                if messagebox.askyesno("Supprimer",
                                       f"Supprimer « {n} » ?", parent=win):
                    lb.delete(sel[0])
                    lst = self.students.get(gk, [])
                    if n in lst: lst.remove(n)
                    save_students(self.students)
                    self._refresh(); rc()

            def rename(lb=lb, gk=gkey):
                sel = lb.curselection()
                if not sel: return
                old = lb.get(sel[0])
                new = simpledialog.askstring(
                    "Renommer", f"Nouveau nom pour « {old} » :",
                    initialvalue=old, parent=win)
                if new and new.strip() and new.strip() != old:
                    n   = new.strip()
                    lst = self.students.get(gk, [])
                    try:
                        lst[lst.index(old)] = n
                        lb.delete(sel[0]); lb.insert(sel[0], n)
                        save_students(self.students); self._refresh()
                    except ValueError: pass

            bf = tk.Frame(tab, bg=PNL)
            bf.pack(pady=6)
            for txt, col, fg_c, fn in [
                ("+ Ajouter",  GOLD_DK,  "#1A1206", add),
                ("Renommer",   FIELD,    TXT_MUT,   rename),
                ("Supprimer",  FIELD,    "#C98B86",  remove),
            ]:
                tk.Button(bf, text=txt, bg=col, fg=fg_c,
                          font=("Arial", 10, "bold"), relief=tk.FLAT,
                          padx=10, pady=7,
                          command=fn).pack(side=tk.LEFT, padx=4)

        tk.Button(win, text="Fermer", bg=GOLD_DK, fg="#1A1206",
                  font=("Arial", 11, "bold"), relief=tk.FLAT,
                  padx=14, pady=6, command=win.destroy).pack(pady=10)

    # ── utilitaires UI ────────────────────────────────────────────────────

    def _section_title(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 9, "bold"),
                 bg=PNL, fg=TXT_DIM, anchor=tk.W,
                 padx=10).pack(fill=tk.X, pady=(12, 0))

    def _hsep(self, parent):
        tk.Frame(parent, bg=SEP, height=1).pack(fill=tk.X, padx=10, pady=(4, 8))


# ── Entrée ────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    WheelApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
