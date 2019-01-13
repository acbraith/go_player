from learn import autoplay
from players import Player

import numpy as np
np.random.seed(1)

import cProfile

pr = cProfile.Profile()
pr.enable()

for _ in range(100):
    autoplay(pause=0)

pr.disable()
pr.print_stats(sort='cumtime')