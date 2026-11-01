"""The only tunables, each with its reason.

EVAL.md copies them before the kill test and freezes them.
"""

BLOCK_STEPS = 30  # steps per block: one SAM call per block, three seconds of video at FPS
FPS = 10
W = H = 128  # the smallest frame SAM tracks at (docs/api.md)
CELL_PX = 2  # one step moves one cell
ELEMENT_PX = 8
MAX_LAG = 4  # echoes repeat an action 1..MAX_LAG steps late
PERMS = 9999  # the permutation floor 1/(PERMS+1) = 1e-4 sits below ALPHA_ACT
PROBE_STEPS = 15  # the diagnostic probe, 3 of each action: with 2 each, p cannot reach ALPHA_ACT
P_NOOP = 0.3  # the no-op rate `design_block` uses unless Muse asks for another
ELEMENTS_MAX = 8  # SAM allows 16 objects per frame; eight keep the demo readable
BLOCK_BUDGET = 6  # probe blocks per episode before the rules decline
ALPHA_ACT = 0.01 / (ELEMENTS_MAX * BLOCK_BUDGET)  # Bonferroni over elements and looks
ALPHA_PROBE = 0.2  # the rule policy declines early when every object sits above it
EARLY_LOOKS = 3  # the rule policy's early decline needs this many looks first
EFFECT_MIN = 0.5 * CELL_PX  # smaller measured effects are dead actions
STALE_TOL = 1.5 * CELL_PX  # the block's summed residual above this means a belief is wrong
JUMP_TOL = 2.5 * CELL_PX  # a one-step jump larger than this is a tracker identity swap
MAX_MUSE_CALLS = 12  # per episode
MAX_FRAMES = (BLOCK_BUDGET + 4) * (BLOCK_STEPS + 1)  # per episode: the budget plus four act blocks
SAM_PROMPT = (
    "colored object"  # the one noun phrase SAM 3.1 matched on every flat shape (docs/api.md)
)
MUSE_EFFORT = "low"  # one step above "minimal"; the kill test says whether it keeps accuracy
# a ceiling per reply, reasoning included: at 400, 6 of 11 Wonder replies were cut off (run 41);
# at 2000 none of 17 was, and the longest used 763 (run 44)
MUSE_MAX_OUTPUT_TOKENS = 2000
