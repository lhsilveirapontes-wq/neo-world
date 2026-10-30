"""NEO-WORLD - protótipo: defenda o núcleo de ondas de inimigos com uma fábrica.

Controles:
  1 / 2 / 3     escolher Broca / Esteira / Torre
  R             girar a esteira
  Clique        construir (arraste pra fazer linhas de esteira)
  Botão direito apagar (devolve metade do custo)
  Espaço        chamar a próxima onda agora
  Enter         reiniciar (depois do fim de jogo)

Como funciona: brocas em cima do minério produzem itens. Esteiras levam os itens
até o núcleo (vira recurso pra construir) ou até as torres (vira munição).
"""
import tkinter as tk
import random
import math

W, H, S, HUD = 28, 18, 32, 48          # largura/altura em células, tamanho da célula, altura do HUD
FPS = 20
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
ARROW = ["→", "↓", "←", "↑"]
COST = {"drill": 10, "conv": 1, "turret": 15}
NOME = {"drill": "Broca", "conv": "Esteira", "turret": "Torre"}
AMMO_ITEM, AMMO_MAX = 5, 20             # tiros por item / máximo de tiros guardados
RANGE, DMG = 4.5, 5                     # alcance (em células) e dano da torre


class Game:
    def __init__(self, root):
        self.root = root
        root.title("NEO-WORLD")
        root.resizable(False, False)
        self.cv = tk.Canvas(root, width=W * S, height=H * S + HUD,
                            bg="#0e1116", highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self.on_click)
        self.cv.bind("<B1-Motion>", self.on_click)
        self.cv.bind("<Button-3>", self.on_erase)
        self.cv.bind("<B3-Motion>", self.on_erase)
        root.bind("<Key>", self.on_key)
        self.reset()
        self.loop()

    # estado inicial
    def reset(self):
        self.t = 0
        self.res = 40
        self.sel = "drill"
        self.rot = 0
        self.grid = {}
        self.ore = set()
        self.enemies = []
        self.shots = []
        self.wave = 0
        self.countdown = 20 * FPS
        self.to_spawn = 0
        self.spawn_cd = 0
        self.over = False

        cx, cy = W // 2 - 1, H // 2 - 1
        self.core = {"t": "core", "x": cx, "y": cy, "hp": 100}
        for dx in (0, 1):
            for dy in (0, 1):
                self.grid[(cx + dx, cy + dy)] = self.core

        # minérios
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

    def cell(self, e):
        return e.x // S, (e.y - HUD) // S

    def on_click(self, e):
        self.place(*self.cell(e))

    def on_erase(self, e):
        self.erase(*self.cell(e))

    def on_key(self, e):
        k = e.keysym.lower()
        if k in ("1", "2", "3"):
            self.sel = ("drill", "conv", "turret")[int(k) - 1]
        elif k == "r":
            self.rot = (self.rot + 1) % 4
        elif k == "space":
            self.countdown = 1
        elif k == "return" and self.over:
            self.reset()

    # construção
    def place(self, x, y):
        if self.over or not (0 <= x < W and 0 <= y < H):
            return
        t, cell = self.sel, (x, y)
        b = self.grid.get(cell)
        if t == "conv" and b and b["t"] == "conv":      # clicar numa esteira gira ela
            b["d"] = self.rot
            return
        if b or (t == "drill" and cell not in self.ore) or self.res < COST[t]:
            return
        self.res -= COST[t]
        b = {"t": t, "x": x, "y": y}
        if t == "conv":
            b.update(d=self.rot, item=False)
        elif t == "drill":
            b["cd"] = random.randint(0, 20)
        elif t == "turret":
            b.update(ammo=0, cd=0)
        self.grid[cell] = b

    def erase(self, x, y):
        b = self.grid.get((x, y))
        if self.over or not b or b["t"] == "core":
            return
        self.res += COST[b["t"]] // 2
        del self.grid[(x, y)]

    # simulação
    def give(self, b):
        """Tenta entregar 1 item pra construção b. Retorna True se aceitou."""
        if b["t"] == "core":
            self.res += 1
            return True
        if b["t"] == "turret" and b["ammo"] <= AMMO_MAX - AMMO_ITEM:
            b["ammo"] += AMMO_ITEM
            return True
        if b["t"] == "conv" and not b["item"]:
            b["item"] = True
            return True
        return False

    def spawn(self):
        s = random.randint(0, 3)
        if s == 0:
            x, y = -0.5, random.uniform(0, H)
        elif s == 1:
            x, y = W + 0.5, random.uniform(0, H)
        elif s == 2:
            x, y = random.uniform(0, W), -0.5
        else:
            x, y = random.uniform(0, W), H + 0.5
        hp = 8 + 4 * self.wave
        self.enemies.append({"x": x, "y": y, "hp": hp, "max": hp,
                             "sp": min(0.03 + 0.002 * self.wave, 0.07)})

    def update(self):
        self.t += 1
        g = self.grid
        blds = list(g.values())

        # esteiras
        if self.t % 4 == 0:
            moved = set()
            for b in blds:
                if b["t"] == "conv" and b["item"] and id(b) not in moved:
                    dx, dy = DIRS[b["d"]]
                    n = g.get((b["x"] + dx, b["y"] + dy))
                    if n and self.give(n):
                        b["item"] = False
                        if n["t"] == "conv":
                            moved.add(id(n))

        # brocas: 1 item a cada 1,5s, empurrado pra um vizinho que aceite
        for b in blds:
            if b["t"] != "drill":
                continue
            b["cd"] += 1
            if b["cd"] < 30:
                continue
            for dx, dy in DIRS:
                n = g.get((b["x"] + dx, b["y"] + dy))
                if not n:
                    continue
                if n["t"] == "conv":                    # não joga em esteira que aponta pra broca
                    ndx, ndy = DIRS[n["d"]]
                    if (n["x"] + ndx, n["y"] + ndy) == (b["x"], b["y"]):
                        continue
                if self.give(n):
                    b["cd"] = 0
                    break

        # torres
        for b in blds:
            if b["t"] != "turret":
                continue
            b["cd"] = max(0, b["cd"] - 1)
            if b["ammo"] > 0 and b["cd"] == 0 and self.enemies:
                tx, ty = b["x"] + .5, b["y"] + .5
                e = min(self.enemies, key=lambda e: math.hypot(e["x"] - tx, e["y"] - ty))
                if math.hypot(e["x"] - tx, e["y"] - ty) <= RANGE:
                    e["hp"] -= DMG
                    b["ammo"] -= 1
                    b["cd"] = 8
                    self.shots.append([tx, ty, e["x"], e["y"], 3])
        self.shots = [[*s[:4], s[4] - 1] for s in self.shots if s[4] > 1]

        # inimigos
        cx, cy = self.core["x"] + 1, self.core["y"] + 1
        for e in self.enemies[:]:
            if e["hp"] <= 0:
                self.enemies.remove(e)
                self.res += 1
                continue
            d = math.hypot(cx - e["x"], cy - e["y"])
            if d < 1.3:
                self.core["hp"] -= 5
                self.enemies.remove(e)
                continue
            e["x"] += (cx - e["x"]) / d * e["sp"]
            e["y"] += (cy - e["y"]) / d * e["sp"]

        # ondas
        self.countdown -= 1
        if self.countdown <= 0:
            self.wave += 1
            self.to_spawn += 3 + 2 * self.wave
            self.countdown = 30 * FPS
        if self.to_spawn > 0:
            self.spawn_cd -= 1
            if self.spawn_cd <= 0:
                self.spawn()
                self.to_spawn -= 1
                self.spawn_cd = 10

        if self.core["hp"] <= 0:
            self.over = True

    # desenho
    def draw(self):
        c = self.cv
        c.delete("d")
        for (x, y), b in self.grid.items():
            t, px, py = b["t"], x * S, y * S + HUD
            if t == "core":
                if (x, y) != (b["x"], b["y"]):
                    continue
                c.create_rectangle(px + 2, py + 2, px + 2 * S - 2, py + 2 * S - 2,
                                   fill="#2f8fe0", outline="#9fd0ff", width=2, tags="d")
                c.create_text(px + S, py + S - 4, text="NÚCLEO", fill="white", tags="d")
                w = (2 * S - 12) * max(0, b["hp"]) / 100
                c.create_rectangle(px + 6, py + 2 * S - 14, px + 6 + w, py + 2 * S - 8,
                                   fill="#6be07a", outline="", tags="d")
            elif t == "drill":
                c.create_rectangle(px + 5, py + 5, px + S - 5, py + S - 5,
                                   fill="#e0a82e", outline="#fff3c4", tags="d")
                c.create_oval(px + 12, py + 12, px + S - 12, py + S - 12,
                              fill="#3b2c0a", outline="", tags="d")
            elif t == "conv":
                c.create_rectangle(px + 2, py + 2, px + S - 2, py + S - 2,
                                   fill="#2a313b", outline="", tags="d")
                c.create_text(px + S / 2, py + S / 2, text=ARROW[b["d"]],
                              fill="#8b97a6", font=("TkDefaultFont", 14), tags="d")
                if b["item"]:
                    c.create_oval(px + 11, py + 11, px + S - 11, py + S - 11,
                                  fill="#ffd34d", outline="", tags="d")
            elif t == "turret":
                c.create_oval(px + 3, py + 3, px + S - 3, py + S - 3,
                              fill="#3bb273", outline="#c9ffe3", width=2, tags="d")
                c.create_rectangle(px + 4, py + S - 7, px + 4 + (S - 8) * b["ammo"] / AMMO_MAX,
                                   py + S - 3, fill="#ffd34d", outline="", tags="d")

        for x1, y1, x2, y2, _ in self.shots:
            c.create_line(x1 * S, y1 * S + HUD, x2 * S, y2 * S + HUD,
                          fill="#fff08a", width=2, tags="d")
        for e in self.enemies:
            px, py = e["x"] * S, e["y"] * S + HUD
            c.create_oval(px - 8, py - 8, px + 8, py + 8, fill="#e5484d", outline="#ffb3b5", tags="d")
            c.create_rectangle(px - 8, py - 13, px - 8 + 16 * max(0, e["hp"]) / e["max"], py - 10,
                               fill="#6be07a", outline="", tags="d")

        # HUD
        c.create_rectangle(0, 0, W * S, HUD, fill="#0b0e13", outline="", tags="d")
        info = (f"Minério: {self.res}     Núcleo: {max(0, int(self.core['hp']))}/100     "
                f"Onda: {self.wave}     Próxima em: {self.countdown // FPS + 1}s")
        c.create_text(10, 14, anchor="w", text=info, fill="#e6edf3",
                      font=("TkDefaultFont", 11, "bold"), tags="d")
        c.create_text(W * S - 10, 14, anchor="e", fill="#7d8896", tags="d",
                      text="R girar  |  botão direito apaga  |  Espaço chama a onda")
        menu = "     ".join(
            ("▶ " if self.sel == k else "   ") + f"[{i}] {NOME[k]} ({COST[k]})"
            + (f" {ARROW[self.rot]}" if k == "conv" else "")
            for i, k in enumerate(("drill", "conv", "turret"), 1))
        c.create_text(10, 34, anchor="w", text=menu, fill="#ffd34d", tags="d")

        if self.over:
            c.create_rectangle(W * S / 2 - 200, H * S / 2 + HUD - 50,
                               W * S / 2 + 200, H * S / 2 + HUD + 50,
                               fill="#1a0f12", outline="#e5484d", width=2, tags="d")
            c.create_text(W * S / 2, H * S / 2 + HUD - 14, fill="#ff8a8e", tags="d",
                          text="NÚCLEO DESTRUÍDO", font=("TkDefaultFont", 18, "bold"))
            c.create_text(W * S / 2, H * S / 2 + HUD + 20, fill="#e6edf3", tags="d",
                          text=f"Você chegou até a onda {self.wave}  -  Enter pra recomeçar")

    def loop(self):
        if not self.over:
            self.update()
        self.draw()
        self.root.after(1000 // FPS, self.loop)


if __name__ == "__main__":
    root = tk.Tk()
    Game(root)
    root.mainloop()
