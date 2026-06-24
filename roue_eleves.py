#!/usr/bin/env python3
"""Roue des Élèves — Sélecteur aléatoire pour le tableau"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json, random, math, os
from datetime import datetime

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.json")
HISTORY_FILE  = os.path.join(BASE_DIR, "history.json")

# Vibrant palette (cycles if more students than colors)
COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFEAA7", "#A29BFE",
    "#6BCB77", "#FF8C42", "#4D96FF", "#FF6B9D", "#56CFE1",
    "#FFBE0B", "#C77DFF", "#80FFDB", "#FB5607", "#06D6A0",
    "#EF476F", "#FFD166", "#118AB2", "#F72585", "#3A86FF",
    "#8338EC", "#06D6A0", "#FFBE0B", "#FF006E", "#3F37C9",
    "#4361EE", "#4CC9F0", "#F77F00", "#D62828", "#023E8A",
]

CALLED_BG   = "#2D3748"   # already-called sector fill
CALLED_TEXT = "#718096"   # already-called text color


# ── persistence ───────────────────────────────────────────────────────────────

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


# ── application ───────────────────────────────────────────────────────────────

class WheelApp:
    W       = 520    # canvas size (px)
    FPS     = 14     # ms per frame
    DECEL   = 0.972  # speed multiplier per frame
    FLASH_N = 6      # flash cycles after stop

    BG  = "#0F172A"  # app background
    PNL = "#1E293B"  # panel background
    SEP = "#334155"  # separator / muted element

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Roue des Élèves")
        root.configure(bg=self.BG)
        root.geometry("1120x730")
        root.minsize(960, 640)

        self.students  = load_students()
        self.history   = load_history()
        self.mode      = tk.StringVar(value="classe_entiere")
        self.spinning  = False
        self.angle     = 0.0
        self.speed     = 0.0
        self.flash_idx = None
        self.flash_on  = False
        self.flash_cnt = 0

        self._build_ui()
        self._refresh()

    # ── helpers ───────────────────────────────────────────────────────────────

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

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg="#1E293B")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Roue des Élèves",
                 font=("Arial", 20, "bold"), bg="#1E293B",
                 fg="#F1F5F9", pady=10).pack()

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # ── Left panel ──
        left = tk.Frame(body, bg=self.PNL, padx=12, pady=14)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        left.config(width=215)

        self._lbl(left, "MODE")
        self._hsep(left)

        self.mode_btns = {}
        for label, val in [("Classe entière", "classe_entiere"),
                            ("Demi-groupe 1",  "demi_groupe_1"),
                            ("Demi-groupe 2",  "demi_groupe_2")]:
            btn = tk.Button(left, text=label,
                            font=("Arial", 11, "bold"),
                            relief=tk.FLAT, cursor="hand2",
                            padx=8, pady=7, anchor=tk.W,
                            command=lambda v=val: self._set_mode(v))
            btn.pack(fill=tk.X, pady=2)
            self.mode_btns[val] = btn

        self._hsep(left)
        self._lbl(left, "STATISTIQUES")
        self._hsep(left)

        self.stats_lbl = tk.Label(left, text="", font=("Arial", 10),
                                  bg=self.PNL, fg="#CBD5E1",
                                  justify=tk.LEFT, anchor=tk.W)
        self.stats_lbl.pack(fill=tk.X)

        self.prog_canvas = tk.Canvas(left, height=10, bg=self.SEP,
                                     highlightthickness=0)
        self.prog_canvas.pack(fill=tk.X, pady=(6, 0))

        self._hsep(left)

        for txt, col, cmd in [
            ("Gérer les élèves",         "#2563EB", self._manage_students),
            ("Voir l'historique",        "#059669", self._show_history),
            ("Réinitialiser historique", "#DC2626", self._reset_history),
        ]:
            tk.Button(left, text=txt, bg=col, fg="white",
                      font=("Arial", 10, "bold"), relief=tk.FLAT,
                      cursor="hand2", padx=8, pady=7,
                      command=cmd).pack(fill=tk.X, pady=2)

        self._update_mode_buttons()

        # ── Center ──
        center = tk.Frame(body, bg=self.BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, width=self.W, height=self.W,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack()

        self.result_var = tk.StringVar(value="Appuyez sur Tourner !")
        self.result_lbl = tk.Label(center, textvariable=self.result_var,
                                   font=("Arial", 15, "bold"),
                                   bg=self.BG, fg="#F59E0B", wraplength=460)
        self.result_lbl.pack(pady=(4, 2))

        self.spin_btn = tk.Button(center, text="TOURNER !",
                                  font=("Arial", 14, "bold"),
                                  bg="#EF4444", fg="white", relief=tk.FLAT,
                                  cursor="hand2", padx=28, pady=10,
                                  command=self._spin)
        self.spin_btn.pack(pady=6)

        # ── Right panel ──
        right = tk.Frame(body, bg=self.PNL, padx=8, pady=14)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)
        right.config(width=200)

        self._lbl(right, "DERNIERS PASSAGES")
        self._hsep(right)

        lf = tk.Frame(right, bg=self.PNL)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_lb = tk.Listbox(lf, bg=self.BG, fg="#E2E8F0",
                                  font=("Arial", 10), yscrollcommand=sb.set,
                                  selectbackground="#2563EB",
                                  relief=tk.FLAT, highlightthickness=0)
        self.hist_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.hist_lb.yview)

    # ── mode buttons ─────────────────────────────────────────────────────────

    def _set_mode(self, val):
        self.mode.set(val)
        self._update_mode_buttons()
        self.result_var.set("Appuyez sur Tourner !")
        self.result_lbl.config(fg="#F59E0B")
        self._refresh()

    def _update_mode_buttons(self):
        active = self.mode.get()
        for val, btn in self.mode_btns.items():
            btn.config(bg="#2563EB" if val == active else self.SEP,
                       fg="white"   if val == active else "#94A3B8")

    # ── wheel ─────────────────────────────────────────────────────────────────

    def _draw_wheel(self, hl_idx=None, hl_on=False):
        self.canvas.delete("all")
        students = self.current_students()
        called   = self.called_set()
        cx = cy  = self.W // 2
        R        = cx - 24     # wheel outer radius
        HUB      = 28          # center hub radius

        # ── empty state ──
        if not students:
            self.canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                                    fill="#1E293B", outline=self.SEP, width=3)
            self.canvas.create_text(
                cx, cy,
                text="Aucun élève\n\nCliquez sur\n« Gérer les élèves »",
                font=("Arial", 13), fill="#64748B", justify=tk.CENTER)
            self._draw_arrow(cx, cy, R)
            return

        n     = len(students)
        sweep = 360.0 / n

        # outer glow / shadow (rings of decreasing darkness)
        for offset, alpha in [(12, "#050a14"), (8, "#0a1628"), (4, "#0f1e38")]:
            self.canvas.create_oval(cx-R-offset, cy-R-offset,
                                    cx+R+offset, cy+R+offset,
                                    fill="", outline=alpha, width=offset)

        # ── sectors ──
        for i, name in enumerate(students):
            start     = self.angle + i * sweep
            mid_deg   = start + sweep / 2
            is_called = name in called
            is_winner = (hl_idx == i)
            flashing  = is_winner and hl_on

            fill = "#FBBF24" if flashing else (CALLED_BG if is_called else COLORS[i % len(COLORS)])
            bw   = 3 if is_winner else 1
            bc   = "#FBBF24" if is_winner else "#0F172A"

            self.canvas.create_arc(cx-R, cy-R, cx+R, cy+R,
                                   start=start, extent=sweep,
                                   fill=fill, outline=bc, width=bw)

            # ── rotated text ──
            mid_rad = math.radians(mid_deg)
            tx = cx + R * 0.64 * math.cos(mid_rad)
            ty = cy - R * 0.64 * math.sin(mid_rad)

            norm = mid_deg % 360
            t_angle = (norm + 180) if 90 < norm < 270 else norm

            max_c  = max(5, int(14 - n / 6))
            label  = name if len(name) <= max_c else name[:max_c - 1] + "…"
            fsize  = max(6, min(12, int(200 / n)))
            tcolor = (CALLED_TEXT if is_called and not flashing else "white")

            # text shadow
            self.canvas.create_text(tx + 1, ty + 1, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill="#0a0e17", angle=t_angle)
            self.canvas.create_text(tx, ty, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill=tcolor, angle=t_angle)

        # outer rim
        self.canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                                fill="", outline="white", width=2)
        # inner rim
        self.canvas.create_oval(cx-R+5, cy-R+5, cx+R-5, cy+R-5,
                                fill="", outline="#334155", width=1)

        # ── hub ──
        self.canvas.create_oval(cx-HUB-4, cy-HUB-4, cx+HUB+4, cy+HUB+4,
                                fill="#0F172A", outline="white", width=2)
        self.canvas.create_oval(cx-HUB+3, cy-HUB+3, cx+HUB-3, cy+HUB-3,
                                fill=self.SEP, outline="#475569", width=1)
        self.canvas.create_oval(cx-6, cy-6, cx+6, cy+6,
                                fill="#F59E0B", outline="")

        self._draw_arrow(cx, cy, R)

    def _draw_arrow(self, cx, cy, R):
        ax    = cx
        tip   = cy - R + 2
        base_y = cy - R - 26
        hw    = 14

        # shadow
        self.canvas.create_polygon(ax-hw+2, base_y+2, ax+hw+2, base_y+2,
                                   ax+2, tip+2,
                                   fill="#0a0e17", outline="")
        # body
        self.canvas.create_polygon(ax-hw, base_y, ax+hw, base_y, ax, tip,
                                   fill="#EF4444", outline="white", width=2)
        # mounting circle
        br = 11
        self.canvas.create_oval(ax-br, base_y-br, ax+br, base_y+br,
                                fill="#EF4444", outline="white", width=2)
        self.canvas.create_oval(ax-4, base_y-4, ax+4, base_y+4,
                                fill="white", outline="")

    # ── sector finder ─────────────────────────────────────────────────────────

    def _top_sector(self):
        students = self.current_students()
        if not students:
            return None
        n   = len(students)
        adj = (90.0 - self.angle) % 360.0
        return int(adj / (360.0 / n)) % n

    # ── spin ──────────────────────────────────────────────────────────────────

    def _spin(self):
        if self.spinning:
            return
        students = self.current_students()
        if not students:
            messagebox.showwarning(
                "Aucun élève",
                "Ajoutez des élèves via « Gérer les élèves » avant de tourner.")
            return

        self.spinning  = True
        self.flash_idx = None
        self.spin_btn.config(state=tk.DISABLED)
        self.result_var.set("…")
        self.result_lbl.config(fg="#F59E0B")
        self.speed = random.uniform(16, 25)
        self._animate()

    def _animate(self):
        self.angle = (self.angle + self.speed) % 360
        self.speed *= self.DECEL
        self._draw_wheel()
        if self.speed > 0.20:
            self.root.after(self.FPS_MS, self._animate)
        else:
            self.spinning = False
            self.spin_btn.config(state=tk.NORMAL)
            self._on_stop()

    def _on_stop(self):
        students = self.current_students()
        if not students:
            return
        idx    = self._top_sector()
        winner = students[idx]
        called = self.called_set()

        if winner in called:
            self.result_var.set(f"{winner}  —  déjà passé·e au tableau")
            self.result_lbl.config(fg="#F97316")
        else:
            self.result_var.set(f"⭐  {winner}  passe au tableau !")
            self.result_lbl.config(fg="#10B981")

        # start flash
        self.flash_idx = idx
        self.flash_cnt = 0
        self.flash_on  = False
        self._flash()

    def _flash(self):
        self.flash_on  = not self.flash_on
        self.flash_cnt += 1
        self._draw_wheel(hl_idx=self.flash_idx, hl_on=self.flash_on)
        if self.flash_cnt < self.FLASH_N * 2:
            self.root.after(180, self._flash)
        else:
            self._draw_wheel(hl_idx=self.flash_idx, hl_on=True)
            winner = self.current_students()[self.flash_idx]
            self._ask_record(winner)

    def _ask_record(self, winner):
        if messagebox.askyesno(
                "Enregistrer le passage",
                f"Confirmer que {winner} est passé·e au tableau ?"):
            self._record(winner)
        else:
            self.flash_idx = None
            self._draw_wheel()

    def _record(self, name):
        self.history.append({
            "student": name,
            "mode":    self.mode.get(),
            "date":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        save_history(self.history)
        self.flash_idx = None
        self._refresh()

    # ── refresh ───────────────────────────────────────────────────────────────

    def _refresh(self):
        self._draw_wheel()
        self._update_stats()
        self._update_hist_list()

    def _update_stats(self):
        students = self.current_students()
        called   = self.called_set()
        n_total  = len(students)
        n_called = sum(1 for s in students if s in called)
        n_left   = n_total - n_called

        self.stats_lbl.config(
            text=(f"Groupe : {self.mode_name()}\n\n"
                  f"Total :    {n_total} élève(s)\n"
                  f"Passés :   {n_called}\n"
                  f"Restants : {n_left}"))

        # progress bar
        w = self.prog_canvas.winfo_width() or 185
        self.prog_canvas.delete("all")
        self.prog_canvas.create_rectangle(0, 0, w, 10, fill=self.SEP, outline="")
        if n_total > 0:
            fw    = int(w * n_called / n_total)
            color = "#F59E0B" if n_called == n_total else "#10B981"
            self.prog_canvas.create_rectangle(0, 0, fw, 10, fill=color, outline="")

    def _update_hist_list(self):
        self.hist_lb.delete(0, tk.END)
        abbr = {"classe_entiere": "CE", "demi_groupe_1": "G1", "demi_groupe_2": "G2"}
        for e in reversed(self.history[-30:]):
            a = abbr.get(e.get("mode", ""), "?")
            self.hist_lb.insert(tk.END, f"[{a}]  {e['student']}")

    # ── dialogs ───────────────────────────────────────────────────────────────

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
            self.history = [e for e in self.history
                            if e["student"] not in group]
        save_history(self.history)
        self._refresh()

    def _show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Historique complet")
        win.configure(bg=self.BG)
        win.geometry("580x460")

        tk.Label(win, text="Historique des passages au tableau",
                 font=("Arial", 13, "bold"), bg=self.BG, fg="white").pack(pady=10)

        fr = tk.Frame(win, bg=self.BG)
        fr.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg=self.PNL, fg="#E2E8F0",
                        font=("Courier", 11), yscrollcommand=sb.set,
                        selectbackground="#2563EB", relief=tk.FLAT,
                        highlightthickness=0)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)

        ml = {"demi_groupe_1": "Demi-groupe 1",
              "demi_groupe_2": "Demi-groupe 2",
              "classe_entiere": "Classe entière"}
        for e in reversed(self.history):
            m = ml.get(e.get("mode", ""), "?")
            lb.insert(tk.END,
                      f"  {e.get('date',''):16}  {e['student']:<22}  [{m}]")

        tk.Button(win, text="Fermer", bg="#DC2626", fg="white",
                  font=("Arial", 11), relief=tk.FLAT,
                  padx=14, pady=6, command=win.destroy).pack(pady=10)

    def _manage_students(self):
        win = tk.Toplevel(self.root)
        win.title("Gestion des élèves")
        win.configure(bg=self.BG)
        win.geometry("620x540")

        tk.Label(win, text="Gestion des élèves",
                 font=("Arial", 13, "bold"), bg=self.BG, fg="white").pack(pady=10)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        style = ttk.Style()
        style.configure("TNotebook",     background=self.BG)
        style.configure("TNotebook.Tab", background=self.PNL,
                        foreground="white", padding=[12, 5])

        for gkey, gname in [("demi_groupe_1", "Demi-groupe 1"),
                             ("demi_groupe_2", "Demi-groupe 2")]:
            tab = tk.Frame(nb, bg=self.PNL)
            nb.add(tab, text=gname)

            count_lbl = tk.Label(tab, font=("Arial", 10),
                                 bg=self.PNL, fg="#64748B", anchor=tk.W)
            count_lbl.pack(fill=tk.X, padx=12, pady=(8, 2))

            lb = tk.Listbox(tab, bg=self.BG, fg="white",
                            font=("Arial", 11), selectbackground="#2563EB",
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
                if not raw:
                    return
                names = [n.strip() for part in raw.splitlines()
                         for n in part.split(",") if n.strip()]
                existing = set(self.students.get(gk, []))
                for n in names:
                    if n not in existing:
                        self.students.setdefault(gk, []).append(n)
                        lb.insert(tk.END, n)
                        existing.add(n)
                save_students(self.students)
                self._refresh()
                rc()

            def remove(lb=lb, gk=gkey, rc=_rc):
                sel = lb.curselection()
                if not sel:
                    return
                n = lb.get(sel[0])
                if messagebox.askyesno("Supprimer",
                                       f"Supprimer « {n} » ?", parent=win):
                    lb.delete(sel[0])
                    lst = self.students.get(gk, [])
                    if n in lst:
                        lst.remove(n)
                    save_students(self.students)
                    self._refresh()
                    rc()

            def rename(lb=lb, gk=gkey):
                sel = lb.curselection()
                if not sel:
                    return
                old = lb.get(sel[0])
                new = simpledialog.askstring(
                    "Renommer", f"Nouveau nom pour « {old} » :",
                    initialvalue=old, parent=win)
                if new and new.strip() and new.strip() != old:
                    n = new.strip()
                    lst = self.students.get(gk, [])
                    try:
                        lst[lst.index(old)] = n
                        lb.delete(sel[0])
                        lb.insert(sel[0], n)
                        save_students(self.students)
                        self._refresh()
                    except ValueError:
                        pass

            bf = tk.Frame(tab, bg=self.PNL)
            bf.pack(pady=6)
            for txt, col, fn in [("+ Ajouter",  "#059669", add),
                                  ("Renommer",   "#2563EB", rename),
                                  ("Supprimer",  "#DC2626", remove)]:
                tk.Button(bf, text=txt, bg=col, fg="white",
                          font=("Arial", 10, "bold"), relief=tk.FLAT,
                          padx=10, pady=7,
                          command=fn).pack(side=tk.LEFT, padx=4)

        tk.Button(win, text="Fermer", bg=self.PNL, fg="white",
                  font=("Arial", 11), relief=tk.FLAT,
                  padx=14, pady=6, command=win.destroy).pack(pady=10)

    # ── widget helpers ────────────────────────────────────────────────────────

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 9, "bold"),
                 bg=self.PNL, fg="#64748B", anchor=tk.W).pack(fill=tk.X)

    def _hsep(self, parent):
        tk.Frame(parent, bg=self.SEP, height=1).pack(fill=tk.X, pady=(2, 8))


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    WheelApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
