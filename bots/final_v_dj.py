"""final
A slight variation on final.py that lasts slightly longer against djsquared's bot exodius_fortress
their bot is really cool! check out the matches
`python3 run_game.py -b bots/final.py -r bots/exodius_fortress.py -m maps/meow.awap24m --render`
`python3 run_game.py -b bots/final_v_dj.py -r bots/exodius_fortress.py -m maps/meow.awap24m --render`
``

"""

import random
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map
from src.tower import Tower


class BotPlayer(Player):
    def __init__(self, map: Map):
        self.next_tower_to_build_idx = 0
        self.next_tower_to_build_map = {
            0: TowerType.SOLAR_FARM,
            1: TowerType.GUNSHIP,
            2: TowerType.BOMBER,
            3: TowerType.REINFORCER,
        }
        self.map = map

        self.towers_spawned = 0

        self.path_locs: set[tuple[int, int]] = self.get_path_locs(map)
        self.space_locs: set[tuple[int, int]] = self.get_space_locs(map)
        self.ordered_bomberlocs: list[
            tuple[tuple[int, int], int]
        ] = self.get_ordered_bomberlocs(map, self.path_locs)
        self.next_shooter_loc: tuple[int, int] = self.ordered_bomberlocs.pop()[0]
        self.next_farm_loc: tuple[int, int] = self.ordered_bomberlocs.pop(0)[0]
        self.farm_towers_endgame: set[Tower] | None = None
        self.solar_farms: int = 0

    def get_path_locs(self, map: Map) -> set[tuple[int, int]]:
        """returns a set of all (x, y) tuples of paths that exist"""
        ans = set()
        for x in range(map.width):
            for y in range(map.height):
                if map.is_path(x, y):
                    ans.add((x, y))
        return ans

    def get_space_locs(self, map: Map) -> set[tuple[int, int]]:
        """returns a set of all (x, y) tuples of paths that exist"""
        ans = set()
        for x in range(map.width):
            for y in range(map.height):
                if map.is_space(x, y):
                    ans.add((x, y))
        return ans

    def get_ordered_bomberlocs(
        self, map: Map, path_locs: set[tuple[int, int]]
    ) -> list[tuple[tuple[int, int], int]]:
        """returns a list of ((x, y), n) sorted by n ascending
        where (x, y) is a possible bomber location and n is its efficiency
        """
        temp: list[tuple[tuple[int, int], int]] = []
        for x in range(map.width):
            for y in range(map.height):
                if map.is_space(x, y):
                    temp.append(((x, y), self.get_bomber_efficiency(x, y, path_locs)))

        return sorted(temp, key=lambda orderedloc: orderedloc[1])

    def get_bomber_efficiency(
        self, x: int, y: int, path_locs: set[tuple[int, int]]
    ) -> int:
        """gets the paths that a bomber of location (x,y) can effect
        when given path_locs, a set of all (x, y) tuples of paths that exist
        """
        tiles_in_range: set[tuple[int, int]] = set()

        disallowed_bombervecs = {
            (3, 3),
            (3, 2),
            (3, -2),
            (3, -3),
            (2, 3),
            (2, -3),
            (-2, 3),
            (-2, -3),
            (-3, 3),
            (-3, 2),
            (-3, -2),
            (-3, -3),
        }

        for xoffset in range(-3, 4):
            for yoffset in range(-3, 4):
                if (xoffset, yoffset) in disallowed_bombervecs:
                    continue

                tiles_in_range.add((x + xoffset, y + yoffset))

        return len(path_locs.intersection(tiles_in_range))

    def play_turn(self, rc: RobotController) -> None:
        self.build_towers(rc)
        self.towers_attack(rc)

    def build_towers(self, rc: RobotController) -> None:
        if self.farm_towers_endgame is not None:
            if len(self.farm_towers_endgame) == 0:
                return

            # we're in the endgame now...
            to_sell: Tower = self.farm_towers_endgame.pop()
            x = to_sell.x
            y = to_sell.y
            rc.sell_tower(to_sell.id)
            rc.build_tower(TowerType.GUNSHIP, x, y)

        to_build: TowerType = self.next_tower()
        if to_build == TowerType.SOLAR_FARM:
            x, y = self.next_farm_loc
        else:
            x, y = self.next_shooter_loc

        if rc.can_build_tower(to_build, x, y):
            if to_build == TowerType.SOLAR_FARM:
                self.solar_farms += 1
            rc.build_tower(to_build, x, y)

            # start selling
            if len(self.ordered_bomberlocs) == 0:
                print("zeroed out")
                if self.farm_towers_endgame is None:
                    self.farm_towers_endgame = set(
                        [
                            tower
                            for tower in rc.get_towers(rc.get_ally_team())
                            if tower.type == TowerType.SOLAR_FARM
                        ]
                    )
                return

            if to_build == TowerType.SOLAR_FARM:
                self.next_farm_loc = self.ordered_bomberlocs.pop(0)[0]
            else:
                self.next_shooter_loc = self.ordered_bomberlocs.pop()[0]

            self.towers_spawned += 1

    def next_tower(self) -> TowerType:
        """returns the next tower we should build since we know self.towers_spawned"""

        if self.solar_farms > len(self.space_locs) / 3:
            return TowerType.GUNSHIP

        # first, 2 farms
        # if self.towers_spawned <= 1:
        #     return TowerType.SOLAR_FARM

        # then, 3 bombers
        if self.towers_spawned <= 1:
            return TowerType.BOMBER

        # then, alternate gunships and farms
        if self.towers_spawned % 5 == 0:
            return TowerType.SOLAR_FARM
        return TowerType.GUNSHIP

    def towers_attack(self, rc: RobotController) -> None:
        """
        if we are in the earlygame (< 2000 ticks), all gunships should snipe the first
        if we've passed the earlygame, split them between sniping strong and first
        """
        towers = rc.get_towers(rc.get_ally_team())
        for i, tower in enumerate(towers):
            if tower.type == TowerType.GUNSHIP:
                if rc.get_turn() < 2000:
                    rc.auto_snipe(tower.id, SnipePriority.FIRST)
                else:
                    if i % 6 == 0:
                        rc.auto_snipe(tower.id, SnipePriority.STRONG)
                    else:
                        rc.auto_snipe(tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)
