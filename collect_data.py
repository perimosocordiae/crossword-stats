#!/usr/bin/env python3
import appdirs
import copy
import datetime
import functools
import json
import matplotlib.cm
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pathlib
import random
import requests
import time
from typing import Sequence, Iterable, Tuple


NYT_APPSPOT_URL: str = 'https://nyt-games-prd.appspot.com/svc/crosswords/'
CACHE_DIR = pathlib.Path(appdirs.user_cache_dir(appname='crossword-stats'))


@functools.lru_cache(maxsize=None)
def get_user_info():
    path = os.path.join(os.path.dirname(__file__), 'user_info.json')
    return json.load(open(path))


def user_id() -> str:
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


def get_cached(path: pathlib.Path, expiration: datetime.timedelta = None):
    if not path.exists():
        return None
    if expiration is not None:
        mtime = path.stat().st_mtime
        stale = datetime.timedelta(seconds=(time.time() - mtime))
        if stale > expiration:
            return None
    return json.load(path.open())


def get_stats():
    uid = user_id()
    stats_cache = CACHE_DIR.joinpath(uid, 'stats.json')
    results = get_cached(stats_cache, datetime.timedelta(hours=12))
    if not results:
        url = f'{NYT_APPSPOT_URL}/v3/{uid}/stats-and-streaks.json'
        params = dict(date_start='2014-01-01', start_on_monday='true')
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        results = resp.json()['results']
        stats_cache.parent.mkdir(parents=True, exist_ok=True)
        json.dump(results, stats_cache.open(mode='w'))
    return results


def get_puzzle_data(puzzle_id: int):
    puzzle_cache = CACHE_DIR.joinpath(user_id(), f'{puzzle_id}.json')
    result = get_cached(puzzle_cache)
    if not result:
        url = f'{NYT_APPSPOT_URL}/v6/game/{puzzle_id}.json'
        resp = requests.get(url, headers={'nyt-s': user_cookie()})
        resp.raise_for_status()
        result = resp.json()
        puzzle_cache.parent.mkdir(parents=True, exist_ok=True)
        puzzle_cache.write_text(resp.text)
    return result


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


def parse_streak_ranges(dates: Sequence[Sequence[str]]
                        ) -> Iterable[Tuple[datetime.date, datetime.date]]:
    for row in dates:
        if len(row) == 1:
            start = datetime.date.fromisoformat(row[0])
            stop = start
        else:
            start, stop = map(datetime.date.fromisoformat, row)
        yield start, stop


def plot_streaks(dates: Sequence[Tuple[datetime.date, datetime.date]]) -> None:
    fig, ax = plt.subplots()
    one_day = datetime.timedelta(days=1)
    for start, stop in dates:
        xs, ys = [], []
        while start <= stop:
            x = start.timetuple().tm_yday
            if xs and x < xs[-1]:
                xs.append(np.nan)
                ys.append(np.nan)
            xs.append(x)
            ys.append(start.year + x/366)
            start += one_day
        ax.plot(xs, ys, lw=3)
    fig.tight_layout()


def main():
    stats = get_stats()
    print('Your current streak:', stats['streaks']['current_streak'], 'days.')
    print('Your longest streak:', stats['streaks']['longest_streak'], 'days.')
    print('Your solve rate:', stats['stats']['solve_rate'])
    streaks = list(parse_streak_ranges(stats['streaks']['dates']))
    plot_streaks(streaks)

    today = datetime.date.today()
    lookback = datetime.timedelta(weeks=4)
    puzzles = list_puzzles(today - lookback, today)
    print('Found', len(puzzles), 'puzzles from the last 4 weeks.')
    solved_puzzles = [p for p in puzzles if p['solved']]
    print('Of these, you solved', len(solved_puzzles))

    if False:
        p = random.choice(solved_puzzles)
        print('Selected puzzle', p['puzzle_id'], 'from', p['print_date'])

        puzzle = get_puzzle_data(p['puzzle_id'])
        print(
            'Your solution time:',
            puzzle['calcs']['secondsSpentSolving'],
            'seconds.',
        )
        plot_puzzle_solve(puzzle)
    else:
        foo = []
        for p in solved_puzzles:
            d = datetime.date.fromisoformat(p['print_date'])
            bar = get_puzzle_data(p['puzzle_id'])
            for key in ['board', 'userID', 'lastCommitID']:
                del bar[key]
            for key in ['solved', 'percentFilled', 'eligible']:
                bar['calcs'].pop(key, None)
            bar['date'] = d
            bar['dayofweek'] = d.strftime('%a')
            foo.append(pd.json_normalize(bar, sep='_'))
        df = pd.concat(foo, ignore_index=True)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        solve_times = [df[df.dayofweek == d].calcs_secondsSpentSolving
                       for d in days]
        fig, ax = plt.subplots()
        ax.boxplot(solve_times, labels=days, showmeans=True)

    # TODO: clean up, show progression of solve time per weekday over time

    plt.show()

    import IPython
    IPython.embed()


if __name__ == "__main__":
    main()
