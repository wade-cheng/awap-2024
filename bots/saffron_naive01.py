"""saffron_naive01
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
        self.map = map

    def play_turn(self, rc: RobotController):
        self.build_towers(rc)
        self.build_towers(rc)
        self.build_towers(rc)
        self.build_towers(rc)
        self.towers_attack(rc)

    def build_towers(self, rc: RobotController):
        to_build = self.next_tower_to_build_map[self.next_tower_to_build_idx]
        x, y = self.choose_new_tower_loc()
        if rc.can_build_tower(to_build, x, y):
            rc.build_tower(to_build, x, y)

            self.update_build_idx(rc)

    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)

    def choose_new_tower_loc(self):
        return (
            random.randint(0, self.map.width - 1),
            random.randint(0, self.map.height - 1),
        )

    def update_build_idx(self, rc: RobotController):
        if rc.get_turn() > 2000:
            self.next_tower_to_build_idx = 2
            return

        self.increment_build_idx()
        while (
            self.next_tower_to_build_map[self.next_tower_to_build_idx]
            == TowerType.REINFORCER
            or self.next_tower_to_build_map[self.next_tower_to_build_idx]
            == TowerType.GUNSHIP
        ):
            self.increment_build_idx()

    def increment_build_idx(self):
        self.next_tower_to_build_idx += 1
        self.next_tower_to_build_idx %= 4
