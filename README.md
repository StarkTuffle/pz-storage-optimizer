# pz-storage-optimizer
Optimizer for Project Zomboid storage using Google's optimization tools.

## Getting Started

Install the ortools dependancy
`python3 -m pip install ortools`

Run the script
`python3 ./PZStorageOptimizer.py`

### Settings and Options

Grid Size: Define the size of your grid

Edit Modes:
- Toggle usable tile: Marks a tile as usable or unusable
  - Usable (White): Can be used in the optimizers calculations; empty walkable space
  - Unusable (Dark Gray): Ignored by the optimizer; spaces that cannot be passed through by the player
- Forced empty tile (Cyan): Any space that is player-walkable but should be ignored by the optimizer
- Set entrance (Green): A manditory forced empty tile, normally an entrance to the storage area
- Toggle wall edge: Mark spaces between tiles as having walls (cannot walk or interact through)

Optimizer Settings:
- Time Limit: Max time the optimizer will run before return it's best guess, will end earlier if it finds an optimized solution before time limit is reached
- Max Workers (Advanced): Worker threads used by the optimizer
