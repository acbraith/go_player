from go import Go

from typing import Tuple, List

import re

def sgf_to_moves(sgf: str) -> List[Tuple[int,int]]:
    moves = []
    for move in sgf.split(';'):
        if move[0] in ['B','W']:
            if '[]' in move:
                moves += [Go.PASS] # Pass
            else:
                x,y = move[2], move[3]
                i,j = ord(x) - ord('a'), ord(y) - ord('a')
                moves += [(i,j)]
    return moves

def winner(sgf: str) -> int:
    winner = re.search(r'RE\[(\w)', sgf)[1]
    if winner == 'B': return Go.BLACK
    if winner == 'W': return Go.WHITE
    return None

def play_sgf(sgf: str) -> Tuple[List[Go], int]:
    moves = sgf_to_moves(sgf)
    go = Go()
    history = [go]
    for move in moves:
        go = go.place(move)
        history += [go]
    return (history, winner(sgf))
    
if __name__ == '__main__':
    sgf = open('sgfs/594193/15594332.sgf', 'r').read()
    history, winner = play_sgf(sgf)
    for board in history:
        print(board)
    print(winner)