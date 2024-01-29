"""saffron_naive05_06
05 version 06:
minor optimization tweaks from the 05-variants
stop building farms once enough
no reinforcers
2 bomb towers

05
optimizations by yoinking other people's ideas lol
- selling 
- only fiveish bomb towers are sufficient (thanks amogus, I think)
- sell farms when board is full

04
tries to obtain perfectly optimal attacker placing

03
minor tweaks to algorithm

02
naive01 but bomb towers are next to the path and plantations aren't

naive01 did this:
alternates between plantations and bomb towers, changing to only bomb after turn 2000.
places randomly.
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

        # NEW LOGIC
        self.towers_spawned = 0

        self.path_locs: set[tuple[int, int]] = self.get_path_locs(map)
        self.space_locs: set[tuple[int, int]] = self.get_space_locs(map)
        self.ordered_bomberlocs: list[tuple[tuple[int, int], int]] = self.get_ordered_bomberlocs(map, self.path_locs)
        self.next_shooter_loc: tuple[int, int] = self.ordered_bomberlocs.pop()[0]
        self.next_farm_loc: tuple[int, int] = self.ordered_bomberlocs.pop(0)[0]
        self.farm_towers_endgame: set[Tower] = None
        # for loc in self.ordered_bomberlocs:
        #     print(loc)
        self.solar_farms: int = 0


        self.map = map
        
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

    def get_ordered_bomberlocs(self, map: Map, path_locs: set[tuple[int, int]]) -> list[tuple[tuple[int, int], int]]:
        """returns a list of ((x, y), n) sorted by n ascending
        where (x, y) is a possible bomber location and n is its efficiency
        """
        temp: list[tuple[tuple[int, int], int]] = []
        for x in range(map.width):
            for y in range(map.height):
                if map.is_space(x, y):
                    temp.append(((x, y), self.get_bomber_efficiency(x, y, path_locs)))

        return sorted(temp, key=lambda orderedloc: orderedloc[1])


    def get_bomber_efficiency(self, x: int, y: int, path_locs: set[tuple[int, int]]):
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

        # print(f"intersection: {sorted(list(path_locs and tiles_in_range))}")
        # print(f"pathlocs {sorted(list(path_locs))}")
        temp = len(path_locs.intersection(tiles_in_range))
        # print(f"efficiency{temp}")
        return temp

    def play_turn(self, rc: RobotController):
        self.build_towers(rc)
        self.towers_attack(rc)

    def build_towers(self, rc: RobotController):
        if self.farm_towers_endgame is not None:
            if len(self.farm_towers_endgame) == 0:
                return
            
            # we're in the endgame now...
            to_sell: Tower = self.farm_towers_endgame.pop()
            x = to_sell.x
            y = to_sell.y
            rc.sell_tower(to_sell.id)
            rc.build_tower(TowerType.GUNSHIP, x, y)


        to_build: TowerType = self.next_tower(rc)
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
                    self.farm_towers_endgame = set([tower for tower in rc.get_towers(rc.get_ally_team()) if tower.type == TowerType.SOLAR_FARM])
                return 

            # account for early game single gunship to defend against rushes
            if self.towers_spawned == 2:
                try:
                    self.next_shooter_loc = self.ordered_bomberlocs.pop(-10)[0]
                except:
                    # try except in case there are less than 10 possible places
                    self.next_shooter_loc = self.ordered_bomberlocs.pop()[0]

            if to_build == TowerType.SOLAR_FARM:
                self.next_farm_loc = self.ordered_bomberlocs.pop(0)[0]
            else:
                self.next_shooter_loc = self.ordered_bomberlocs.pop()[0]

            self.towers_spawned += 1

    def next_tower(self, rc: RobotController) -> TowerType:
        """returns the next tower we should build since we know self.towers_spawned"""
        # n % 7 is [0, 7)
        # 2 farms

        print(f"len(space_lcos) is {len(self.space_locs)}")
        if self.solar_farms > len(self.space_locs) / 3:
            return TowerType.GUNSHIP

        if self.towers_spawned <= 1:
            return TowerType.SOLAR_FARM
        
        # 3 bombers
        if self.towers_spawned <= 4:
            return TowerType.BOMBER
        
        # alternate gunships and farms
        if self.towers_spawned % 2 == 0:
            return TowerType.GUNSHIP
        return TowerType.SOLAR_FARM
        # elif self.towers_spawned == 1:
        #     return TowerType.SOLAR_FARM
        # elif self.towers_spawned == 2:
        #     return TowerType.BOMBER
        # elif self.towers_spawned == 3:
        #     return TowerType.SOLAR_FARM
        # elif self.towers_spawned == 4:
        #     return TowerType.BOMBER
        # elif self.towers_spawned == 5:
        #     return TowerType.SOLAR_FARM
        # elif self.towers_spawned == 6:
        #     return TowerType.GUNSHIP

        # if turn < 2000:
        #     if self.towers_spawned % 7 == 0:
        #         return TowerType.SOLAR_FARM
        #     elif self.towers_spawned % 7 == 1:
        #         return TowerType.BOMBER
        #     elif self.towers_spawned % 7 == 2:
        #         return TowerType.SOLAR_FARM
        #     elif self.towers_spawned % 7 == 3:
        #         return TowerType.GUNSHIP
        #     elif self.towers_spawned % 7 == 4:
        #         return TowerType.SOLAR_FARM
        #     elif self.towers_spawned % 7 == 5:
        #         return TowerType.BOMBER
        #     elif self.towers_spawned % 7 == 6:
        #         return TowerType.GUNSHIP
        #     else:
        #         print("what")

        if self.towers_spawned % 7 == 0:
            return TowerType.SOLAR_FARM
        elif self.towers_spawned % 7 == 1:
            return TowerType.GUNSHIP
        elif self.towers_spawned % 7 == 2:
            return TowerType.SOLAR_FARM
        elif self.towers_spawned % 7 == 3:
            return TowerType.GUNSHIP
        elif self.towers_spawned % 7 == 4:
            return TowerType.BOMBER
        elif self.towers_spawned % 7 == 5:
            return TowerType.GUNSHIP
        elif self.towers_spawned % 7 == 6:
            return TowerType.BOMBER
        

    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for i, tower in enumerate(towers):
            # if we are in the earlygame (< 2000 ticks), all gunships should snipe the first
            # if we've passed the earlygame, split them between sniping strong and first
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

    def __choose_random_loc(self):
        loc = (
            random.randint(0, self.map.width - 1),
            random.randint(0, self.map.height - 1),
        )
        while loc in self.empty_pathborders:
            loc = (
                random.randint(0, self.map.width - 1),
                random.randint(0, self.map.height - 1),
            )
        self.empty_pathborders.discard(loc)
        return loc
