"""Main gameplay loop for AIVenture"""
import Generator
import Mob
import World


class Game:
    def __init__(self):
        self.gen = Generator.Generator()
        self.player = Mob.Mob("Player", None)
        self.world = World.World()
        self.history = []
        self.commands = {
            "look": self.look,
            "go": self.go,
            "take": self.take,
            "drop": self.drop,
            "save": self.save,
            "quit": self.quit,
            "hit": self.attack,
            "attack": self.attack,
            "wear": self.equip,
            "hold": self.hold,
            "help": self.help
        }

    def help(self, cmd: str = ""):
        self.display(f"You may do the following, {', '.join(self.commands.keys())}")

    def look(self, at: str = "") -> bool:
        """Looks around the current room if at is blank, or displays description of item or mob if it's found"""
        if at == "":
            self.display(str(self.player.location.describe()), False)
            self.history.append(str(self.player.location.json()))
        return self.player.alive()

    def go(self, where: str) -> bool:
        """Changes to the room in the given direction"""
        if where not in self.player.location.exits:
            self.display(f"You try to go {where} but can't figure out how to.")
            return self.player.alive()
        if self.player.location.exits[where] is None:
            """Have to generate a new room!"""
            self.display(f"You move {where}.")
            new_room = Generator.Generator().new_room(self.history)
            if new_room is None:
                return self.player.alive()
            new_room.exits[World.flip(where)] = self.player.location
            self.player.location.exits[where] = new_room
        self.player.go(where)
        self.display(f"You arrive at {self.player.location}.")
        return self.player.alive()

    def take(self, thing: str) -> bool:
        """Takes items"""
        self.display("Sorry dave, I can't do that")
        return self.player.alive()

    def drop(self, thing: str) -> bool:
        """Drops the indicated item if it's in inventory or in hand"""
        self.display("It's stuck")
        return self.player.alive()

    def equip(self, what: str) -> bool:
        """Equips the specified item if it can be worn"""
        self.display("That doesn't fit")
        return self.player.alive()

    def hold(self, what: str) -> bool:
        """Holds the specified item in hand"""
        self.display("It slips from your hands")
        return self.player.alive()

    def save(self, file_name: str) -> bool:
        """Saves the game"""
        self.display("I cannot save you")
        return self.player.alive()

    def quit(self, arg: str = "") -> bool:
        """Exits the game to main menu if confirmed"""
        result = input("Are you sure?  Unsaved progress will be lost (y/N): ").lower()
        if result == "":
            result = "n"
        return result == "n"

    def attack(self, who: str) -> bool:
        """Tries to attack the given mob"""
        self.display("Stop hitting yourself")
        return self.player.alive()

    def display(self, text, log=True) -> None:
        """This should be """
        if log:
            self.history.append(text)
        print(text)

    def run_game(self):
        """Main gameplay loop"""
        # self.look()
        running = True
        # L.R.E.P.
        while running:  # Loop
            # Read the user's command
            self.look()
            line = input(":> ").strip()
            parts = line.split(" ")
            cmd = parts[0]
            rest = " ".join(parts[1:])
            # Execute (if valid)
            print(f"player wants to [{cmd}] with [{rest}]")
            if cmd in self.commands:
                running = self.commands[cmd](rest)
            elif cmd == "":
                continue
            else:
                print("That's not a valid command.")
            # Print the result
            pass

    def load(self, fileName: str):
        """Loads game data from the specified file"""


if __name__ == "__main__":
    game = Game()
    while True:
        print("1. Start new game")
        print("2. Load game")
        print("3. Quit")
        choice = input(":> ")
        if choice == 2:
            fileName = input("Enter name of save file")
            if not fileName.endswith(".json"):
                fileName += ".json"
            game.load(fileName)
        if choice == "1" or choice == "2":
            game.run_game()
        if choice == "3":
            exit(0)
