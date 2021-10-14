import random
import math
from queue import SimpleQueue
from gupb.model import weapons, coordinates, tiles
from typing import Type, Dict

import pygame

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

WEAPON_RANGE = {
    'bow': 50,
    'sword': 3,
    'knife': 1
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotController:
    def __init__(self):
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.current_weapon = 'knife'
        self.facing = None  # inicjalizacja przy pierwszym decide
        self.position = None  # inicjalizacja przy pierwszym decide
        self.menhir_coord: coordinates.Coords = None
        self.grid = {}
        self.reached_menhir = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_coord = arena_description.menhir_position
        self.current_weapon = 'knife'
        self.action_queue = SimpleQueue()
        self.reached_menhir = False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__refresh_info(knowledge)

        if self.__can_attack(knowledge.visible_tiles) or self.__should_reload():
            return characters.Action.ATTACK

        if not self.reached_menhir:
            path = Astar.astar(self.grid, self.position, self.menhir_coord)
            if path is not None:
                self.action_queue = self.__generate_queue_from_path(path[:-1]) # without last element, because last element is menhir
                self.reached_menhir = True

        if not self.action_queue.empty():
            return self.action_queue.get()
        elif self.reached_menhir:
            return characters.Action.TURN_LEFT
        else:
            return random.choice([characters.Action.TURN_LEFT,
                                  characters.Action.TURN_RIGHT,
                                  characters.Action.STEP_FORWARD])

    @property
    def name(self) -> str:
        return 'BotController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def __refresh_info(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        character = knowledge.visible_tiles[self.position].character
        self.facing = character.facing
        self.current_weapon = character.weapon.name
        self.grid.update(knowledge.visible_tiles)

    def __can_attack(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if self.current_weapon == 'axe':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, centre_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'amulet':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'bow_loaded' or self.current_weapon == 'sword' or self.current_weapon == 'knife':
                reach = WEAPON_RANGE[self.current_weapon]
                tile = self.position
                for _ in range(1, reach + 1):
                    tile = tile + self.facing.value
                    if visible_tiles[tile].character:
                        return True
        except KeyError:
            # kafelek nie byl widoczny
            return False
        return False

    def __should_reload(self):
        return self.current_weapon == 'bow_unloaded'

    def __generate_queue_from_path(self, path):
        queue = SimpleQueue()
        current_cord = self.position
        current_facing = self.facing
        while len(path) > 0:
            next_coord = path.pop(0)
            desired_facing = characters.Facing(coordinates.sub_coords(next_coord, current_cord))
            if (current_facing == Facing.RIGHT and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.UP) or (
                    current_facing == Facing.UP and desired_facing == Facing.RIGHT):
                queue.put(characters.Action.TURN_RIGHT)

            if (current_facing == Facing.RIGHT and desired_facing == Facing.UP) or (
                    current_facing == Facing.UP and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.RIGHT):
                queue.put(characters.Action.TURN_LEFT)
                
            if (current_facing == Facing.RIGHT and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.UP and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.RIGHT) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.UP):
                queue.put(characters.Action.TURN_LEFT)
                queue.put(characters.Action.TURN_LEFT)

            queue.put(characters.Action.STEP_FORWARD)

            current_cord = next_coord
            current_facing = desired_facing
        return queue


class Astar:
    @staticmethod
    def astar(grid, start_position, end_position):
        start_node = Node(None, start_position)
        end_node = Node(None, end_position)

        open_list = []
        closed_list = []
        open_list.append(start_node)
        while len(open_list) > 0:
            open_list.sort()
            # Get the current node
            current_node = open_list.pop(0)
            # Pop current off open list, add to closed list
            closed_list.append(current_node)

            # Found the goal
            if current_node == end_node:
                path = []
                current = current_node  # parent, a nie current node, poniewaz nie mozemy wejsc ma mnehira
                while current != start_node:
                    path.append(current.position)
                    current = current.parent
                return path[::-1]

            # Generate children
            for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0)]:  # Adjacent squares

                # Get node position
                node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])

                # # Make sure walkable terrain
                if grid.get(node_position) is None or grid[node_position].type in ['sea', 'wall']:
                    continue

                # Create new node
                neighbor = Node(current_node, node_position)
                # Check if the neighbor is in the closed list
                if neighbor in closed_list:
                    continue
                # Generate heuristics (Manhattan distance)
                neighbor.g = abs(neighbor.position[0] - start_node.position[0]) + abs(
                    neighbor.position[1] - start_node.position[1])
                neighbor.h = abs(neighbor.position[0] - end_node.position[0]) + abs(
                    neighbor.position[1] - end_node.position[1])
                neighbor.f = neighbor.g + neighbor.h
                # Check if neighbor is in open list and if it has a lower f value
                if Astar.__add_to_open(open_list, neighbor):
                    # Everything is green, add neighbor to open list
                    open_list.append(neighbor)

    @staticmethod
    def __add_to_open(open_list, neighbor):
        for node in open_list:
            if neighbor == node and neighbor.f >= node.f:
                return False
        return True

class Node():
    def __init__(self, parent=None, position=None):
        self.parent = parent
        self.position = position

        self.g = 0
        self.h = 0
        self.f = 0

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        return self.f < other.f


POTENTIAL_CONTROLLERS = [
    BotController(),
]
