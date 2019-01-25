from sgf_converter import play_sgf

import cProfile
import os

if __name__ == '__main__':
    pr = cProfile.Profile()
    pr.enable()

    for _ in range(10):
        for uid in os.listdir('sgfs'):
            for fname in os.listdir('sgfs/%s' % uid):
                play_sgf(open('sgfs/%s/%s' % (uid, fname), 'r').read())

    pr.disable()
    pr.print_stats(sort='time')
