"""saffron_naive06
06 version 02: CURRENT BEST SUBVERSION
optimization tweaks from the 06-variants
- earlygame (tick 500) rush

06
go on offensive when the endgame comes
using 
```
>>> from src.robot_controller import RobotController
>>> RobotController.get_debris_cost("self",1,1)
```

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
        self.ordered_bomberlocs: list[tuple[tuple[int, int], int]] = self.get_ordered_bomberlocs(map, self.path_locs)
        self.next_shooter_loc: tuple[int, int] = self.ordered_bomberlocs.pop()[0]
        self.next_farm_loc: tuple[int, int] = self.ordered_bomberlocs.pop(0)[0]
        self.farm_locs_built: set[tuple[int, int]] = set() # DEPRECATED
        self.farm_towers_endgame: list[Tower] = None

        self.sold_all = False
        # for loc in self.ordered_bomberlocs:
        #     print(loc)


        self.map = map

    # def init_empty_locs(self, map: Map):
    #     pass
        
    def get_path_locs(self, map: Map) -> set[tuple[int, int]]:
        """returns a set of all (x, y) tuples of paths that exist"""
        ans = set()
        for x in range(map.width):
            for y in range(map.height):
                if map.is_path(x, y):
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
        """earlygame rush, optimized for temple by @vi.xen"""
        if rc.get_turn() > 500:
            if not self.sold_all:
                for tower in rc.get_towers(rc.get_ally_team()):
                    rc.sell_tower(tower.id)
            if rc.can_send_debris(4, 100):
                rc.send_debris(4, 100)
            return 
        self.build_towers(rc, self.map)
        self.towers_attack(rc)

    def build_towers(self, rc: RobotController, map: Map):
        if self.farm_towers_endgame is not None:
            # if len(self.farm_towers_endgame) == 0:
            if True:
                # if we've sold all the towers we needed to go on offensive
                print("trying to send")
                if rc.can_send_debris(5, 2000):
                    rc.send_debris(5, 2000)
                return
            
            # hmmmm, what if we don't sell and just start attacking
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
            rc.build_tower(to_build, x, y)

            if len(self.ordered_bomberlocs) == 0:
                # start selling
                print("zeroed out")
                if self.farm_towers_endgame is None:
                    self.farm_towers_endgame = [tower for tower in rc.get_towers(rc.get_ally_team()) if tower.type == TowerType.SOLAR_FARM]
                    print([i.id for i in self.farm_towers_endgame])
                    print("PRINTED\n\n\n\n\n\n\n\n\n\n")
                return 

            if to_build == TowerType.SOLAR_FARM:
                self.farm_locs_built.add((x, y))
                self.next_farm_loc = self.ordered_bomberlocs.pop(0)[0]
            else:
                self.next_shooter_loc = self.ordered_bomberlocs.pop()[0]

            self.towers_spawned += 1

    # TODO TODO TODOOOOOOOOOOOOOOO
    def next_tower(self, rc: RobotController) -> TowerType:
        """returns the next tower we should build since we know self.towers_spawned"""
        # n % 7 is [0, 7)
        turn: int = rc.get_turn()
        if self.towers_spawned == 0:
            return TowerType.SOLAR_FARM
        
        if self.towers_spawned <= 12:
            if self.towers_spawned % 2 == 0:
                return TowerType.BOMBER
            return TowerType.SOLAR_FARM
        
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
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.STRONG)
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
