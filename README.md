# Go Experiments

## Overview

* `go.py` contains a `Go` class, which can play games of Go.
* `ogs_api.py` downloads `.sgf` files from OGS.
* `sgf_converter.py` converts these files into game histories and winners.
* `players.py` contains a series of players, which can take a `Go` class as input
and output a `Tuple[int,int]` move.
* `supervised_learn.py` trains a CNN on a series of SGF files, producing a
`Player` using the trained CNN.

## TODO

* SL Value function
    * `Player`
* SL Policy network
    * `Player`
* SL Policy and Value in one network
    * `Player`
* MCTS using SL Policy + Value networks
* Download high level game `sgf` files from OGS
* Produce data from self-play and train same network on this
    * Maybe function to turn Go history into `.sgf`
* OGS Go Bot
    * Manually play on OGS from console
    * Plug `Player` in to this