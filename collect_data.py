#!/usr/bin/env python3
import copy
import datetime
import functools
import json
import matplotlib.cm
import matplotlib.pyplot as plt
import numpy as np
import os
import random
import requests

NYT_APPSPOT_URL = 'https://nyt-games-prd.appspot.com/svc/crosswords/'


@functools.lru_cache(maxsize=None)
def get_user_info():
    path = os.path.join(os.path.dirname(__file__), 'user_info.json')
    return json.load(open(path))


def user_id() -> int:
    return get_user_info()['user_id']


def user_cookie() -> str:
    return get_user_info()['cookie']


def list_puzzles(start: datetime.date, stop: datetime.date):
    uid = user_id()
    url = f'{NYT_APPSPOT_URL}/v3/{uid}/puzzles.json'
    params = dict(
        publish_type='daily',
        sort_order='asc',
        sort_by='print_date',
        date_start=str(start),
        date_end=str(stop),
    )
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()['results']


def get_stats():
    uid = user_id()
    url = f'{NYT_APPSPOT_URL}/v3/{uid}/stats-and-streaks.json'
    params = dict(date_start='2014-01-01', start_on_monday='true')
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()['results']


def get_puzzle_data(puzzle_id: int):
    url = f'{NYT_APPSPOT_URL}/v6/game/{puzzle_id}.json'
    resp = requests.get(url, headers={'nyt-s': user_cookie()})
    resp.raise_for_status()
    return resp.json()


def guess_dimensions(n: int):
    guess = int(np.sqrt(n))
    while n % guess != 0:
        guess -= 1
    return guess, n // guess


def plot_puzzle_solve(puzzle):
    board_cells = puzzle['board']['cells']
    num_rows, num_cols = guess_dimensions(len(board_cells))
    board = np.zeros((num_rows, num_cols))
    letters = []
    for i, cell in enumerate(board_cells):
        r, c = divmod(i, num_cols)
        if 'blank' in cell:
            board[r, c] = np.nan
        else:
            board[r, c] = cell['timestamp']
            letters.append((r, c, cell['guess']))
    fig, ax = plt.subplots()
    cmap = copy.copy(matplotlib.cm.get_cmap())
    cmap.set_bad(color='black')
    im = ax.imshow(board, cmap=cmap)
    for r, c, letter in letters:
        ax.text(c, r, letter, ha='center', va='center', color='k')
    ax.set_axis_off()
    fig.colorbar(im, ax=ax)
    fig.tight_layout()


def main():
    stats = get_stats()
    print('Your current streak:', stats['streaks']['current_streak'], 'days.')
    print('Your solve rate:', stats['stats']['solve_rate'])

    today = datetime.date.today()
    lookback = datetime.timedelta(weeks=4)
    puzzles = list_puzzles(today - lookback, today)
    print('Found', len(puzzles), 'puzzles from the last 4 weeks.')
    solved_puzzles = [p for p in puzzles if p['solved']]
    print('Of these, you solved', len(solved_puzzles))

    p = random.choice(solved_puzzles)
    print('Selected solved puzzle', p['puzzle_id'], 'from', p['print_date'])

    puzzle = get_puzzle_data(p['puzzle_id'])
    print(
        'Your solution time:',
        puzzle['calcs']['secondsSpentSolving'],
        'seconds.',
    )
    plot_puzzle_solve(puzzle)
    plt.show()

    import IPython

    IPython.embed()


if __name__ == "__main__":
    main()
