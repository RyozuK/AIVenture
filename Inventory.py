import json


class ItemExpiredException(Exception):
    def __init__(self, item, result):
        super(ItemExpiredException, self).__init__(f"{item} is out of uses, {result}")


class ItemFailedException(Exception):
    def __init__(self, item, result):
        super(ItemFailedException, self).__init__(f"{item} appears to do nothing, {result}")


"""
Types of items:
Armor (worn)
Key (Used on door, all keys are universal, but one time use)
Weapon (Held)
Treasure (Value)
Potion (Used)
"""


class Item:
    Armor = 0
    Key = 1
    Weapon = 2
    Treasure = 3
    Potion = 4

    def __init__(self, name, description, item_type="", stat=0, uses=-1):
        self.stat = stat
        self.item_type = item_type
        self.id = 0
        self.name = name
        self.description = description
        self.uses = uses

    def use(self, target=None):
        """Will try to use the item depending on it's type"""
        pass

    def json(self) -> dict:
        return {"id": self.id,
                "name": self.name,
                "description": self.description,
                "uses": self.uses,
                "type": self.item_type,
                "stat": self.stat}

    def __str__(self):
        return f"{self.name}"

    def describe(self) -> str:
        if self.uses > 0:
            desc_uses = f" It has {self.uses} charges left."
        else:
            desc_uses = ""
        return f"{self.name}: {self.description}.{desc_uses}"


    @staticmethod
    def from_json(_json: [dict, str]):
        if type(_json) is str:
            _json = json.loads(_json)
        item = Item(_json["name"], _json["description"], _json["type"], _json["stat"], _json["uses"])
        item.id = _json["id"]
        return item


class Inventory:
    def __init__(self, stuff=None):
        if stuff is None:
            stuff = []
        self.items = stuff

    def add_item(self, item: [Item, str]):
        if type(item) is str:
            item = item  # TODO Get item from item database
        self.items.append(item)

    def __str__(self):
        return ', '.join([str(x) for x in self.items])

    def json(self) -> list:
        return [x.json() for x in self.items]

    @staticmethod
    def from_json(_json: [list, str]):
        if type(_json) is str:
            _json = json.loads(_json)
        stuff = [Item.from_json(x) for x in _json]
        inv = Inventory(stuff)
