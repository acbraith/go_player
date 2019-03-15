
from collections import defaultdict

import numpy as np
import pygame
from pygame import gfxdraw

from go import Go
from process_sgf import play_sgf

class SGFViewer:
    def __init__(self, sgf, screen, overlay=None):
        self.sgf    = sgf
        self.screen = screen
        self.result = play_sgf(sgf)
        self.states = [self.result['board']]
        self.overlay = overlay

        while self.states[0]._prev is not None:
            self.states = [self.states[0]._prev] + self.states

        self.curr_idx = 0

    def next(self):
        self.curr_idx = min(self.curr_idx + 1, len(self.states) - 1)
    def prev(self):
        self.curr_idx = max(self.curr_idx - 1, 0)

    def mouse_click(self, pos):
        state = self.states[self.curr_idx]
        size = state._size
        r = np.mean(SIZE) / (size + 1)

        x = int(round(pos[0] / r - 1))
        y = int(round(pos[1] / r - 1))
        try:
            state = state.place((x,y))
            self.curr_idx += 1
            self.states = self.states[:self.curr_idx]
            self.states += [state]
            self.update()
        except:
            pass

    def update(self):
        state = self.states[self.curr_idx]
        size = state._size
        r = np.mean(SIZE) / (size + 1)
        def clear():
            self.screen.fill(BOARD)
            for i in range(size):
                xy = r * (i+1)
                pygame.draw.line(self.screen, BLACK, [r, xy], [SIZE[0]-r, xy], 1)
                pygame.draw.line(self.screen, BLACK, [xy, r], [xy, SIZE[1]-r], 1)
        def draw_stone(x,y,c,surface):
            x = x*r + r
            y = y*r + r
            pygame.gfxdraw.filled_circle(surface, int(x), int(y), int(r/2), c)
            pygame.gfxdraw.aacircle(surface, int(x), int(y), int(r/2), BLACK)
        def mark_stone(x, y, c, surface):
            x = x*r + r
            y = y*r + r
            pygame.gfxdraw.aacircle(surface, int(x), int(y), int(r/4), c)
        def draw_stones():
            for i in range(size):
                for j in range(size):
                    if state._board[i,j] != 0:
                        draw_stone(i,j,WHITE if state._board[i,j] == Go.WHITE else BLACK, self.screen)
            if state._last_move and state._last_move != Go.PASS:
                x,y = state._last_move
                mark_stone(x, y, WHITE if state._turn == Go.WHITE else BLACK, self.screen)
        def draw_overlay():
            if not self.overlay: return
            overlay = self.overlay(state)
            if np.max(overlay) == np.min(overlay): return
            overlay /= np.max(overlay)
            surface = pygame.Surface(SIZE)
            # surface = surface.convert_alpha()
            surface.set_alpha(0.2 * 255)
            def draw_overlay(x,y,val):
                c = (int(255*val), 0, 0)
                draw_stone(x, y, c, surface)
            for i in range(size):
                for j in range(size):
                    draw_overlay(i,j,overlay[i,j])
            x,y = np.unravel_index(np.argmax(overlay, axis=None), overlay.shape)
            mark_stone(x, y, BLACK, surface)
            self.screen.blit(surface, (0,0))
        clear()
        draw_stones()
        draw_overlay()
        pygame.display.flip()


if __name__ == '__main__':
    from train import single_go_to_x
    from model import Gen_Model
    from players import MCTS_Player
    model = Gen_Model().load('Go', '0.1')
    player = MCTS_Player(model, time_limit=1)
    import functools as ft
    # @ft.lru_cache(maxsize=None)
    def overlay_func(state, mode):
        try:
            if mode == 'PRIOR':
                if state._turn == Go.BLACK: raise Exception('AI Play WHITE')
                x = single_go_to_x(state)
                val, pi = model.predict(x)
                return np.reshape(pi[0,:-1], state._board.shape)
            elif mode == 'MCTS':
                action_visits = player.mcts.action_visits(MCTS_Player.GoState(state))
                pi = np.zeros(state._size**2)
                for action in action_visits:
                    print(action)
                    try:
                        pi[action] = action_visits[action]
                    except IndexError:
                        pass
                return pi.reshape(state._board.shape)
            else:
                raise Exception('Unknown Mode')
        except:
            import traceback
            print(traceback.format_exc())
            return np.zeros_like(state._board)
    BLACK = (  0,   0,   0)
    WHITE = (255, 255, 255)
    BOARD = (220, 179,  92)
    # Open a new window
    SIZE = (400, 400)
    screen = pygame.display.set_mode(SIZE)
    clock = pygame.time.Clock()
    pygame.display.set_caption("SGF Viewer")
    sgf = (
        '''
        (;FF[4]
        CA[UTF-8]
        GM[1]
        DT[2019-01-30]
        PC[OGS: https://online-go.com/game/16358212]
        PB[abraith93]
        PW[OntanisKalėda]
        BR[15k]
        WR[11k]
        TM[259200]OT[86400 fischer]
        CP[online-go.com]
        RE[W+R]
        SZ[9]
        KM[3.5]
        RU[japanese]
        AB[ee]
        ;W[cf]
        ;B[fg]
        ;W[cc]
        ;B[fc]
        ;W[ge]
        ;B[hd]
        ;W[gg]
        ;B[hf]
        ;W[gf]
        ;B[gh]
        ;W[hh]
        ;B[fh]
        ;W[he]
        ;B[cg]
        ;W[bg]
        ;B[dg]
        ;W[bh]
        ;B[dc]
        ;W[cd]
        ;B[dd]
        ;W[hi]
        ;B[cb]
        ;W[bb]
        ;B[db]
        ;W[gd]
        ;B[gc]
        ;W[hc]
        ;B[hb]
        ;W[ic]
        ;B[ib]
        ;W[id]
        ;B[ce]
        ;W[be]
        ;B[df]
        ;W[de]
        ;B[ch]
        ;W[ba]
        ;B[bi]
        ;W[ah]
        ;B[ca]
        ;W[ai]
        ;B[ci]
        ;W[ed]
        ;B[fd]
        ;W[ce]
        )
        '''
    )
    sgf = 'SZ[9]'
    viewer = SGFViewer(sgf, screen, lambda state: overlay_func(state, 'PRIOR'))
    viewer.update()
    running = True
    key_down = defaultdict(int)
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                key_down[event.key] += 1
            elif event.type == pygame.KEYUP:
                key_down[event.key] = 0
            elif event.type == pygame.MOUSEBUTTONDOWN:
                viewer.mouse_click(pygame.mouse.get_pos())

        if key_down[pygame.K_LEFT] == 1 or key_down[pygame.K_LEFT] > 10:
            viewer.prev()
            viewer.update()
        if key_down[pygame.K_RIGHT] == 1 or key_down[pygame.K_RIGHT] > 10:
            viewer.next()
            viewer.update()

        for key in key_down:
            if key_down[key]: key_down[key] += 1
        clock.tick(20)