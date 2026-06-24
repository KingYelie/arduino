#!/usr/bin/env python3
"""
Roue des Élèves - Sélecteur aléatoire pour le passage au tableau
Supports: Demi-groupe 1 / Demi-groupe 2 / Classe entière
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import random
import math
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.json")
HISTORY_FILE  = os.path.join(BASE_DIR, "history.json")

COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2980B9", "#27AE60", "#8E44AD",
    "#16A085", "#D35400", "#C0392B", "#2471A3", "#1E8449",
    "#7D3C98", "#148F77", "#BA4A00", "#117A65", "#1A5276",
]

DEFAULT_STUDENTS = {
    "demi_groupe_1": [
        "Élève 1", "Élève 2", "Élève 3", "Élève 4",
        "Élève 5", "Élève 6", "Élève 7", "Élève 8",
    ],
    "demi_groupe_2": [
        "Élève 9",  "Élève 10", "Élève 11", "Élève 12",
        "Élève 13", "Élève 14", "Élève 15", "Élève 16",
    ],
}


# ── persistence ──────────────────────────────────────────────────────────────

def load_students():
    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {k: list(v) for k, v in DEFAULT_STUDENTS.items()}
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


# ── main application ──────────────────────────────────────────────────────────

class WheelApp:
    WHEEL_SIZE = 480       # canvas px
    DECEL      = 0.971     # speed multiplier each frame
    FPS_MS     = 16        # ~60 fps

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Roue des Élèves")
        self.root.configure(bg="#1C2833")
        self.root.geometry("1050x680")
        self.root.minsize(900, 620)

        self.students_data  = load_students()
        self.history        = load_history()
        self.current_mode   = tk.StringVar(value="classe_entiere")
        self.spinning       = False
        self.angle          = 0.0          # current rotation (degrees, CCW in Tk)
        self.speed          = 0.0
        self.winner_index   = None

        self._build_ui()
        self._refresh()

    # ── helpers ───────────────────────────────────────────────────────────────

    def get_students(self):
        m = self.current_mode.get()
        if m == "demi_groupe_1":
            return list(self.students_data.get("demi_groupe_1", []))
        if m == "demi_groupe_2":
            return list(self.students_data.get("demi_groupe_2", []))
        return (list(self.students_data.get("demi_groupe_1", [])) +
                list(self.students_data.get("demi_groupe_2", [])))

    def get_called(self):
        """Returns the set of names already called to the board."""
        return {e["student"] for e in self.history}

    def _mode_label(self, mode=None):
        m = mode or self.current_mode.get()
        return {"classe_entiere": "Classe entière",
                "demi_groupe_1":  "Demi-groupe 1",
                "demi_groupe_2":  "Demi-groupe 2"}.get(m, m)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── title bar ──
        tk.Label(self.root, text="Roue des Élèves",
                 font=("Arial", 22, "bold"), bg="#1C2833", fg="#F8F9FA").pack(pady=(12, 4))

        main = tk.Frame(self.root, bg="#1C2833")
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # ── left panel ──
        left = tk.Frame(main, bg="#2C3E50", bd=0, relief=tk.FLAT)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)
        left.config(width=210)

        tk.Label(left, text="Mode", font=("Arial", 13, "bold"),
                 bg="#2C3E50", fg="white").pack(pady=(18, 6))

        for label, value in [("Classe entière", "classe_entiere"),
                              ("Demi-groupe 1",  "demi_groupe_1"),
                              ("Demi-groupe 2",  "demi_groupe_2")]:
            tk.Radiobutton(left, text=label, variable=self.current_mode,
                           value=value, command=self._on_mode_change,
                           bg="#2C3E50", fg="white", selectcolor="#1C2833",
                           activebackground="#2C3E50", activeforeground="white",
                           font=("Arial", 11)).pack(anchor=tk.W, padx=22, pady=4)

        self._sep(left)

        tk.Label(left, text="Statistiques", font=("Arial", 12, "bold"),
                 bg="#2C3E50", fg="white").pack(pady=(6, 4))
        self.stats_lbl = tk.Label(left, text="", font=("Arial", 10),
                                  bg="#2C3E50", fg="#BDC3C7",
                                  wraplength=185, justify=tk.LEFT)
        self.stats_lbl.pack(padx=12, pady=4)

        self._sep(left)

        for text, color, cmd in [
            ("Gérer les élèves",         "#2980B9", self._manage_students),
            ("Voir l'historique",        "#27AE60", self._show_history),
            ("Réinitialiser historique", "#C0392B", self._reset_history),
        ]:
            tk.Button(left, text=text, bg=color, fg="white",
                      font=("Arial", 10, "bold"), relief=tk.FLAT,
                      cursor="hand2", padx=8, pady=6,
                      command=cmd).pack(fill=tk.X, padx=14, pady=3)

        # ── center (wheel) ──
        center = tk.Frame(main, bg="#1C2833")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, width=self.WHEEL_SIZE, height=self.WHEEL_SIZE,
                                bg="#1C2833", highlightthickness=0)
        self.canvas.pack(pady=6)

        self.result_var = tk.StringVar(value="Appuyez sur Tourner !")
        self.result_lbl = tk.Label(center, textvariable=self.result_var,
                                   font=("Arial", 15, "bold"),
                                   bg="#1C2833", fg="#F39C12", wraplength=430)
        self.result_lbl.pack(pady=4)

        self.spin_btn = tk.Button(center, text="TOURNER !",
                                  font=("Arial", 14, "bold"),
                                  bg="#E74C3C", fg="white", relief=tk.FLAT,
                                  cursor="hand2", padx=22, pady=10,
                                  command=self._spin)
        self.spin_btn.pack(pady=8)

        # ── right panel (recent history) ──
        right = tk.Frame(main, bg="#2C3E50", bd=0)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)
        right.config(width=195)

        tk.Label(right, text="Derniers passages",
                 font=("Arial", 12, "bold"), bg="#2C3E50", fg="white").pack(pady=(16, 6))

        lf = tk.Frame(right, bg="#2C3E50")
        lf.pack(fill=tk.BOTH, expand=True, padx=5, pady=4)
        sb = tk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_lb = tk.Listbox(lf, bg="#1C2833", fg="white",
                                  font=("Arial", 10), yscrollcommand=sb.set,
                                  selectbackground="#2980B9", relief=tk.FLAT,
                                  highlightthickness=0)
        self.hist_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.hist_lb.yview)

    # ── wheel drawing ─────────────────────────────────────────────────────────

    def _draw_wheel(self):
        self.canvas.delete("all")
        students = self.get_students()
        called   = self.get_called()
        cx = cy  = self.WHEEL_SIZE // 2
        r        = cx - 18

        if not students:
            self.canvas.create_text(cx, cy, text="Aucun élève\ndans ce groupe",
                                    font=("Arial", 18), fill="#BDC3C7")
            return

        n = len(students)
        sweep = 360 / n

        for i, name in enumerate(students):
            start = self.angle + i * sweep
            color = "#707B7C" if name in called else COLORS[i % len(COLORS)]

            self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                   start=start, extent=sweep,
                                   fill=color, outline="white", width=2)

            # text centred at 65% radius along mid-angle
            mid_rad = math.radians(start + sweep / 2)
            tx = cx + r * 0.65 * math.cos(mid_rad)
            ty = cy - r * 0.65 * math.sin(mid_rad)

            label = name if len(name) <= 11 else name[:9] + "…"
            fsize = max(6, min(11, int(170 / n)))
            self.canvas.create_text(tx, ty, text=label,
                                    font=("Arial", fsize, "bold"),
                                    fill="white")

        # centre disc
        self.canvas.create_oval(cx - 18, cy - 18, cx + 18, cy + 18,
                                fill="#1C2833", outline="white", width=2)

        # fixed arrow at top (points downward into wheel)
        ax = cx
        ay = cy - r - 4
        self.canvas.create_polygon(ax - 13, ay - 22,
                                   ax + 13, ay - 22,
                                   ax,      ay + 6,
                                   fill="#E74C3C", outline="white", width=1)

    def _sector_at_top(self):
        """Return the index of the student sector currently under the top arrow."""
        students = self.get_students()
        if not students:
            return None
        n     = len(students)
        sweep = 360 / n
        # Arrow sits at 90° in Tk canvas (counter-clockwise from 3 o'clock = top)
        adj   = (90 - self.angle) % 360
        return int(adj / sweep) % n

    # ── spin logic ────────────────────────────────────────────────────────────

    def _spin(self):
        if self.spinning:
            return
        students = self.get_students()
        if not students:
            messagebox.showwarning("Attention", "Aucun élève dans ce groupe !")
            return

        self.spinning = True
        self.spin_btn.config(state=tk.DISABLED)
        self.result_var.set("...")
        self.result_lbl.config(fg="#F39C12")

        self.speed = random.uniform(14, 22)
        self._animate()

    def _animate(self):
        self.angle  = (self.angle + self.speed) % 360
        self.speed *= self.DECEL
        self._draw_wheel()

        if self.speed > 0.25:
            self.root.after(self.FPS_MS, self._animate)
        else:
            self.spinning = False
            self.spin_btn.config(state=tk.NORMAL)
            self._on_stop()

    def _on_stop(self):
        students = self.get_students()
        if not students:
            return
        idx     = self._sector_at_top()
        winner  = students[idx]
        called  = self.get_called()

        if winner in called:
            self.result_var.set(f"{winner}\n(déjà passé·e au tableau)")
            self.result_lbl.config(fg="#E67E22")
        else:
            self.result_var.set(f"{winner} passe au tableau !")
            self.result_lbl.config(fg="#2ECC71")

        if messagebox.askyesno("Confirmation",
                               f"Enregistrer que {winner} est passé·e au tableau ?"):
            self._record(winner)

    def _record(self, name: str):
        entry = {
            "student": name,
            "mode":    self.current_mode.get(),
            "date":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        self.history.append(entry)
        save_history(self.history)
        self._refresh()

    # ── mode change ───────────────────────────────────────────────────────────

    def _on_mode_change(self):
        self.result_var.set("Appuyez sur Tourner !")
        self.result_lbl.config(fg="#F39C12")
        self._refresh()

    # ── full refresh ──────────────────────────────────────────────────────────

    def _refresh(self):
        self._draw_wheel()
        self._update_stats()
        self._update_hist_list()

    def _update_stats(self):
        students = self.get_students()
        called   = self.get_called()
        n_total  = len(students)
        n_called = sum(1 for s in students if s in called)
        txt = (f"{self._mode_label()}\n\n"
               f"Total :    {n_total} élève(s)\n"
               f"Passés :   {n_called}\n"
               f"Restants : {n_total - n_called}")
        self.stats_lbl.config(text=txt)

    def _update_hist_list(self):
        self.hist_lb.delete(0, tk.END)
        mode_abbr = {"classe_entiere": "CE", "demi_groupe_1": "G1", "demi_groupe_2": "G2"}
        for e in reversed(self.history[-25:]):
            abbr = mode_abbr.get(e.get("mode", ""), "?")
            self.hist_lb.insert(tk.END, f"[{abbr}] {e['student']}")

    # ── dialogs ───────────────────────────────────────────────────────────────

    def _reset_history(self):
        mode = self.current_mode.get()
        if not messagebox.askyesno(
                "Réinitialisation",
                f"Supprimer l'historique pour : {self._mode_label()} ?"):
            return
        if mode == "classe_entiere":
            self.history = []
        else:
            group_students = set(self.students_data.get(mode, []))
            self.history = [e for e in self.history
                            if e["student"] not in group_students]
        save_history(self.history)
        self._refresh()

    def _show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Historique complet")
        win.configure(bg="#1C2833")
        win.geometry("520x420")

        tk.Label(win, text="Historique des passages au tableau",
                 font=("Arial", 13, "bold"), bg="#1C2833", fg="white").pack(pady=10)

        fr = tk.Frame(win, bg="#1C2833")
        fr.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg="#2C3E50", fg="white", font=("Courier", 11),
                        yscrollcommand=sb.set, selectbackground="#2980B9",
                        relief=tk.FLAT, highlightthickness=0)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=lb.yview)

        mode_labels = {"demi_groupe_1": "Demi-groupe 1",
                       "demi_groupe_2": "Demi-groupe 2",
                       "classe_entiere": "Classe entière"}
        for e in reversed(self.history):
            ml = mode_labels.get(e.get("mode", ""), "?")
            lb.insert(tk.END, f"  {e.get('date',''):16}  {e['student']:<20}  [{ml}]")

        tk.Button(win, text="Fermer", bg="#E74C3C", fg="white",
                  font=("Arial", 11), relief=tk.FLAT, padx=14, pady=6,
                  command=win.destroy).pack(pady=10)

    def _manage_students(self):
        win = tk.Toplevel(self.root)
        win.title("Gestion des élèves")
        win.configure(bg="#1C2833")
        win.geometry("580x480")

        tk.Label(win, text="Gestion des élèves",
                 font=("Arial", 13, "bold"), bg="#1C2833", fg="white").pack(pady=10)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        style = ttk.Style()
        style.configure("TNotebook",       background="#1C2833")
        style.configure("TNotebook.Tab",   background="#2C3E50", foreground="white",
                        padding=[10, 4])

        for gkey, gname in [("demi_groupe_1", "Demi-groupe 1"),
                             ("demi_groupe_2", "Demi-groupe 2")]:
            tab = tk.Frame(nb, bg="#2C3E50")
            nb.add(tab, text=gname)

            lb = tk.Listbox(tab, bg="#1C2833", fg="white", font=("Arial", 11),
                            selectbackground="#2980B9", relief=tk.FLAT,
                            highlightthickness=0, height=14)
            lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            for s in self.students_data.get(gkey, []):
                lb.insert(tk.END, s)

            def add(lb=lb, gk=gkey):
                name = simpledialog.askstring("Ajouter un élève",
                                              "Nom complet :", parent=win)
                if name and name.strip():
                    n = name.strip()
                    if n not in self.students_data.get(gk, []):
                        self.students_data.setdefault(gk, []).append(n)
                        lb.insert(tk.END, n)
                        save_students(self.students_data)
                        self._refresh()

            def remove(lb=lb, gk=gkey):
                sel = lb.curselection()
                if not sel:
                    return
                n = lb.get(sel[0])
                if messagebox.askyesno("Supprimer", f"Supprimer {n} de {gk} ?",
                                       parent=win):
                    lb.delete(sel[0])
                    if n in self.students_data.get(gk, []):
                        self.students_data[gk].remove(n)
                        save_students(self.students_data)
                        self._refresh()

            def rename(lb=lb, gk=gkey):
                sel = lb.curselection()
                if not sel:
                    return
                old = lb.get(sel[0])
                new = simpledialog.askstring("Renommer", f"Nouveau nom pour {old} :",
                                             initialvalue=old, parent=win)
                if new and new.strip() and new.strip() != old:
                    n = new.strip()
                    idx = self.students_data.get(gk, []).index(old)
                    self.students_data[gk][idx] = n
                    lb.delete(sel[0])
                    lb.insert(sel[0], n)
                    save_students(self.students_data)
                    self._refresh()

            bf = tk.Frame(tab, bg="#2C3E50")
            bf.pack(pady=6)
            for txt, col, fn in [("+ Ajouter",    "#27AE60", add),
                                  ("Renommer",     "#2980B9", rename),
                                  ("- Supprimer",  "#C0392B", remove)]:
                tk.Button(bf, text=txt, bg=col, fg="white",
                          font=("Arial", 10, "bold"), relief=tk.FLAT,
                          padx=10, pady=6, command=fn).pack(side=tk.LEFT, padx=5)

        tk.Button(win, text="Fermer", bg="#2C3E50", fg="white",
                  font=("Arial", 11), relief=tk.FLAT, padx=14, pady=6,
                  command=win.destroy).pack(pady=10)

    # ── utility ───────────────────────────────────────────────────────────────

    def _sep(self, parent):
        tk.Frame(parent, bg="#566573", height=1).pack(fill=tk.X, padx=10, pady=10)


# ── entry point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    WheelApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
