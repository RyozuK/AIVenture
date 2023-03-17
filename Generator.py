import json
import re

import openai
import Config
import World

openai.api_key = Config.open_ai_key


class Generator:
    pattern = r"\{\"name\": ?\"(?P<name>[A-Za-z0-9 ]*?)\", ?\"description\": ?\"(?P<description>.*?)\".*?\"exits\": ?(?P<exits>\[.*?\])"
    instance = None
    initialized = False
    preamble = """You are a text adventure game room generator.
Your job is to generate new rooms.  The following is an example of a room in json format:
Valid directions are north, south, east, west, up, down
There will always be at least two exits.
You will generate a new room based on the adventure so far.
Be sure to give the results in the form of json.
Example
{"name": "hallway", "description": "A long hallway full of detritus.", "exits": ["east", "west"]}
Here is the adventure so far:
"""

    #
    # def __init__(self):
    #     if not Generator.initialized:
    #         self.name = "hello"
    #         Generator.initialized = True
    #
    # def __new__(cls, *args, **kwargs):
    #     if cls.instance is None:
    #         cls.instance = super().__new__(cls)
    #     return cls.instance
    #
    @classmethod
    def new_room(cls, history):
        # First, we build the message log
        log = [{"role": "user", "content": cls.preamble}]
        log += [{"role": "user", "content": msg} for msg in history]

        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=log)
        data = response['choices'][0]['message']['content']
        # print(f"OpenAI responded with [{data}]")
        # print("------------------------------\n", "\n".join([str(x) for x in log]))

        data = data.replace("'", '"')

        """Fucking JSON"""

        result = re.search(cls.pattern, data, re.MULTILINE | re.DOTALL)
        if result is None:
            print (f"Bad data from OpenAI: {data}")
            return None

        return World.Room(name=result.group(1), description=result.group(2),
                          exits=json.loads(result.group(3)))

        # for line in data.split('\n'):
        #     try:
        #         data = json.loads(data)
        #         return World.Room(**data)
        #     except:
        #         # breakpoint()
        #         """Nothing"""
        # print(f"OpenAI gave back bad data: {data}")
        # breakpoint()


if __name__ == "__main__":
    this = Generator()
    this2 = Generator()
    this2.name = "Goodbye"
    print(this.name)
    this3 = Generator()
    print(this.name)
