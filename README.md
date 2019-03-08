# Go Experiments

## Overview

- `go.py` contains a `Go` class, which can play games of Go
- `players.py`, `mcts.py` and `model.py` are the files for creating Go playing
agents
- `download_*.py` downloads SGF files
- `train.py` trains and saves a CNN (from `model.py`) on SGF files
- `play.py` logs on to an OGS account using details in `config.yml`, and plays 
games using the model saved by `train.py`

## TODO
- [x] Go Game
    - [x] Play SGF files
- [ ] Create an Agent
    - [x] Random Agent
    - [x] Webscrape SGF files
        - [x] Use proxy and multithreading
    - [x] Build AlphaZero style CNN
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
    - [x] Log on to API
    - [x] Place a move in a game
    - [x] Load a game into Go object
    - [x] Plug in simple random agent
    - [x] Handle multiple games
        - [x] Play multiple games at once
        - [x] Pick up existing games on startup
        - [x] Pick up new games whilst running (bug?)
    - [x] Search for game when no games going on
    - [x] Multiprocessing for multiple games
    - [x] Stone removal phase
    - [x] Resign based on win chance
    - [x] Chat
        - [x] Pre-programmed messages
        - [ ] More complex chat-bot model
- [ ] Optimisations
    - [x] Benchmark and optimise Go game
    - [ ] Train on AWS
    - [x] Download more data and train from only dan level games
    - [x] Optimise train data selection
        - https://stackoverflow.com/questions/15993447/python-data-structure-for-efficient-add-remove-and-random-choice
