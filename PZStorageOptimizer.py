import tkinter as tk
from tkinter import ttk, messagebox
from ortools.sat.python import cp_model

CELL_SIZE = 36

MOVE_DELTAS_4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]

def edge_key(a, b):
    return frozenset((a, b))

def is_adjacent_4(a, b):
    ax, ay = a
    bx, by = b
    return abs(ax - bx) + abs(ay - by) == 1

def blocked_by_wall(a, b, wall_edges):
    return edge_key(a, b) in wall_edges

# Check neighboring cells for walls
def neighbors_4_no_walls(c, cells, wall_edges):
    x, y = c
    result = []

    for dx, dy in MOVE_DELTAS_4:
        n = (x + dx, y + dy)
        if n in cells and not blocked_by_wall(c, n, wall_edges):
            result.append(n)

    return result

def access_neighbors(c, cells, wall_edges):
    x, y = c
    result = []

    # Check nsew tiles for accessability
    for dx, dy in MOVE_DELTAS_4:
        n = (x + dx, y + dy)
        if n in cells and not blocked_by_wall(c, n, wall_edges):
            result.append(n)

    # Check diagonal tiles for accessibility
    for dx in (-1, 1):
        for dy in (-1, 1):
            t = (x + dx, y + dy)
            if t not in cells:
                continue
        
            mid1 = (x + dx, y)
            mid2 = (x, y + dy)

            # Confirm at least one L path to diagonal is not blocked
            path1_ok = (mid1 in cells and not blocked_by_wall(c, mid1, wall_edges) and not blocked_by_wall(mid1, t, wall_edges))
            path2_ok = (mid2 in cells and not blocked_by_wall(c, mid2, wall_edges) and not blocked_by_wall(mid2, t, wall_edges))

            if path1_ok or path2_ok:
                result.append(t)
            
    return result

# Google ORTools CP-SAT Tomfoolery (https://developers.google.com/optimization/)
def optimize_storage(cells, entrance, forced_empty, wall_edges, time_limit_seconds=30, max_workers=8):
    # Init sets
    cells = set(cells)
    forced_empty = set(forced_empty)
    wall_edges = set(wall_edges)

    if entrance is None or entrance not in cells:
        raise ValueError("Entrance must be inside the usbalbe room area.")

    forced_empty.add(entrance)

    # Init CP-SAT model
    n = len(cells)
    model = cp_model.CpModel()

    empty = {c: model.NewBoolVar(f"empty_{c[0]}_{c[1]}") for c in cells}

    # Enforce forced-empty and entrance cells
    for c in forced_empty:
        if c in cells:
            model.Add(empty[c] == 1)

    # Add constraint that all tiles must have access to at least one empty tile
    for c in cells:
        adj = access_neighbors(c, cells, wall_edges)
        model.Add(empty[c] + sum(empty[a] for a in adj) >= 1)

    # Map all cells and their walkable neighbors (non-diagonal)
    move_neighbors = {c: neighbors_4_no_walls(c, cells, wall_edges) for c in cells}

    # Enforce all empty tiles must be reachable from entrance
    flow = {}

    for c in cells:
        for nc in move_neighbors[c]:
            flow[(c, nc)] = model.NewIntVar(0, n, f"flow_{c}_{nc}")

            model.Add(flow[(c, nc)] <= n * empty[c])
            model.Add(flow[(c, nc)] <= n * empty[nc])

    total_empty = sum(empty[c] for c in cells)

    for c in cells:
        incoming = sum(flow[(nc, c)] for nc in move_neighbors[c])
        outgoing = sum(flow[(c, nc)] for nc in move_neighbors[c])

        if c == entrance: # Set entrance as flow source
            model.Add(outgoing - incoming == total_empty - 1)
        else:
            model.Add(incoming - outgoing == empty[c])

    # Minimize empty cells within constraints
    model.Minimize(total_empty)

    # Init CP-SAT solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = int(max_workers)

    status = solver.Solve(model)

    # Return failure info on INFEASIBLE, MODEL_INVALID and UNKNOWN status
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, status, solver
    
    # Extract and return empty cells
    empty_tiles = {c for c in cells if solver.Value(empty[c]) == 1}

    # My head hurts (⊙ω⊙)
    return empty_tiles, status, solver

class StorageOptimizerGUI:
    # Set defaults and init UI
    def __init__(self, root):
        self.root = root
        self.root.title("PZ Storage Optimizer")

        self.width_var = tk.IntVar(value=10)
        self.height_var = tk.IntVar(value=8)
        self.mode_var = tk.StringVar(value="floor")
        self.time_limit_var = tk.StringVar(value="30")
        self.max_workers_var = tk.StringVar(value="8")
        self.status_var = tk.StringVar(value="Ready.")

        self.width = self.width_var.get()
        self.height = self.height_var.get()

        self.cells = set((x, y) for y in range(self.height) for x in range(self.width))
        self.forced_empty = set()
        self.wall_edges = set()
        self.entrance = (0, 0)

        self.solution_empty = None

        self.build_ui()
        self.redraw()

    # TKinter UI Code
    def build_ui(self):
        # Parent Frame
        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Controls Frame (Left Side)
        controls = ttk.Frame(main)
        controls.grid(row=0, column=0, sticky="nw", padx=(0,10))

        # Canvas Frame (Right Side)
        canvas_frame = ttk.Frame(main)
        canvas_frame.grid(row=0, column=1, sticky="nsew")

        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Grid Size Settings
        ttk.Label(controls, text="Grid Size", font=("Ariel", 12)).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(controls, text="Width").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(controls, from_=1, to=50, textvariable=self.width_var, width=6).grid(row=1, column=1, sticky="w")
        ttk.Label(controls, text="Height").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(controls, from_=1, to=50, textvariable=self.height_var, width=6).grid(row=2, column=1, sticky="w")
        ttk.Button(controls, text="New blank grid", command=self.new_grid).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        # Edit Mode Settings
        ttk.Label(controls, text="Edit Mode", font=("Ariel", 12)).grid(row=4, column=0, columnspan=2, sticky="w")

        modes = [
            ("Toggle usable tile", "floor"),
            ("Forced empty tile", "forced"),
            ("Set entrance", "entrance"),
            ("Toggle wall edge", "wall"),
            # ("Toggle containers", "containers")
        ]

        r = 5
        for text, value in modes:
            ttk.Radiobutton(controls, text=text, value=value, variable=self.mode_var).grid(row=r, column=0, columnspan=2, sticky="w")
            r += 1

        ttk.Separator(controls).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Optimizer Settings
        ttk.Label(controls, text="Optimizer Settings", font=("Ariel", 12)).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        ttk.Label(controls, text="Time Limit").grid(row=r, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.time_limit_var, width=8).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(controls, text="Max Workers").grid(row=r, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.max_workers_var, width=8).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Button(controls, text="Optimize", command=self.solve).grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8,2))
        r += 1

        # Clear Buttons
        ttk.Button(controls, text="Clear solution", command=self.clear_solution).grid(row=r, column=0, columnspan=2, sticky="ew")
        r += 1

        ttk.Button(controls, text="Clear walls", command=self.clear_walls).grid(row=r, column=0, columnspan=2, sticky="ew")
        r += 1

        ttk.Button(controls, text="Clear forced-empty", command=self.clear_forced_empty).grid(row=r, column=0, columnspan=2, sticky="ew")
        r += 1

        ttk.Separator(controls).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Legend
        ttk.Label(controls, text="Legend", font=("Ariel", 12)).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        legend = (
            "White = Usable tile\n"
            "Gray = Unusable tile\n"
            "Blue = Forced empty\n"
            "Green = Entrance\n"
            "Orange = Storage result\n"
            "Black bars = walls\n\n"
            "Wall mode:\n"
            "Click a grid line between two tiles."
        )

        ttk.Label(controls, text=legend, justify="left").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        # Status / Info
        ttk.Label(controls, textvariable=self.status_var, wraplength=220, justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=(12,0))

        # Grid Canvas
        self.canvas = tk.Canvas(canvas_frame, width=self.width * CELL_SIZE, height=self.height * CELL_SIZE, background="white", highlightthickness=1, highlightbackground="#080808")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        # Bind LMB
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    # Build new grid
    def new_grid(self):
        try:
            w = int(self.width_var.get())
            h = int(self.height_var.get())
        except:
            messagebox.showerror(title="Invalid size", message="Width and height must be integers.")
            return

        if w < 1 or h < 1:
            messagebox.showerror(title="Invalid size", message="Width and height must be at least 1.")
            return

        self.width = w
        self.height = h

        self.cells = set((x, y) for y in range(h) for x in range(w))

        self.canvas.config(width=self.width * CELL_SIZE, height=self.height * CELL_SIZE)

        self.status_var.set("New grid created.")
        self.redraw()

    def clear_solution(self):
        self.solution_empty = None
        self.status_var.set("Solution cleared.")
        self.redraw()

    def clear_walls(self):
        self.wall_edges.clear()
        self.solution_empty = None
        self.status_var.set("Walls cleared.")
        self.redraw()

    def clear_forced_empty(self):
        self.forced_empty.clear()
        self.solution_empty = None
        self.status_var.set("Forced-empty tiles cleared.")
        self.redraw()

    # LMB Grid Functions
    def on_canvas_click(self, event):
        mode = self.mode_var.get()
        
        # Redirect to Wall Edit def
        if mode == "wall":
            self.toggle_wall_at_click(event.x, event.y)
        else:
            x = event.x // CELL_SIZE
            y = event.y // CELL_SIZE

            # Ignore clicks outside of grid
            if not (0 <= x < self.width and 0 <= y < self.height):
                return
            else:
                self.solution_empty = None

            c = (x, y)

            if mode == "floor": # Usable Tile Mode
                if c in self.cells:
                    if self.entrance == c:
                        return
                    
                    self.cells.remove(c)
                    self.forced_empty.discard(c)
                    self.wall_edges = {
                        e for e in self.wall_edges if c not in e
                    }
                else:
                    self.cells.add(c)
            elif mode == "forced": # Forced Empty Mode
                if c not in self.cells or self.entrance == c:
                    return

                if c in self.forced_empty:
                    self.forced_empty.remove(c)
                else:
                    self.forced_empty.add(c)
            elif mode == "entrance": # Toggle Entrance Mode
                if c in self.cells:
                    self.entrance = c

        self.redraw()

    # Wall Edit Mode
    def toggle_wall_at_click(self, px, py):
        # Convert to grid coords
        gx = px / CELL_SIZE
        gy = py / CELL_SIZE

        # Find nearest grid lines
        nearest_x = round(gx)
        nearest_y = round(gy)

        dist_x = abs(gx - nearest_x)
        dist_y = abs(gy - nearest_y)

        threshold = 0.22

        # Ignore if too far from grid line
        if dist_x > threshold and dist_y > threshold:
            self.status_var.set("Wall mode: click closer to a grid line.")
            return

        # Prefer nearest wall
        if dist_x <= dist_y:
            x_line = nearest_x
            y = int(gy)

            if not (1 <= x_line <= self.width - 1 and 0 <= y < self.height):
                self.status_var.set("Wall must be between two tiles.")
                return

            a = (x_line - 1, y)
            b = (x_line,y)

        else:
            y_line = nearest_y
            x = int(gx)

            if not (1 <= y_line <= self.height - 1 and 0 <= x < self.width):
                self.status_var.set("Wall must be between two tiles.")
                return
            
            a = (x, y_line -1)
            b = (x, y_line)

        # Ensure both tiles are in grid
        if a not in self.cells or b not in self.cells:
            self.status_var.set("Walls can only be placed between two usable tiles.")
            return
        else:
            self.solution_empty = None

        # Create key and toggle wall
        e = edge_key(a, b)

        if e in self.wall_edges:
            self.wall_edges.remove(e)
            self.status_var.set("Wall removed")
        else:
            self.wall_edges.add(e)
            self.status_var.set("Wall added")

    # Optimize Button Func
    def solve(self):
        if not self.cells:
            messagebox.showerror(title="No usable tiles", message="There are no usable room tiles.")
            return

        if self.entrance is None or self.entrance not in self.cells:
            messagebox.showerror(title="No entrance", message="Set an entrance tile inside the room.")
            return

        try:
            time_limit = float(self.time_limit_var.get())
        except:
            messagebox.showerror(title="Invalid time limit", message="Time limit must be a number.")

        self.status_var.set("Solving...")
        self.root.update_idletasks()

        # Attempt to optimize
        try:
            empty_tiles, status, solver = optimize_storage(cells=self.cells, entrance=self.entrance, forced_empty=self.forced_empty, wall_edges=self.wall_edges, time_limit_seconds=time_limit)
        except:
            messagebox.showerror(title="Solver error.", message=str(Exception))
            self.status_var.set("Solver error.")
            return

        # Ignore if no solution
        if empty_tiles is None:
            self.solution_empty = None
            self.redraw()
            self.status_var.set("No valid solution found.")
            return

        self.solution_empty = empty_tiles
        storage_tiles = self.cells - empty_tiles
        density = len(storage_tiles) / len(self.cells) * 100
        total_capacity_def = len(storage_tiles) * 80 * 3
        total_capacity_dis = len(storage_tiles) * 56 * 3
        total_capacity_org = len(storage_tiles) * 104 * 3

        if status == cp_model.OPTIMAL:
            status_text = "Optimal solution found."
        else:
            status_text = "Feasable solution found; optimality not proven within time limit."

        self.status_var.set(
            f"{status_text}\n"
            f"Room tiles: {len(self.cells)}\n"
            f"Storage tiles: {len(storage_tiles)}\n"
            f"Empty tiles: {len(empty_tiles)}\n"
            f"Density: {density:.2f}%\n\n"
            f"Maximum capacity:\n{total_capacity_dis:g}/{total_capacity_def:g}/{total_capacity_org:g}*\n\n"
            f"*Disrganized/No Trait/Organized\nCalculated from a stack of 3 metal crates per tile"
        )

        self.redraw()

    # Redraw Grid (Run whenever grid changes)
    def redraw(self):
        # Clear canvas
        self.canvas.delete("all")

        # Init sets
        storage_tiles = set()
        empty_tiles = set()
        self.fake_walls = set()

        if self.solution_empty is not None:
            empty_tiles = self.solution_empty
            storage_tiles = self.cells - empty_tiles

        # Cylce through all cells in grid
        for y in range(self.height):
            for x in range(self.width):
                c = (x, y)

                x1 = x * CELL_SIZE
                y1 = y * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE

                label = ""

                if c not in self.cells: # Unusable Tile
                    fill = "#333333"
                elif c == self.entrance: # Entrance Tile
                    fill = "#49c764"
                    label = "@"
                elif c in self.forced_empty: # Forced Empty Tile
                    fill = "#89c9ff"
                    label = "-"
                elif c in storage_tiles: # Computed Storage Tile
                    fill = "#f0a13a"
                    label = "C"
                else: # Usable Tile
                    fill = "#ffffff"

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#bbbbbb")

                if label:
                    self.canvas.create_text(x1 + CELL_SIZE / 2, y1 + CELL_SIZE / 2, text=label, font=("Ariel", 14, "bold"))

                # Compute unusable tile walls that need rendered
                if c not in self.cells:
                    for dx, dy in MOVE_DELTAS_4:
                        n = (x + dx, y + dy)
                        if n in self.cells:
                            e = edge_key(c, n)
                            self.fake_walls.add(e)

        # Cycle though all placed and computed walls
        for e in self.wall_edges.union(self.fake_walls):
            a, b = tuple(e)
            ax, ay = a
            bx, by = b

            if not is_adjacent_4(a, b):
                continue

            if ax == bx:
                x1 = ax * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y = max(ay, by) * CELL_SIZE

                self.canvas.create_line(x1, y, x2, y, fill="#000000", width=5)
            else:
                x = max(ax, bx) * CELL_SIZE
                y1 = ay * CELL_SIZE
                y2 = y1 + CELL_SIZE

                self.canvas.create_line(x, y1, x, y2, fill="#000000", width=5)

        # Outer grid border
        self.canvas.create_rectangle(0, 0, self.width * CELL_SIZE, self.height * CELL_SIZE, outline="#444444", width=2)

# Main
def main():
    root = tk.Tk()
    app = StorageOptimizerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()