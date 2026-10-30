"""NEO-WORLD v2 - defenda o núcleo com uma fábrica.

Controles:
  1-7           escolher construção (ou clique nos botões embaixo)
  R             girar a esteira
  Clique        construir (arraste pra fazer linhas) | Botão direito: apagar
  Espaço        chamar a próxima onda agora
  P pausa       T velocidade x1/x2       Enter reinicia (fim de jogo)

Brocas produzem itens; esteiras levam até o núcleo (recurso) ou até as
torres (munição). Inimigos terrestres atacam o que estiver no caminho.
"""
import tkinter as tk
import random
import math
from collections import Counter

W, H, S = 28, 18, 32
HUD, BAR = 60, 62
FPS = 20
WAVE_TIME = 30 * FPS
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
ARROW = ["→", "↓", "←", "↑"]
AMMO_ITEM, AMMO_MAX = 5, 20
F = "TkDefaultFont"

# ------------------------------------------------------------ construções
B = {
    "drill":  dict(nome="Broca", cost=10, hp=40, cor="#e0a82e", info="só no minério"),
    "conv":   dict(nome="Esteira", cost=1, hp=15, cor="#2a313b", info="R gira"),
    "turret": dict(nome="Torre", cost=15, hp=60, cor="#3bb273", info="equilibrada",
                   rng=4.5, dmg=5, cd=8, use=1, letra=""),
    "sniper": dict(nome="Sniper", cost=35, hp=50, cor="#7aa2ff", info="longo alcance",
                   rng=8, dmg=30, cd=32, use=2, letra="S"),
    "cannon": dict(nome="Canhão", cost=40, hp=90, cor="#e07b39", info="área, só solo",
                   rng=5, dmg=14, cd=26, use=2, splash=1.4, ground=True, letra="C"),
    "frost":  dict(nome="Gelo", cost=30, hp=60, cor="#5ad1e6", info="lentidão em área",
                   rng=3.8, dmg=2, cd=12, use=1, letra="F"),
    "wall":   dict(nome="Muro", cost=6, hp=150, cor="#8a8f98", info="bloqueia"),
}
ORDER = list(B)
TURRETS = [k for k in B if "rng" in B[k]]

# --------------------------------------------------------------- inimigos
E = {
    "grunt":  dict(nome="Soldado",  hp=10, sp=.034, core=5,  armor=0, atk=6,  cor="#e5484d", r=8,  fly=False, pts=1, rew=1),
    "runner": dict(nome="Corredor", hp=6,  sp=.062, core=3,  armor=0, atk=4,  cor="#ff9f43", r=6,  fly=False, pts=2, rew=1),
    "tank":   dict(nome="Tanque",   hp=45, sp=.020, core=12, armor=2, atk=22, cor="#8e5bd6", r=11, fly=False, pts=6, rew=4),
    "flyer":  dict(nome="Voador",   hp=9,  sp=.042, core=6,  armor=0, atk=0,  cor="#4cc9f0", r=7,  fly=True,  pts=3, rew=2),
    "boss":   dict(nome="CHEFE",    hp=0,  sp=.017, core=35, armor=3, atk=40, cor="#ff2e63", r=17, fly=False, pts=0, rew=25),
}


class Game:
    def __init__(self, root):
        self.root = root
        root.title("NEO-WORLD")
        root.resizable(False, False)
        self.cv = tk.Canvas(root, width=W * S, height=HUD + H * S + BAR,
                            bg="#0e1116", highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<Button-3>", self.on_erase)
        self.cv.bind("<B3-Motion>", self.on_erase)
        self.cv.bind("<Motion>", self.on_move)
        root.bind("<Key>", self.on_key)
        self.reset()
        self.loop()

    # ---------------------------------------------------------- estado inicial
    def reset(self):
        self.t = 0
        self.res = 40
        self.sel = "drill"
        self.rot = 0
        self.grid = {}
        self.ore = set()
        self.enemies = []
        self.fx = []
        self.wave = 0
        self.kills = 0
        self.countdown = 25 * FPS
        self.spawn_list = []
        self.spawn_cd = 0
        self.sides_cur = [0]
        self.active = False
        self.msg = None
        self.mouse = None
        self.paused = False
        self.speed = 1
        self.over = False
        self.plan = self.make_wave(1)

        cx, cy = W // 2 - 1, H // 2 - 1
        self.core = {"t": "core", "x": cx, "y": cy, "hp": 100, "mhp": 100}
        for dx in (0, 1):
            for dy in (0, 1):
                self.grid[(cx + dx, cy + dy)] = self.core

        made = 0
        for _ in range(300):
            if made >= 6:
                break
            x, y = random.randint(2, W - 3), random.randint(2, H - 3)
            if not 4 <= math.hypot(x - W / 2, y - H / 2) <= 9:
                continue
            made += 1
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    p = (x + dx, y + dy)
                    if (dx * dx + dy * dy <= 5 and random.random() < 0.85
                            and 0 <= p[0] < W and 0 <= p[1] < H and p not in self.grid):
                        self.ore.add(p)

        self.cv.delete("all")
        for x in range(W):
            for y in range(H):
                px, py = x * S, y * S + HUD
                is_ore = (x, y) in self.ore
                self.cv.create_rectangle(px, py, px + S, py + S,
                                         fill="#4a3b17" if is_ore else "#161b22",
                                         outline="#1e252e")
                if is_ore:
                    self.cv.create_oval(px + 10, py + 10, px + S - 10, py + S - 10,
                                        fill="#c9a227", outline="")

    # ---------------------------------------------------------------- entrada
    def cell(self, e):
        return e.x // S, (e.y - HUD) // S

    def on_move(self, e):
        self.mouse = (e.x, e.y)

    def on_press(self, e):
        self.mouse = (e.x, e.y)
        if e.y >= HUD + H * S:                       # barra de construção
            i = e.x // (W * S // len(ORDER))
            if i < len(ORDER):
                self.sel = ORDER[i]
            return
        self.place(*self.cell(e))

    def on_drag(self, e):
        self.mouse = (e.x, e.y)
        self.place(*self.cell(e))

    def on_erase(self, e):
        self.mouse = (e.x, e.y)
        self.erase(*self.cell(e))

    def on_key(self, e):
        k = e.keysym.lower()
        if k.isdigit() and 1 <= int(k) <= len(ORDER):
            self.sel = ORDER[int(k) - 1]
        elif k == "r":
            self.rot = (self.rot + 1) % 4
        elif k == "space" and not self.over:
            self.countdown = 1
        elif k == "p":
            self.paused = not self.paused
        elif k == "t":
            self.speed = 3 - self.speed
        elif k == "return" and self.over:
            self.reset()

    # ------------------------------------------------------------- construção
    def place(self, x, y):
        if self.over or not (0 <= x < W and 0 <= y < H):
            return
        t, cell = self.sel, (x, y)
        d, b = B[t], self.grid.get(cell)
        if t == "conv" and b and b["t"] == "conv":
            b["d"] = self.rot
            return
        if b or (t == "drill" and cell not in self.ore) or self.res < d["cost"]:
            return
        self.res -= d["cost"]
        b = {"t": t, "x": x, "y": y, "hp": d["hp"], "mhp": d["hp"]}
        if t == "conv":
            b.update(d=self.rot, item=False)
        elif t == "drill":
            b["cd"] = random.randint(0, 20)
        elif t in TURRETS:
            b.update(ammo=0, cd=0)
        self.grid[cell] = b

    def erase(self, x, y):
        b = self.grid.get((x, y))
        if self.over or not b or b["t"] == "core":
            return
        self.res += B[b["t"]]["cost"] // 2
        del self.grid[(x, y)]

    # ------------------------------------------------------------------ ondas
    def make_wave(self, n):
        pts = 3 + 3 * n
        lst = []
        if n % 5 == 0:
            lst.append("boss")
            pts = int(pts * 0.6)
        pool = ["grunt"] + ["runner"] * (n >= 2) + ["tank"] * (n >= 3) + ["flyer"] * (n >= 4)
        peso = {"grunt": 5, "runner": 3, "tank": 1.5, "flyer": 2}
        resto = []
        while True:
            opts = [k for k in pool if E[k]["pts"] <= pts]
            if not opts:
                break
            k = random.choices(opts, [peso[o] for o in opts])[0]
            resto.append(k)
            pts -= E[k]["pts"]
        random.shuffle(resto)
        return {"list": lst + resto,
                "sides": random.sample(range(4), 1 if n < 3 else 2 if n < 8 else 3)}

    def say(self, text, color):
        self.msg = [text, color, 50]

    def start_wave(self):
        self.wave += 1
        self.spawn_list = list(self.plan["list"])
        self.sides_cur = self.plan["sides"]
        self.active = True
        boss = "boss" in self.spawn_list
        self.say(f"ONDA {self.wave}" + ("  -  CHEFE!" if boss else ""),
                 "#ff2e63" if boss else "#ffd34d")
        self.plan = self.make_wave(self.wave + 1)
        self.countdown = WAVE_TIME

    def spawn(self, kind, x=None, y=None):
        st = E[kind]
        hp = 200 + 60 * self.wave if kind == "boss" else st["hp"] * (1 + 0.15 * (self.wave - 1))
        if x is None:
            s = random.choice(self.sides_cur)
            if s == 0:
                x, y = -.5, random.uniform(0, H)
            elif s == 1:
                x, y = W + .5, random.uniform(0, H)
            elif s == 2:
                x, y = random.uniform(0, W), -.5
            else:
                x, y = random.uniform(0, W), H + .5
        self.enemies.append({"k": kind, "x": x, "y": y, "hp": hp, "max": hp,
                             "sp": st["sp"] * min(1.6, 1 + 0.01 * self.wave),
                             "armor": st["armor"], "fly": st["fly"],
                             "slow": 0, "t": 0, "atk": None})

    # ------------------------------------------------------------- simulação
    def give(self, b):
        if b["t"] == "core":
            self.res += 1
            return True
        if b["t"] in TURRETS and b["ammo"] <= AMMO_MAX - AMMO_ITEM:
            b["ammo"] += AMMO_ITEM
            return True
        if b["t"] == "conv" and not b["item"]:
            b["item"] = True
            return True
        return False

    def hit(self, e, dmg):
        e["hp"] -= max(1, dmg - e["armor"])

    def fire(self, b):
        d = B[b["t"]]
        b["cd"] = max(0, b["cd"] - 1)
        if b["cd"] or b["ammo"] < d["use"]:
            return
        tx, ty = b["x"] + .5, b["y"] + .5
        near = [e for e in self.enemies
                if not (d.get("ground") and e["fly"])
                and math.hypot(e["x"] - tx, e["y"] - ty) <= d["rng"]]
        if not near:
            return
        b["ammo"] -= d["use"]
        b["cd"] = d["cd"]
        t = b["t"]
        if t == "frost":
            for e in near:
                e["slow"] = 30
                self.hit(e, d["dmg"])
            self.fx.append({"k": "ring", "x": tx, "y": ty, "r": d["rng"], "life": 6, "c": d["cor"]})
            return
        if t == "sniper":
            e = max(near, key=lambda e: e["hp"])
        else:
            e = min(near, key=lambda e: math.hypot(e["x"] - tx, e["y"] - ty))
        if t == "cannon":
            for o in self.enemies:
                if not o["fly"] and math.hypot(o["x"] - e["x"], o["y"] - e["y"]) <= d["splash"]:
                    self.hit(o, d["dmg"])
            self.fx.append({"k": "ring", "x": e["x"], "y": e["y"], "r": d["splash"], "life": 5, "c": d["cor"]})
        else:
            self.hit(e, d["dmg"])
        self.fx.append({"k": "line", "x": tx, "y": ty, "x2": e["x"], "y2": e["y"], "life": 3, "c": d["cor"]})

    def update(self):
        self.t += 1
        g = self.grid
        blds = list(g.values())

        if self.t % 4 == 0:                                 # esteiras
            moved = set()
            for b in blds:
                if b["t"] == "conv" and b["item"] and id(b) not in moved:
                    dx, dy = DIRS[b["d"]]
                    n = g.get((b["x"] + dx, b["y"] + dy))
                    if n and self.give(n):
                        b["item"] = False
                        if n["t"] == "conv":
                            moved.add(id(n))

        for b in blds:                                      # brocas
            if b["t"] != "drill":
                continue
            b["cd"] += 1
            if b["cd"] < 30:
                continue
            for dx, dy in DIRS:
                n = g.get((b["x"] + dx, b["y"] + dy))
                if not n:
                    continue
                if n["t"] == "conv":
                    ndx, ndy = DIRS[n["d"]]
                    if (n["x"] + ndx, n["y"] + ndy) == (b["x"], b["y"]):
                        continue
                if self.give(n):
                    b["cd"] = 0
                    break

        for b in blds:                                      # torres
            if b["t"] in TURRETS:
                self.fire(b)

        cx, cy = self.core["x"] + 1, self.core["y"] + 1     # inimigos
        for e in self.enemies[:]:
            st = E[e["k"]]
            if e["hp"] <= 0:
                self.enemies.remove(e)
                self.res += st["rew"]
                self.kills += 1
                continue
            e["slow"] = max(0, e["slow"] - 1)
            d = math.hypot(cx - e["x"], cy - e["y"])
            if d < 1.3:
                self.core["hp"] -= st["core"]
                self.enemies.remove(e)
                self.fx.append({"k": "ring", "x": cx, "y": cy, "r": 1.6, "life": 6, "c": "#ff6b6b"})
                continue
            ux, uy = (cx - e["x"]) / d, (cy - e["y"]) / d
            if e["k"] == "boss":
                e["t"] += 1
                if e["t"] % 80 == 0:                        # chefe invoca soldados
                    self.spawn("grunt", e["x"], e["y"])
            blocked = None
            if not e["fly"] and st["atk"]:
                tb = g.get((math.floor(e["x"] + ux * .55), math.floor(e["y"] + uy * .55)))
                if tb and tb["t"] != "core":
                    blocked = tb
            if blocked:
                blocked["hp"] -= st["atk"] / FPS
                e["atk"] = blocked
                if blocked["hp"] <= 0:
                    g.pop((blocked["x"], blocked["y"]), None)
            else:
                e["atk"] = None
                v = e["sp"] * (.5 if e["slow"] else 1)
                e["x"] += ux * v
                e["y"] += uy * v

        self.countdown -= 1                                 # ondas
        if self.countdown <= 0:
            self.start_wave()
        if self.spawn_list:
            self.spawn_cd -= 1
            if self.spawn_cd <= 0:
                k = self.spawn_list.pop(0)
                self.spawn(k)
                self.spawn_cd = 40 if k == "boss" else 10
        if self.active and not self.spawn_list and not self.enemies:
            bonus = 5 + 2 * self.wave
            self.res += bonus
            self.active = False
            self.say(f"Onda {self.wave} concluída!  +{bonus}", "#6be07a")

        for f in self.fx:
            f["life"] -= 1
        self.fx = [f for f in self.fx if f["life"] > 0]
        if self.msg:
            self.msg[2] -= 1
            if self.msg[2] <= 0:
                self.msg = None
        if self.core["hp"] <= 0:
            self.over = True

    # --------------------------------------------------------------- desenho
    def draw_building(self, b, px, py):
        c, t = self.cv, b["t"]
        d = B[t]
        if t == "drill":
            c.create_rectangle(px + 5, py + 5, px + S - 5, py + S - 5, fill=d["cor"],
                               outline="#fff3c4", tags="d")
            c.create_oval(px + 12, py + 12, px + S - 12, py + S - 12, fill="#3b2c0a", outline="", tags="d")
        elif t == "conv":
            c.create_rectangle(px + 2, py + 2, px + S - 2, py + S - 2, fill=d["cor"], outline="", tags="d")
            c.create_text(px + S / 2, py + S / 2, text=ARROW[b["d"]], fill="#8b97a6",
                          font=(F, 14), tags="d")
            if b["item"]:
                c.create_oval(px + 11, py + 11, px + S - 11, py + S - 11, fill="#ffd34d", outline="", tags="d")
        elif t == "wall":
            c.create_rectangle(px + 1, py + 1, px + S - 1, py + S - 1, fill=d["cor"], outline="#c5cad3",
                               width=2, tags="d")
            c.create_line(px + 1, py + S / 2, px + S - 1, py + S / 2, fill="#5d626b", tags="d")
        else:                                               # torres
            c.create_oval(px + 3, py + 3, px + S - 3, py + S - 3, fill=d["cor"], outline="#e8fff3",
                          width=2, tags="d")
            if d["letra"]:
                c.create_text(px + S / 2, py + S / 2 - 2, text=d["letra"], fill="#0e1116",
                              font=(F, 12, "bold"), tags="d")
            c.create_rectangle(px + 4, py + S - 7, px + 4 + (S - 8) * b["ammo"] / AMMO_MAX, py + S - 3,
                               fill="#ffd34d", outline="", tags="d")
        if b["hp"] < b["mhp"]:
            c.create_rectangle(px + 3, py + 1, px + 3 + (S - 6) * max(0, b["hp"]) / b["mhp"], py + 4,
                               fill="#ff6b6b", outline="", tags="d")

    def draw_enemy(self, e):
        c, st = self.cv, E[e["k"]]
        px, py, r = e["x"] * S, e["y"] * S + HUD, st["r"]
        if e["atk"]:
            c.create_line(px, py, (e["atk"]["x"] + .5) * S, (e["atk"]["y"] + .5) * S + HUD,
                          fill="#ff6b6b", width=2, tags="d")
        outline = "#5ad1e6" if e["slow"] else ("#ffd34d" if e["k"] == "boss" else "#ffffff")
        if e["fly"]:
            c.create_polygon(px, py - r, px + r, py + r, px - r, py + r, fill=st["cor"],
                             outline=outline, tags="d")
        else:
            c.create_oval(px - r, py - r, px + r, py + r, fill=st["cor"], outline=outline,
                          width=3 if e["k"] == "boss" else 1, tags="d")
        c.create_rectangle(px - r, py - r - 6, px + r, py - r - 3, fill="#3a1d1f", outline="", tags="d")
        c.create_rectangle(px - r, py - r - 6, px - r + 2 * r * max(0, e["hp"]) / e["max"], py - r - 3,
                           fill="#6be07a", outline="", tags="d")

    def draw_bar(self, x0, y0, x1, y1, frac, color, text=None):
        c = self.cv
        c.create_rectangle(x0, y0, x1, y1, fill="#26303b", outline="", tags="d")
        c.create_rectangle(x0, y0, x0 + (x1 - x0) * max(0, min(1, frac)), y1, fill=color, outline="", tags="d")
        if text:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text, fill="#ffffff",
                          font=(F, 9, "bold"), tags="d")

    def draw(self):
        c = self.cv
        c.delete("d")
        W_PX = W * S

        if self.countdown < 10 * FPS and not self.over and self.t % 10 < 6:   # aviso de onda
            for s in self.plan["sides"]:
                r = [(0, HUD, 5, HUD + H * S), (W_PX - 5, HUD, W_PX, HUD + H * S),
                     (0, HUD, W_PX, HUD + 5), (0, HUD + H * S - 5, W_PX, HUD + H * S)][s]
                c.create_rectangle(*r, fill="#ff2e63", outline="", tags="d")

        for (x, y), b in self.grid.items():
            px, py = x * S, y * S + HUD
            if b["t"] == "core":
                if (x, y) == (b["x"], b["y"]):
                    c.create_rectangle(px + 2, py + 2, px + 2 * S - 2, py + 2 * S - 2, fill="#2f8fe0",
                                       outline="#9fd0ff", width=2, tags="d")
                    c.create_text(px + S, py + S, text="NÚCLEO", fill="white", font=(F, 10, "bold"), tags="d")
            else:
                self.draw_building(b, px, py)

        for f in self.fx:
            if f["k"] == "line":
                c.create_line(f["x"] * S, f["y"] * S + HUD, f["x2"] * S, f["y2"] * S + HUD,
                              fill=f["c"], width=2, tags="d")
            else:
                r = f["r"] * S
                c.create_oval(f["x"] * S - r, f["y"] * S + HUD - r, f["x"] * S + r, f["y"] * S + HUD + r,
                              outline=f["c"], width=2, tags="d")
        for e in self.enemies:
            self.draw_enemy(e)

        # fantasma de construção + alcance
        tip = None
        if self.mouse and not self.over and HUD <= self.mouse[1] < HUD + H * S:
            gx, gy = self.mouse[0] // S, (self.mouse[1] - HUD) // S
            b = self.grid.get((gx, gy))
            if b and b["t"] != "core":
                tip = (b["t"], b)
            elif not b:
                d = B[self.sel]
                ok = self.res >= d["cost"] and (self.sel != "drill" or (gx, gy) in self.ore)
                col = "#6be07a" if ok else "#ff6b6b"
                px, py = gx * S, gy * S + HUD
                c.create_rectangle(px + 2, py + 2, px + S - 2, py + S - 2, outline=col, width=2, tags="d")
                if self.sel == "conv":
                    c.create_text(px + S / 2, py + S / 2, text=ARROW[self.rot], fill=col, font=(F, 14), tags="d")
                if "rng" in d:
                    r = d["rng"] * S
                    c.create_oval(px + S / 2 - r, py + S / 2 - r, px + S / 2 + r, py + S / 2 + r,
                                  outline="#ffffff", dash=(3, 4), tags="d")

        # ---- HUD de cima
        c.create_rectangle(0, 0, W_PX, HUD, fill="#0b0e13", outline="", tags="d")
        c.create_rectangle(12, 9, 26, 23, fill="#c9a227", outline="", tags="d")
        c.create_text(32, 16, anchor="w", text=str(self.res), fill="#ffd34d", font=(F, 13, "bold"), tags="d")
        hp = max(0, int(self.core["hp"]))
        c.create_text(110, 16, anchor="w", text="NÚCLEO", fill="#9fd0ff", font=(F, 9, "bold"), tags="d")
        self.draw_bar(165, 8, 325, 24, hp / 100,
                      "#6be07a" if hp > 50 else "#ffd34d" if hp > 25 else "#ff6b6b", f"{hp}/100")
        c.create_text(345, 16, anchor="w", text=f"ONDA {self.wave}", fill="#e6edf3", font=(F, 12, "bold"), tags="d")
        c.create_text(430, 16, anchor="w", text="próxima", fill="#7d8896", font=(F, 9), tags="d")
        self.draw_bar(485, 8, 600, 24, 1 - self.countdown / WAVE_TIME, "#4a6fa5",
                      f"{self.countdown // FPS + 1}s")
        c.create_text(620, 16, anchor="w", text=f"Inimigos: {len(self.enemies)} (+{len(self.spawn_list)})",
                      fill="#e6edf3", tags="d")
        c.create_text(W_PX - 10, 16, anchor="e", text=f"Abates: {self.kills}", fill="#7d8896", tags="d")

        cnt = Counter(self.plan["list"])
        x = 12
        c.create_text(x, 44, anchor="w", text=f"Onda {self.wave + 1}:", fill="#7d8896", tags="d")
        x = 80
        if cnt["boss"]:
            c.create_text(x, 44, anchor="w", text="CHEFE", fill="#ff2e63", font=(F, 10, "bold"), tags="d")
            x += 60
        for k in ("grunt", "runner", "tank", "flyer"):
            if cnt[k]:
                s = f"{cnt[k]}x {E[k]['nome']}"
                c.create_text(x, 44, anchor="w", text=s, fill=E[k]["cor"], tags="d")
                x += len(s) * 7 + 16
        c.create_text(W_PX - 10, 44, anchor="e", fill="#5d6773", tags="d",
                      text=f"P pausa  |  T velocidade x{self.speed}  |  Espaço chama onda")

        # ---- barra de construção
        y0, bw = HUD + H * S, W_PX // len(ORDER)
        c.create_rectangle(0, y0, W_PX, y0 + BAR, fill="#0b0e13", outline="", tags="d")
        for i, k in enumerate(ORDER):
            d, x0 = B[k], i * bw
            c.create_rectangle(x0 + 3, y0 + 4, x0 + bw - 3, y0 + BAR - 3, fill="#161b22",
                               outline="#ffffff" if k == self.sel else "#2a313b",
                               width=2 if k == self.sel else 1, tags="d")
            c.create_rectangle(x0 + 10, y0 + 11, x0 + 22, y0 + 23, fill=d["cor"], outline="#c5cad3", tags="d")
            c.create_text(x0 + 28, y0 + 17, anchor="w", text=f"[{i + 1}] {d['nome']}", fill="#e6edf3",
                          font=(F, 10, "bold"), tags="d")
            c.create_text(x0 + 10, y0 + 36, anchor="w", text=f"custo {d['cost']}",
                          fill="#ffd34d" if self.res >= d["cost"] else "#ff6b6b", tags="d")
            extra = f"  dano {d['dmg']}" if "dmg" in d else ""
            c.create_text(x0 + 10, y0 + 51, anchor="w", text=d["info"] + extra, fill="#7d8896",
                          font=(F, 8), tags="d")

        boss = next((e for e in self.enemies if e["k"] == "boss"), None)
        if boss:
            self.draw_bar(W_PX / 2 - 200, HUD + 8, W_PX / 2 + 200, HUD + 22, boss["hp"] / boss["max"],
                          "#ff2e63", f"CHEFE  {max(0, int(boss['hp']))}")
        if self.msg:
            c.create_text(W_PX / 2, HUD + 80, text=self.msg[0], fill=self.msg[1],
                          font=(F, 26, "bold"), tags="d")
        if tip:
            t, b = tip
            lines = [B[t]["nome"], f"HP {int(b['hp'])}/{b['mhp']}"]
            if t in TURRETS:
                lines.append(f"munição {b['ammo']}/{AMMO_MAX}")
            mx, my = self.mouse[0] + 14, self.mouse[1] + 14
            c.create_rectangle(mx, my, mx + 120, my + 14 * len(lines) + 8, fill="#0b0e13",
                               outline="#5d6773", tags="d")
            for i, s in enumerate(lines):
                c.create_text(mx + 6, my + 11 + 14 * i, anchor="w", text=s, fill="#e6edf3", tags="d")

        if self.paused and not self.over:
            c.create_text(W_PX / 2, HUD + H * S / 2, text="PAUSADO", fill="#e6edf3",
                          font=(F, 30, "bold"), tags="d")
        if self.over:
            cx0, cy0 = W_PX / 2, HUD + H * S / 2
            c.create_rectangle(cx0 - 210, cy0 - 55, cx0 + 210, cy0 + 55, fill="#1a0f12",
                               outline="#e5484d", width=2, tags="d")
            c.create_text(cx0, cy0 - 18, text="NÚCLEO DESTRUÍDO", fill="#ff8a8e",
                          font=(F, 18, "bold"), tags="d")
            c.create_text(cx0, cy0 + 20, fill="#e6edf3", tags="d",
                          text=f"Onda {self.wave}  |  {self.kills} abates  |  Enter pra recomeçar")

    def loop(self):
        if not self.paused:
            for _ in range(self.speed):
                if not self.over:
                    self.update()
        self.draw()
        self.root.after(1000 // FPS, self.loop)


if __name__ == "__main__":
    root = tk.Tk()
    Game(root)
    root.mainloop()
