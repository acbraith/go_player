# Go Experiments

## Overview

* `go.py` contains a `Go` class, which can play games of Go.
* `ogs_webscraper.py` downloads `.sgf` files from OGS.
* `sgf_converter.py` converts these files into game histories and winners.
* `players.py` contains a series of players, which can take a `Go` class as 
input and output a `Tuple[int,int]` move
* `train.py` trains and saves a CNN (from `model.py`) on SGF files

## TODO
- [x] Go Game
    - [x] Play SGF files
- [ ] Create an Agent
    - [x] Random Agent
    - [x] Webscrape SGF files
        - [x] Use proxy and multithreading
    - [ ] Build AlphaZero style CNN
        - https://github.com/AppliedDataSciencePartners/DeepReinforcementLearning
    - [x] Train policy and value heads
        - [x] Convert SGF files into network inputs / targets
    - [x] Greedy policy and value head agents
    - [x] MCTS
        - https://github.com/pbsinclair42/MCTS
    - [x] MCTS agent
    - [ ] Self-play to generate training data
    - [ ] Full AlphaZero : Self-Play / Train / Evaluate
        - https://medium.com/applied-data-science/alphago-zero-explained-in-one-diagram-365f5abf67e0
        - https://applied-data.science/static/main/res/alpha_go_zero_cheat_sheet.png
- [x] Play Online
    - https://online-go.com/api/
    - https://ogs.docs.apiary.io/
    - https://forums.online-go.com/t/ogs-api-notes/17136
    - [x] Create account for AI
        - Pasbot
        - https://online-go.com/user/view/619703
    - [x] Log on to API
    - [x] Place a move in a game
    - [x] Load a game into Go object
    - [x] Plug in simple random agent
    - [x] Handle multiple games
        - [x] Play multiple games at once
        - [x] Pick up existing games on startup
        - [x] Pick up new games whilst running (bug?)
    - [x] Search for game when no games going on
    - [ ] Multiprocessing for multiple games
- [ ] Optimisations
    - [x] Benchmark and optimise Go game
    - [ ] Train on AWS
    - [ ] Download more data and train from only dan level games
    - [ ] Optimise train data selection
        - https://stackoverflow.com/questions/15993447/python-data-structure-for-efficient-add-remove-and-random-choice
