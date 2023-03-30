import Inventory
from Generator import Generator

Directions = {"up", "down", "east", "west", "north", "south"}
FlipDirections = {"north": "south",
                  "south": "north",
                  "east": "west",
                  "west": "east",
                  "up": "down",
                  "down": "up"}

# Following a traditional x,y,z format with 0,0 as the top left
Increments = {
    "north": (0, -1, 0),
    "south": (0, 1, 0),
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 0, 1),
    "down": (0, 0, -1)
}


def increment_pos(pos, direction):
    if direction not in Increments:
        return pos
    i = Increments[direction]
    return pos[0] + i[0], pos[1] + i[1], pos[2] + i[2]


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

    def add_room(self, room):
        self.rooms[room.position] = room

    def go_to_room(self, pos, direction, log):
        """Instead of generating rooms in AIVenture main loop, do it here instead"""
        new_pos = increment_pos(pos, direction)
        if new_pos not in self.rooms:
            new_room = Generator.new_room(log)
            old_room = self.rooms[pos]
            if new_room is None:
                return old_room
            if flip(direction) not in new_room.exits:
                new_room.exits.append(flip(direction))
            new_room.position = new_pos
            self.add_room(new_room)

        return self.rooms[new_pos]

    def get_room(self, pos):
        return self.rooms[pos]


class Room:

    def __init__(self, name: str, description: str, exits=None, items=None, position=(0, 0, 0)):
        if exits is None:
            exits = []
        self.position = position
        self.name = name
        self.description = description
        self.exits = exits
        self.inventory = Inventory.Inventory(items)

    def __str__(self):
        return self.name

    def describe(self):
        return f"{self.name}\n{self.description}\nItems: {self.inventory}\nExits: {', '.join(self.exits)}"

    def json(self):
        return {'name': self.name,
                'description': self.description,
                'exits': self.exits
                }


def get_start():
    desc = """A dark, musty prison cell in the dungeon. The walls are made of stone.
There is a door to the north that is slightly open.  A dead goblin lays in front of the door"""
    sword = Inventory.Item("sword", "a short rusty sword taken from a goblin", Inventory.Item.Weapon, 2, -1)
    return Room("Dungeon cell", desc, ["north"], [sword])
