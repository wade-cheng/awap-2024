"""from team djsquared at https://github.com/jack-champagne/djsquared-bot/"""

import random
from enum import Enum
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map
import numpy as np

NUM_TOWERS_PER_REINF = 5

MINIMUM_HEALTH = 51 # Enough to survive a 2 gunshots
GAPFILL = 7
FUDGE_FACTOR = 1.1
CLUSTER_SIZE = 60

BOMBER_DPS = 0.4
BOMBER_DAMAGE = 6
GUNSHIP_DPS = 1.25
GUNSHIP_DAMAGE = 25

class BotMode(Enum):
    STARTING = 0
    DEFENDING = 1
    FARMING = 2
    ATTACKING = 3
    SELLING_ALL = 4

def max_cluster(reinf_tiles):
    tile = np.unravel_index(np.argmax(reinf_tiles), reinf_tiles.shape)
    return tile

def num_tiles_in_range(map: Map):
    # Upper bounds on bounding square
    GUNX = GUNY = int(np.sqrt(TowerType.GUNSHIP.range))
    BOMBX = BOMBY = int(np.sqrt(TowerType.BOMBER.range))

    gunship_tiles = np.zeros(shape=(map.width, map.height), dtype=int)
    bomber_tiles = np.zeros(shape=(map.width, map.height), dtype=int)
    for tile in map.path:
        x, y = tile
        for tower_x in range(x - GUNX, x + GUNX + 1):
            for tower_y in range(y - GUNY, y + GUNY + 1):
                if not map.is_space(tower_x, tower_y):
                    continue
                if (x - tower_x)**2 + (y - tower_y)**2 <= TowerType.GUNSHIP.range:
                    gunship_tiles[tower_x, tower_y] += 1
        
        for tower_x in range(x - BOMBX, x + BOMBX + 1):
            for tower_y in range(y - BOMBY, y + BOMBY + 1):
                if not map.is_space(tower_x, tower_y):
                    continue
                if (x - tower_x)**2 + (y - tower_y)**2 <= TowerType.BOMBER.range:
                    bomber_tiles[tower_x, tower_y] += 1
    
    return (gunship_tiles, bomber_tiles)

def reinf_value(tower_tiles, num_towers, map):
    """
    Returns the best sport to place a reinforcement,
    assuming you can only place a given number of towers
    Very inefficient function...
    """
    REINFX = REINFY = int(np.sqrt(TowerType.REINFORCER.range))
    reinf_val = np.zeros(shape=(map.width, map.height), dtype=int)
    for x in range(map.width):
        for y in range(map.height):
            if not map.is_space(x, y):
                continue
            value_in_range = []
            for tower_x in range(x - REINFX, x + REINFX + 1):
                for tower_y in range(y - REINFY, y + REINFY + 1):
                    if not(map.is_space(tower_x, tower_y)) or (tower_x == x and tower_y == y):
                        continue
                    if (x - tower_x)**2 + (y - tower_y)**2 <= TowerType.REINFORCER.range:
                        value_in_range.append(tower_tiles[tower_x, tower_y])

            value_in_range.sort()
            for i in range(min(num_towers, len(value_in_range))):
                reinf_val[x, y] += value_in_range[len(value_in_range)-1-i]

    return reinf_val

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

        gunship_tiles, bomber_tiles = num_tiles_in_range(self.map)
        self.base_gunship_tiles = gunship_tiles.copy()
        self.base_bomber_tiles = bomber_tiles.copy()
        self.gunship_tiles = gunship_tiles
        self.bomber_tiles = bomber_tiles
        self.gunship_strike_mult, self.bomber_strike_mult = self.get_strike_mult()

        self.cur_reinfs = set()
        self.cur_farm_reinf = None
        self.farm_reinf_boundary = set()
        # Tentative farm tiles
        self.farm_tiles = set()

        # STARTING metrics
        self.num_towers = 0

        self.gun_rate = 6
        self.bomb_rate = 2
        self.ratio_sum = self.gun_rate + self.bomb_rate

        # Current mode
        self.mode = BotMode.STARTING

    def set_farm_cluster(self, corner, rc):
        self.cur_farm_reinf = corner
        self.cur_reinfs.add(corner)
        x, y = corner
        for new_corner in [(x-2,y-2),(x-2,y+2),(x+2,y-2),(x+2,y+2)]:
            if (new_corner not in self.cur_reinfs) and rc.is_placeable(rc.get_ally_team(), new_corner[0], new_corner[1]):
                self.farm_reinf_boundary.add(new_corner)

    def next_farm_reinf(self, rc: RobotController):
        """
        XOOOXOOOX
        OOOOOOOOO
        OOXOOOXOO <- relatively good layout of farms and reinforcer
        OOOOOOOOO
        XOOOXOOOX
        """
        min_val = 10000
        min_corner = None
        for corner in self.farm_reinf_boundary:
            if self.reinf_tiles[corner[0], corner[1]] < min_val:
                min_corner = corner
                min_val = self.reinf_tiles[corner[0], corner[1]]
        self.cur_farm_reinf = min_corner
        # print("next corner: ", min_corner)
        if min_corner is None:
            return
        
        self.farm_reinf_boundary.remove(min_corner)
        self.set_farm_cluster(min_corner, rc)
        self.get_new_farm_locs(min_corner, rc)
        # print("new farm locs", self.farm_tiles)

    def init_farm_cluster(self, rc):
        min_reinf = 1000
        tile = None
        for x in range(self.map.width):
            for y in range(self.map.height):
                if self.map.is_space(x, y):
                    if self.reinf_tiles[x, y] < min_reinf:
                        min_reinf = self.reinf_tiles[x, y]
                        tile = (x, y)
        self.set_farm_cluster(tile, rc)
        # print("starting tile: ", tile)
        if tile:
            self.next_farm_reinf(rc)
    
    def reset_farm(self):
        self.cur_reinfs = set()
        self.cur_farm_reinf = None
        self.farm_reinf_boundary = set()
        # Tentative farm tiles
        self.farm_tiles = set()
        
    def get_new_farm_locs(self, next_reinf, rc):
        """
        Adds new farm locations
        """
        x, y = next_reinf
        for new_corner in [(x-2,y-2),(x-2,y+2),(x+2,y-2),(x+2,y+2)]:
            if new_corner not in self.cur_reinfs:
                continue
            minx, maxx = min(x, new_corner[0]), max(x, new_corner[0])
            miny, maxy = min(y, new_corner[1]), max(y, new_corner[1])
            for tower_x in range(minx, maxx+1):
                for tower_y in range(miny, maxy+1):
                    if (tower_x == x and tower_y == y) or (tower_x == new_corner[0] and tower_y == new_corner[1]):
                        continue
                    if rc.is_placeable(rc.get_ally_team(), tower_x, tower_y):
                        self.farm_tiles.add((tower_x, tower_y))
    
    def fallback_farm_loc(self, rc: RobotController):
        min_reinf = 1000
        tile = None
        for x in range(self.map.width):
            for y in range(self.map.height):
                if rc.is_placeable(rc.get_ally_team(), x, y):
                    if self.gunship_tiles[x, y] < min_reinf:
                        min_reinf = self.gunship_tiles[x, y]
                        tile = (x, y)
        if rc.get_balance(rc.get_ally_team()) >= TowerType.SOLAR_FARM.cost:
            tower_x, tower_y = tile
            # print("fallback farm tile", tower_x, tower_y)
            if rc.can_build_tower(TowerType.SOLAR_FARM, tower_x, tower_y):
                rc.build_tower(TowerType.SOLAR_FARM, tower_x, tower_y)

    def fill_farm_tile(self, rc):
        if rc.get_balance(rc.get_ally_team()) >= TowerType.SOLAR_FARM.cost:
            tower_x, tower_y = self.farm_tiles.pop()
            # print("attempting farm tile", tower_x, tower_y)
            if rc.can_build_tower(TowerType.SOLAR_FARM, tower_x, tower_y):
                rc.build_tower(TowerType.SOLAR_FARM, tower_x, tower_y)

    def build_farm(self, rc: RobotController):
        if len(self.farm_tiles) == 0:
            # print("out of farm tiles")
            if len(self.farm_reinf_boundary) == 0:
                self.fallback_farm_loc(rc)
            elif not self.cur_farm_reinf:
                self.next_farm_reinf(rc)
                if len(self.farm_tiles) > 0:
                    self.fill_farm_tile(rc)
                else:
                    self.fallback_farm_loc(rc)
            else:
                tower_x, tower_y = self.cur_farm_reinf
                if rc.can_build_tower(TowerType.REINFORCER, tower_x, tower_y):
                    # print("placing reinf tile")
                    rc.build_tower(TowerType.REINFORCER, tower_x, tower_y)
                    self.cur_farm_reinf = None
        else:
            self.fill_farm_tile(rc)        


    def optimal_tower(self, tower_tiles, rc):
        while True:
            tile = np.unravel_index(np.argmax(tower_tiles), tower_tiles.shape)
            x, y = int(tile[0]), int(tile[1])
            if tower_tiles[x, y] == 0:
                return tile
            # Prevent future placements on this tile
            tower_tiles[x, y] = 0
            if rc.is_placeable(rc.get_ally_team(), x, y):
                return tile
    
    def get_num_farms(self, rc):
        num_farms = 0
        for tower in rc.get_towers(rc.get_ally_team()):
            if tower.type == TowerType.SOLAR_FARM:
                num_farms += 1
        return num_farms
    
    def get_total_value(self, rc):
        value = 0
        for tower in rc.get_towers(rc.get_ally_team()):
            value += tower.type.cost
        return value
    
    def sell_all(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.SOLAR_FARM:
                # Add farm spot into farm_tiles
                self.farm_tiles.add((tower.x, tower.y))
            rc.sell_tower(tower.id)
        self.reset_farm()
        self.init_farm_cluster(rc)

    def sell_one(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.BOMBER or tower.type == TowerType.GUNSHIP:
                rc.sell_tower(tower.id)
                return
        for tower in towers:
            if tower.type == TowerType.SOLAR_FARM or tower.type == TowerType.REINFORCER:
                rc.sell_tower(tower.id)
                return

    def sell_farms(self, target, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        num_towers = 0
        for tower in towers:
            if tower.type == TowerType.SOLAR_FARM:
                num_towers += 1

        for tower in towers:
            if tower.type == TowerType.SOLAR_FARM:
                if num_towers <= target:
                    break
                # Add farm spot into farm_tiles
                self.farm_tiles.add((tower.x, tower.y))
                rc.sell_tower(tower.id)
                num_towers -= 1

    def get_strike_mult(self):
        """
        Attempt to calculate the ratio of extra times a debris can be hit for single target
        on a windy map where debris leaves and enters the range of the tower
        """
        # tile = np.unravel_index(np.argmax(self.base_gunship_tiles), self.base_gunship_tiles.shape)
        # tower_x, tower_y = int(tile[0]), int(tile[1])
        gunship_strike_mult = []
        bomber_strike_mult = []
        for tower_x in range(self.map.width):
            for tower_y in range(self.map.height):
                if not self.map.is_space(tower_x, tower_y):
                    continue
                since_in_range = 100
                temp_mult = 0
                for tile in self.map.path:
                    x, y = tile
                    since_in_range += 1
                    if (x - tower_x)**2 + (y - tower_y)**2 <= TowerType.GUNSHIP.range:
                        if since_in_range >= TowerType.GUNSHIP.cooldown:
                            temp_mult += 1
                            since_in_range = 0
                # temp_mult *= TowerType.GUNSHIP.cooldown / self.base_gunship_tiles[tower_x, tower_y]
                # if temp_mult > gunship_strike_mult:
                gunship_strike_mult.append(temp_mult)
        
                since_in_range = 100
                temp_mult = 0
                for tile in self.map.path:
                    x, y = tile
                    since_in_range += 1
                    if (x - tower_x)**2 + (y - tower_y)**2 <= TowerType.BOMBER.range:
                        if since_in_range >= TowerType.BOMBER.cooldown:
                            temp_mult += 1
                            since_in_range = 0
                # if temp_mult > bomber_strike_mult:
                bomber_strike_mult.append(temp_mult)

        gunship_strike_mult = np.average(np.sort(gunship_strike_mult)[-10:])
        bomber_strike_mult = np.average(np.sort(bomber_strike_mult)[-10:])
        return (gunship_strike_mult, bomber_strike_mult)



    def check_offense_power(self, num_farms, num_enemy_farms, rc):
        towers = rc.get_towers(rc.get_enemy_team())
        # Recompute health if cached value is incorrect
        tg = 0
        nguns = 0
        tb = 0
        nbombs = 0
        # for tower in towers:
            # if tower.type == TowerType.REINFORCER:

        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                tg += self.base_gunship_tiles[tower.x, tower.y]
                nguns += 1
            elif tower.type == TowerType.BOMBER:
                tb += self.base_bomber_tiles[tower.x, tower.y]
                nbombs += 1

        next_best_bomber = np.max(self.base_bomber_tiles) # Fudge factor with 2 additional bombers
        self.desired_health = int(max(MINIMUM_HEALTH,
                                    BOMBER_DAMAGE*np.ceil((BOMBER_DPS * (tb + 2 * next_best_bomber))/BOMBER_DAMAGE) + # Bomber damage
                                    GUNSHIP_DAMAGE*np.floor(nguns / 5) + # Gunship damage
                                    GAPFILL))

        # Check if no offensive tower
        if nguns + nbombs <= 1:
            cluster_cost = rc.get_debris_cost(1, self.desired_health)
            cluster_damage_per_cost = self.desired_health / cluster_cost
        else:
            # How many farms are we willing to sell? Up to enemy farms? Unless hail mary...
            cluster_cost = rc.get_debris_cost(1, self.desired_health)
            cluster_damage_per_cost = 0.5 * self.desired_health / cluster_cost
        total_value = rc.get_balance(rc.get_ally_team())
        total_value += self.get_total_value(rc) * 0.8
        overkill = max(0, rc.get_turn() - 1500)
        if (cluster_damage_per_cost * cluster_cost * int(total_value / cluster_cost) >= rc.get_health(rc.get_enemy_team()) + overkill
            and cluster_damage_per_cost * cluster_cost * int(total_value / cluster_cost) >= 500):
            self.sending_health = self.desired_health
            self.sending = int(total_value / cluster_cost)
            self.sell_all(rc)
            self.mode = BotMode.ATTACKING
            # print("sell everything - sending cluster ", self.sending_health)
        else:
            # Normal assault
            total_value = rc.get_balance(rc.get_ally_team())
            if num_farms > num_enemy_farms:
                total_value += (num_farms - num_enemy_farms) * 0.8 * TowerType.SOLAR_FARM.cost
            if (total_value >= cluster_cost * CLUSTER_SIZE
                and CLUSTER_SIZE * 0.5 * self.desired_health >= 1250):
                self.sending_health = int(self.desired_health)
                self.sending = CLUSTER_SIZE
                # if num_farms > num_enemy_farms:
                #     self.sell_farms(num_enemy_farms, rc)
                self.mode = BotMode.ATTACKING
                # print("switch to attacking - sending cluster", self.sending_health)

        # if (total_value >= single_cost 
        #     and single_damage_per_cost > cluster_damage_per_cost 
        #     and single_damage_per_cost*total_value >= 1000):
        #     # Assumes about 50% get through
        #     self.sending_health = int(self.single_health)
        #     self.sending = int(total_value / single_cost)
        #     if num_farms > num_enemy_farms:
        #         self.sell_farms(num_enemy_farms, rc)
        #     self.mode = BotMode.ATTACKING
        #     print("switch to attacking - sending single", self.sending_health, tg, tb, single_damage_per_cost*total_value)
        # print("attacking", cluster_damage_per_cost*total_value)
    
    def get_defense_power(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        tg = 0
        nguns = 0
        tb = 0
        nbombs = 0
        # for tower in towers:
            # if tower.type == TowerType.REINFORCER:
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                tg += self.base_gunship_tiles[tower.x, tower.y]
                nguns += 1
            elif tower.type == TowerType.BOMBER:
                tb += self.base_bomber_tiles[tower.x, tower.y]
                nbombs += 1
        cluster_health = BOMBER_DAMAGE*np.ceil((BOMBER_DPS * tb)/BOMBER_DAMAGE)
        single_health = (BOMBER_DAMAGE*np.ceil((BOMBER_DPS * tb)/BOMBER_DAMAGE) +
                          GUNSHIP_DAMAGE*np.ceil((GUNSHIP_DPS * tg)/GUNSHIP_DAMAGE))
        
        all_debris = rc.get_debris(rc.get_ally_team())
        debris_life = 0
        for debris in all_debris:
            # Sample stuff in front
            if ((debris.progress < 15 and (debris.total_cooldown <= 2 or debris.total_health >= 50 or rc.get_turn() > 2000))
                or (debris.progress >= self.map.path_length - 15 and not(debris.total_cooldown <= 2 or debris.total_health >= 50 or rc.get_turn() > 2000))):
                # Remove 50% bomber damage from health
                debris_life += 25 * np.ceil(max(0, (debris.health / debris.total_cooldown) - cluster_health) / 25)
        debris_life *= self.map.path_length / 15
        # print("defend power", (cluster_health, single_health, debris_life))
        return (cluster_health, single_health, debris_life)
        

    # Strategies
    def do_offense_strat(self, rc: RobotController):
        if self.sending > 0:
            if rc.get_balance(rc.get_ally_team()) < rc.get_debris_cost(1, self.sending_health):
                # Sell farm
                self.sell_farms(self.get_num_farms(rc) - 1, rc)
            if rc.get_balance(rc.get_ally_team()) >= rc.get_debris_cost(1, self.sending_health):   
                rc.send_debris(1, self.sending_health)
                self.sending -= 1
        if self.sending == 0:
            self.mode = BotMode.FARMING

    def do_defense_strat(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        tg = 0
        nguns = 0
        tb = 0
        nbombs = 0
        # for tower in towers:
            # if tower.type == TowerType.REINFORCER:
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                tg += self.base_gunship_tiles[tower.x, tower.y]
                nguns += 1
            elif tower.type == TowerType.BOMBER:
                tb += self.base_bomber_tiles[tower.x, tower.y]
                nbombs += 1
        
        if (tb + np.max(self.bomber_tiles)) * self.gun_rate * 4 >= self.bomb_rate * tg:
            if rc.get_balance(rc.get_ally_team()) >= TowerType.GUNSHIP.cost:
                gunship_x, gunship_y = self.optimal_tower(self.gunship_tiles, rc)
                gunship_x, gunship_y = int(gunship_x), int(gunship_y)
                if rc.can_build_tower(TowerType.GUNSHIP, gunship_x, gunship_y):
                    rc.build_tower(TowerType.GUNSHIP, gunship_x, gunship_y)
        else:
            if rc.get_balance(rc.get_ally_team()) >= TowerType.BOMBER.cost:
                bomber_x, bomber_y = self.optimal_tower(self.bomber_tiles, rc)
                bomber_x, bomber_y = int(bomber_x), int(bomber_y)
                if rc.can_build_tower(TowerType.BOMBER, bomber_x, bomber_y):
                    rc.build_tower(TowerType.BOMBER, bomber_x, bomber_y)

    def do_farming_strat(self, rc: RobotController):
        if rc.get_balance(rc.get_ally_team()) >= TowerType.SOLAR_FARM.cost:
            self.build_farm(rc)
            
        towers = rc.get_towers(rc.get_enemy_team())
        enemy_value = 0
        num_enemy_farms = 0
        for tower in towers:
            if tower.type == TowerType.SOLAR_FARM:
                num_enemy_farms += 1
            enemy_value += tower.type.cost
        num_farms = self.get_num_farms(rc)


        # Don't farm more than their tower count (TODO: change to value count) (TODO: check debris danger)
        # Need more defense if enemy has more farms, or if it's later in the round
        if rc.get_turn() % 5 == 0:
            # Debris analysis
            cluster_health, single_health, debris_life = self.get_defense_power(rc)
            if debris_life > single_health + 10:
                # print("switch to defending 1")
                self.mode = BotMode.DEFENDING
            # if cluster_health < 24 * np.sqrt(1 + 0.2*num_enemy_farms):
                # Source is that I made it up 
                # if num_farms * TowerType.SOLAR_FARM.cost >= enemy_value:
                    # print("switch to defending 2")
                    # self.mode = BotMode.DEFENDING
            elif self.mode == BotMode.FARMING:
                self.check_offense_power(num_farms, num_enemy_farms, rc)
        # Defend if we have more farm than enemies (more farm should mean less defense)
        # if num_farms >= num_enemy_farms + 1:
            # Rush if enemies have low defense/we have enough money
            # Sell farms if needed. TODO: How many farms?


    def play_turn(self, rc: RobotController):
        if rc.get_turn() == 1:
            gunship_tiles, bomber_tiles = num_tiles_in_range(self.map)
            # print("Gunship:")
            # print(gunship_tiles)
            # print("Bomber:")
            # print(bomber_tiles)
            reinf_gunship_tiles = reinf_value(gunship_tiles, NUM_TOWERS_PER_REINF, self.map)
            reinf_bomber_tiles = reinf_value(bomber_tiles, NUM_TOWERS_PER_REINF, self.map)
            # print("Reinforcement at 1-to-1 ratio:")
            self.reinf_tiles = (self.gun_rate*reinf_gunship_tiles + self.bomb_rate*reinf_bomber_tiles) / self.ratio_sum
            # print(self.reinf_tiles)

            # Init the starting farm location
            self.init_farm_cluster(rc)

        if self.mode == BotMode.STARTING:
            # if rc.get_balance(rc.get_ally_team()) >= TowerType.GUNSHIP.cost:
                # gunship_x, gunship_y = self.optimal_tower(self.gunship_tiles, rc)
                # gunship_x, gunship_y = int(gunship_x), int(gunship_y)
                # if rc.can_build_tower(TowerType.GUNSHIP, gunship_x, gunship_y):
                    # rc.build_tower(TowerType.GUNSHIP, gunship_x, gunship_y)
                    # self.num_towers += 1
            
                    # if self.num_towers >= 5:
                        # print("switch to farming")
                        self.mode = BotMode.FARMING
            
        # When to build farms?
        if self.mode == BotMode.FARMING:
            self.do_farming_strat(rc)

        if self.mode == BotMode.DEFENDING:
            self.do_defense_strat(rc)
            
            enemy_value = 0
            num_enemy_farms = 0
            towers = rc.get_towers(rc.get_enemy_team())    
            for tower in towers:
                if tower.type == TowerType.SOLAR_FARM:
                    num_enemy_farms += 1
                enemy_value += tower.type.cost
            num_farms = self.get_num_farms(rc)
            if rc.get_turn() % 5 == 0: # mod 5 for less computation
                cluster_health, single_health, debris_life = self.get_defense_power(rc)
                if debris_life <= single_health:
                    # if num_farms * TowerType.SOLAR_FARM.cost < enemy_value or cluster_health >= 24 * np.sqrt(1 + 0.2*num_enemy_farms):
                    self.mode = BotMode.FARMING
                elif debris_life > single_health * 1.2:
                    self.sell_farms(num_enemy_farms, rc)
        
        if self.mode == BotMode.ATTACKING:
            self.do_offense_strat(rc)

        self.towers_attack(rc)
        
        
    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.FIRST) # TODO: target enemy with highest current hp
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)