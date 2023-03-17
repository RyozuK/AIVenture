import Inventory

Directions = {"up", "down", "east", "west", "north", "south"}
FlipDirections = {"north": "south",
                  "south": "north",
                  "east": "west",
                  "west": "east",
                  "up": "down",
                  "down": "up"}


def flip(direction):
    if direction in FlipDirections:
        return FlipDirections[direction]
    else:
        return direction


class World:
    def __init__(self):
        """Tracks the world itself.  Each room in the world has a unique id that can be used to look up the room
        and connect rooms together."""
        self.rooms = {}


class Room:
    _index = 0

    def __init__(self, name: str, description: str, exits=None, items=None):
        if exits is None:
            exits = {}
        if type(exits) is list:
            exits = {x: None for x in exits}
        self.id = 0
        Room._index += 1
        self.name = name
        self.description = description
        self.exits = exits
        self.inventory = Inventory.Inventory(items)

    def __str__(self):
        return self.name

    def describe(self):
        return f"{self.name}\n{self.description}\nItems: {self.inventory}\nExits: {', '.join(self.exits.keys())}"

    def json(self):
        return {'name': self.name,
                'description': self.description,
                'exits': [d for d in self.exits.keys()]
                }


def get_start():
    desc = """A dark, musty prison cell in the dungeon. The walls are made of stone.
There is a door to the north that is slightly open.  A dead goblin lays in front of the door"""
    sword = Inventory.Item("sword", "a short rusty sword taken from a goblin", Inventory.Item.Weapon, 2, -1)
    return Room("Dungeon cell", desc, {"north": None}, [sword])
