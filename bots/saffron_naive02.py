"""saffron_naive02
i do this:
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


class BotPlayer(Player):
    def __init__(self, map: Map):
        self.next_tower_to_build_idx = 0
        self.next_tower_to_build_map = {
            0: TowerType.SOLAR_FARM,
            1: TowerType.GUNSHIP,
            2: TowerType.BOMBER,
            3: TowerType.REINFORCER,
        }

        # locs (x,y) that are open for towers
        # self.empty_locs: set[tuple[int, int]] = self.init_empty_locs(map)
        self.empty_pathborders: set[tuple[int, int]] = self.init_empty_pathborders(map)
        self.next_bomber_loc = None

        self.map = map

    # def init_empty_locs(self, map: Map):
    #     pass

    def init_empty_pathborders(self, map: Map) -> set[tuple[int, int]]:
        dir_vecs = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 0),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ]
        ans = set()
        for loc in map.path:
            pathx, pathy = loc
            for xoffset, yoffset in dir_vecs:
                borderx = pathx + xoffset
                bordery = pathy + yoffset
                if map.is_space(borderx, bordery):
                    ans.add((borderx, bordery))
        return ans


    def play_turn(self, rc: RobotController):
        self.build_towers(rc)
        self.towers_attack(rc)

    def build_towers(self, rc: RobotController):
        to_build = self.next_tower_to_build_map[self.next_tower_to_build_idx]
        x, y = self.choose_new_tower_loc()
        if rc.can_build_tower(to_build, x, y):
            rc.build_tower(to_build, x, y)
            if self.next_tower_to_build_map[self.next_tower_to_build_idx] == TowerType.BOMBER:
                self.next_bomber_loc = None

            self.update_build_idx(rc)

    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.STRONG)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)

    def choose_new_tower_loc(self):
        if self.next_tower_to_build_map[self.next_tower_to_build_idx] == TowerType.BOMBER:
            if self.next_bomber_loc is None:
                if len(self.empty_pathborders) == 0:
                    return (0,0)
                else:
                    self.next_bomber_loc = self.empty_pathborders.pop()

            return self.next_bomber_loc
        
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

    def update_build_idx(self, rc: RobotController):
        if rc.get_turn() > 2000:
            self.next_tower_to_build_idx = 2
            return

        self.increment_build_idx()
        while (
            self.next_tower_to_build_map[self.next_tower_to_build_idx]
            == TowerType.REINFORCER
        ):
            self.increment_build_idx()

    def increment_build_idx(self):
        self.next_tower_to_build_idx += 1
        self.next_tower_to_build_idx %= 4
