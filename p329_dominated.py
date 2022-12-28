dev = False if __file__ == '/tmp/Answer.py' else True

import sys
import numpy as np
from scipy.signal import convolve2d
from scipy import ndimage
from time import perf_counter
# import matplotlib.pyplot as plt
# import seaborn as sns

verbose = False
print_input_logs = False

def debug(message) -> None:
    print(message, file=sys.stderr, flush=True)


def input_stream(filename):
    print_logs = [line.strip() for line in open(f"./input_logs/{filename}", 'r')]
    idx = -1

    def inner():
        nonlocal idx
        idx += 1
        if idx < len(print_logs):
            return print_logs[idx]
        else:
            raise EOFError("End of input stream")
    return inner


min_max = lambda x: (x - x.min()) / (x.max() - x.min() + 1e-10)


def get_filter(rows, cols, p):
    n = max(rows, cols) * 2 + 1
    a = np.concatenate([np.arange(n//2, 0, -1), [0.25], np.arange(1, n//2+1, 1)], axis=0)
    X, Y = np.meshgrid(a, a)
    filter = p ** (X+Y)
    filter[n//2 - 1: n//2 + 2, n//2] = 3
    filter[n//2, n//2 - 1: n//2 + 2] = 3
    return filter


class Board:

    def __init__(self, input_array, p=0.85):
        self._input_array = input_array
        self.kernel_3_3_ones = np.ones(
            (3, 3))
        self.kernel_manhattan = np.array(
            [[0,1,0],
             [1,1,1],
             [0,1,0]])
        self.kernel_local = np.array(
            [[0, 1, 0],
             [1, 1, 1],
             [0, 1, 0]])
        self.kernel_global = get_filter(
            input_array.shape[0],
            input_array.shape[1],
            p=p)
        self._cached_properties = {}
        self.island_number = None
        self.island_mask = np.ones((self._input_array.shape[0], self._input_array.shape[1]), dtype=bool)
        self.island = ndimage.label(
            input=((self._input_array[:, :, 0] > 0) * (self._input_array[:, :, 3] == 0)),
            structure=self.kernel_manhattan,
        )[0].astype(np.int8)
        self.island_presence_me = set(np.unique(self.owner_me * self.island))
        self.island_presence_op = set(np.unique(self.owner_op * self.island))
        self.island_presence_ne = set(np.unique(self.owner_ne * self.island))
        self.island_shared = set(self.island_presence_me).intersection(set(self.island_presence_op))
        self.island_captured_me = self.island_presence_me - self.island_shared
        self.island_captured_op = self.island_presence_op - self.island_shared
        self.island_complete = self.island_captured_op | self.island_captured_me.difference(self.island_presence_ne)
        self.island_active = set(np.unique(self.island)).difference(self.island_complete)        
        # self.dominated_owner_active_islands_list = [
        #     island for island in self.island_active 
        #     if np.sum((self.island == island) * self.owner_me) <=
        #     np.sum((self.island == island) * self.owner_op)        ]
        # self.dominating_owner_active_islands_list = [
        #     island for island in self.island_active 
        #     if np.sum((self.island == island) * self.owner_me) >
        #     np.sum((self.island == island) * self.owner_op)        ]
        # self.dominated_owner_active_islands = np.isin(self.island, self.dominated_owner_active_islands_list)
        # self.dominating_owner_active_islands = np.isin(self.island, self.dominating_owner_active_islands_list)        
        # self.dominated_units_active_islands_list = [
        #     island for island in self.island_active 
        #     if np.sum((self.island == island) * self.units_me) <=
        #     np.sum((self.island == island) * self.units_op)        ]
        # self.dominating_units_active_islands_list = [
        #     island for island in self.island_active 
        #     if np.sum((self.island == island) * self.units_me) >
        #     np.sum((self.island == island) * self.units_op)        ]
        # self.dominated_units_active_islands = np.isin(self.island, self.dominated_units_active_islands_list)
        # self.dominating_units_active_islands = np.isin(self.island, self.dominating_units_active_islands_list)


    def set_island_number(self, island_number):
        self.island_number = island_number
        self.island_mask = (self.island == self.island_number)

    def reset_island_number(self):
        self.island_number = None
        self.island_mask = np.ones((self._input_array.shape[0], self._input_array.shape[1]), dtype=bool)

    def cached(self, propery_name, func):
        if propery_name not in self._cached_properties:
            self._cached_properties[propery_name] = {}
        if self.island_number not in self._cached_properties[propery_name]:
            if verbose:
                debug(f'updating cache for island {self.island_number} propery {propery_name}')
            self._cached_properties[propery_name][self.island_number] = func
        return self._cached_properties[propery_name][self.island_number]

    @property
    def scrap_amount(self):
        func = self._input_array[:, :, 0] * self.island_mask
        return self.cached('scrap_amount', func)

    @property
    def owner(self):
        func = self._input_array[:, :, 1] * self.island_mask
        return self.cached('owner', func)

    @property
    def units(self):
        func = self._input_array[:, :, 2] * self.island_mask
        return self.cached('units', func)

    @property
    def recycler(self):
        func = self._input_array[:, :, 3] * self.island_mask
        return self.cached('recycler', func)

    @property
    def can_build(self):
        func = self._input_array[:, :, 4] * self.island_mask
        return self.cached('can_build', func)

    @property
    def can_spawn(self):
        func = self._input_array[:, :, 5] * self.island_mask
        return self.cached('can_spawn', func)

    @property
    def in_range_of_recycler(self):
        func = self._input_array[:, :, 6] * self.island_mask
        return self.cached('in_range_of_recycler', func)

    @property
    def is_grass(self):
        func = (self.scrap_amount == 0) * self.island_mask
        return self.cached('is_grass', func)

    @property
    def should_build(self):
        # func = self.can_build * self.dominating_units_active_islands
        func = self.can_build * np.isin(self.island, list(self.island_shared))
        # func = self.island_shared * self.can_build * self.island_mask
        return self.cached('should_build', func)

    @property
    def should_spawn(self):
        # func = self.can_spawn * self.dominated_units_active_islands
        func = self.can_spawn * np.isin(self.island, list(self.island_active))
        # func = self.island_shared * self.can_spawn * self.island_mask
        return self.cached('should_spawn', func)

    @property
    def tile_live(self):
        func = (self.scrap_amount > 0) * (self.recycler == 0) * self.island_mask
        return self.cached('tile_live', func)

    @property
    def tile_dead(self):
        func = (self.tile_live == 0) * self.island_mask
        return self.cached('tile_dead', func)

    @property
    def owner_me(self):
        func = (self.owner == 1) * self.island_mask
        return self.cached('owner_me', func)

    @property
    def owner_op(self):
        func = (self.owner == 0) * self.island_mask
        return self.cached('owner_op', func)

    @property
    def owner_ne(self):
        func = (self.owner == -1) * self.island_mask
        return self.cached('owner_ne', func)

    @property
    def units_op(self):
        func = self.units * (self.owner == 0) * self.island_mask
        return self.cached('units_op', func)

    @property
    def units_me(self):
        func = self.units * (self.owner == 1) * self.island_mask
        return self.cached('units_me', func)

    @property
    def recycler_me(self):
        func = self._input_array[:, :, 3] * (self.owner == 1) * self.island_mask
        return self.cached('recycler_me', func)

    @property
    def scrap_amount_local(self):
        func = convolve2d(self.scrap_amount * self.island_mask, self.kernel_local, mode='same')
        return self.cached('scrap_amount_local', func)

    @property
    def tile_live_global(self):
        func = convolve2d(self.tile_live * self.island_mask, self.kernel_global, mode='same')
        return self.cached('tile_live_global', func)

    @property
    def tile_dead_global(self):
        func = convolve2d(self.tile_dead * self.island_mask, self.kernel_global, mode='same')
        return self.cached('tile_dead_global', func)

    @property
    def owner_me_global(self):
        func = convolve2d(self.owner_me * self.island_mask, self.kernel_global, mode='same')
        return self.cached('owner_me_global', func)

    @property
    def owner_op_global(self):
        func = convolve2d(self.owner_op * self.island_mask, self.kernel_global, mode='same')
        return self.cached('owner_op_global', func)

    @property
    def owner_ne_global(self):
        func = convolve2d(self.owner_ne * self.island_mask, self.kernel_global, mode='same')
        return self.cached('owner_ne_global', func)

    @property
    def owner_op_3_3_sq(self):
        func = convolve2d(self.owner_op * self.island_mask, self.kernel_3_3_ones, mode='same')
        return self.cached('owner_op_3_3_sq', func)

    @property
    def units_op_global(self):
        func = convolve2d(self.units_op * self.island_mask, self.kernel_global, mode='same')
        return self.cached('units_op_global', func)

    @property
    def units_me_global(self):
        func = convolve2d(self.units_me * self.island_mask, self.kernel_global, mode='same')
        return self.cached('units_me_global', func)


def get_move_actions(board, weights):
    results = []
    actions = []
    perf = {}

    for island in board.island_active:
        if verbose:
            perf_start = perf_counter()
            debug(f'{"="*50}\nrunning get_move_actions() for island {island}\n{"="*50}')

        board.set_island_number(island)

        a = np.full_like(board.scrap_amount, 0, dtype=np.float64)
        for feature, weight in weights.items():
            a += weight * min_max(getattr(board, feature))

        for row, col in np.argwhere(board.units_me):

            current_unit = np.zeros_like(a)
            current_unit[row, col] = 1

            units_me_k3_manh_excl_current_unit = convolve2d(
                board.units * (board.owner == 1) * (current_unit == 0),
                board.kernel_local, mode='same'
            ).astype(int)
            a += -2 * min_max(units_me_k3_manh_excl_current_unit)

            legal_moves = (
                1
                * board.tile_live
                * convolve2d(current_unit, np.array([[0,1,0],[1,0,1],[0,1,0]]), mode='same')
            )

            scores = a * np.where(legal_moves, 1, np.nan)
            if np.all(np.isnan(scores)):
                continue
            max_value, max_indices = np.nanmax(scores), np.unravel_index(np.nanargmax(scores), scores.shape)

            actions.append(f"MOVE 1 {col} {row} {max_indices[1]} {max_indices[0]}")
            results.append({'row_col': (row, col), 'max_indices': max_indices, 'max_value': max_value})
        
        if verbose:
            perf[island] = perf_counter() - perf_start
    if verbose:
        for island, results in perf.items():
            debug(f'island {island} took {results} seconds')
        debug(f'total time: {sum(perf.values())} seconds')
    board.reset_island_number()
    return actions


def get_spawn(board, weights, k=1):
    new_spawns = np.full_like(board.scrap_amount, 0, dtype=np.float64)
    actions = []

    for i in range(k):
        # (board.units_me == 0) is to prevent spawning on top of own units
        legal_moves = (
            1
            * (board.can_spawn == 1)
            * (board.should_spawn == 1)
            * (new_spawns == 0)
            * (board.recycler == 0)
            * (board.units_me == 0)
        )
        if legal_moves.sum() == 0:
            break

        a = np.full_like(board.scrap_amount, 0, dtype=np.float64)

        for feature, weight in weights.items():
            a += weight * min_max(getattr(board, feature))

        if i > 0:
            a += -2 * min_max(convolve2d(new_spawns, board.kernel_local, mode='same').astype(int))

        scores = a * np.where(legal_moves, 1, np.nan)
        max_value, max_indices = np.nanmax(scores), np.unravel_index(np.nanargmax(scores), scores.shape)
        row, col = max_indices
        new_spawns[row, col] = 1
        actions.append(f"SPAWN 1 {col} {row}")
    
    debug(actions)
    return actions


def get_build(board):
    legal_moves = board.should_build
    a = (board.owner_op_3_3_sq) + ((board.scrap_amount_local * board.in_range_of_recycler == 0) / 100)
    scores = a * np.where(legal_moves, 1, np.nan)
    max_value, max_indices = np.nanmax(scores), np.unravel_index(np.nanargmax(scores), scores.shape)
    row, col = max_indices
    debug(f"BUILD {col} {row}")
    return [f"BUILD {col} {row}"]


class InputOutput:

    def __init__(self, filename: str = "unittest.txt"):
        self.input = input_stream(filename) if dev else input
        self.input_log = []
        self.output_log = []

    def get_input(self, n: int = 1) -> None:
        if print_input_logs:
            self.input_log += [self.input() for _ in range(n)]
            if print_input_logs:
                [debug(log) for log in self.input_log[-n:]]
            lst = [i.split() for i in self.input_log[-n:]]
            return [int(item) for sublist in lst for item in sublist]
        else:
            lst = [self.input().split() for _ in range(n)]
            return [int(item) for sublist in lst for item in sublist]

    def send_action(self, actions: list):
        if len(actions) == 0:
            actions = ["WAIT"]
        message = ";".join(action.__str__() for action in actions)
        if print_input_logs:
            self.output_log.append(message)
        print(f"{message}")

# TODO
# - capture and print the spawn max, min, mean & std (for threshold tuning)
# - spawn if op units > me units
# - Agression - Build / spawn rate dynamic to my tiles / op tiles 
# - Spawn - Edge of op else edge of ne

# - islands - Consider unique boards / games per island (Use masks? * layer / cluster 3 )
# - island domination:
#       - dominated - spawn more, build less
#       - dominating - Spawn less, build more

# - On island , Move to switch to path based only
# - Remove islands entirely from conv gradients or make unique gradients for each cluster 


def main():
    io = InputOutput('boundaries.txt')
    col, row = io.get_input()
    move_weights = {
        'scrap_amount_local': +1,
        'owner_op_global':    +20,
        'owner_me_global':    -10,
        'owner_ne_global':    +10,
        'tile_live_global':   +1,
        'tile_dead_global':   -1,
        'units_op_global':    +15,
        'units_me_global':    -15,
    }
    spawn_weights = {
        'owner_op_global':    +20,
        'owner_ne_global':    +10,
        'units_me_global':    -20,
    }


    while True:
        try:
            my_matter, op_matter = io.get_input()
            input_array = np.array(io.get_input(row * col)).reshape(row, col, 7)
            board = Board(input_array)
            actions = []
            actions += get_move_actions(board, move_weights)
            if board.units_op.sum() > 0:
                if my_matter >= 10 and board.should_build.sum() > 0:
                    if board.recycler_me.sum() / board.should_build.sum() < 0.1:
                        actions += get_build(board)
                        my_matter -= 10
                if my_matter >= 10 and board.should_spawn.sum() > 0:
                    k = (my_matter) // 10
                    actions += get_spawn(board, spawn_weights, k)
                    my_matter -= k * 10
            io.send_action(actions)
        except EOFError:
            debug("EOF")
            break

if __name__ == '__main__':
    main()

