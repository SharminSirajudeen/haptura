"""The only tunables, each with its reason.

EVAL.md copies them before the kill test and freezes them.
"""

BLOCK_STEPS = 30  # steps per block: one SAM call per block, three seconds of video at FPS
FPS = 10
W = H = 128  # the smallest frame SAM is expected to track at (T2 checks it)
CELL_PX = 2  # one step moves one cell
ELEMENT_PX = 8
MAX_LAG = 4  # echoes repeat an action 1..MAX_LAG steps late
PERMS = 9999  # the permutation floor 1/(PERMS+1) = 1e-4 sits below ALPHA_ACT
PROBE_STEPS = 10  # S14's diagnostic probe, at least two of each action
P_NOOP = 0.3  # the no-op rate S12 uses unless Muse asks for another
ELEMENTS_MAX = 8  # SAM allows 16 objects per frame; eight keep the demo readable
BLOCK_BUDGET = 6  # probe blocks per episode before the rules decline
ALPHA_ACT = 0.01 / (ELEMENTS_MAX * BLOCK_BUDGET)  # Bonferroni over elements and looks
ALPHA_PROBE = 0.2  # above it, an object is treated as not responding
EFFECT_MIN = 0.5 * CELL_PX  # smaller measured effects are dead actions
STALE_TOL = 0.5 * CELL_PX  # a prediction further off than this is a miss
STALE_M = 3  # consecutive misses before S14 calls the belief stale
JUMP_TOL = 2.5 * CELL_PX  # a one-step jump larger than this is a tracker identity swap
MAX_MUSE_CALLS = 12  # per episode
MAX_FRAMES = (BLOCK_BUDGET + 4) * (BLOCK_STEPS + 1)  # per episode: the budget plus four act blocks
