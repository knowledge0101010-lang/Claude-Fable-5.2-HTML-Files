"""Evolved candidate: LeWM ablation protocol.

openevolve mutates PARAMS only. The evaluator trains two variants with the
torch python (SIGReg on at lam, off at 0) and scores how much the variance
collapse widens — a larger separation means the ablation isolates SIGReg better.
"""

# EVOLVE-BLOCK-START
PARAMS = {
    "lam": 0.09,        # SIGReg weight for the treated variant
    "steps": 30,        # training steps per variant (cost control)
    "tolerance": 0.02,  # minimum acceptable mean_std separation
}
# EVOLVE-BLOCK-END
