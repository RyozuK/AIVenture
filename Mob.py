import GameExceptions
import World
from Inventory import Inventory


class Mob:
    def __init__(self, name, location):
        self.id = 0
        self.location = location
        self.name = name
        self.cur_hp = 10
        self.max_hp = 10
        self.inventory = Inventory()
        self.held = None
        self.worn = None

    def alive(self) -> bool:
        return self.cur_hp > 0

    def take(self, thing: str):
        """Will take a thing from the current location with the given name"""
        pass

    def drop(self, thing: str):
        """Takes thing from inventory and places it in current location"""
        pass

    def attack(self, thing: str):
        """If thing is something in the current location that can be attacked, attacks it with held item"""
        pass

    def go(self, direction: str):
        """Checks if direction is available for current location.  If it is, tries to go that direction"""
        if direction in self.location.exits:
            self.location = self.location.exits[direction]
