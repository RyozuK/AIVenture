import json
import re

import openai
import Config
import World

openai.api_key = Config.open_ai_key


class Generator:
    pat_name = r'\"name\":.*?\"(?P<name>[A-Za-z0-9 ]*?)\",'
    pat_desc = r'\"description\": ?\"(?P<description>.*?)\"'
    pat_exit = r'\"exits\": ?(?P<exits>\[.*?\])'
    pattern = r"\{\"name\":.*?\"(?P<name>[A-Za-z0-9 ]*?)\",.*?\"description\": ?\"(?P<description>.*?)\".*?\"exits\": ?(?P<exits>\[.*?\])"
    preamble = """You are a text adventure game room generator.
Valid directions are north, south, east, west, up, down
There will always be at least two exits.
You will generate a new room based on the adventure so far.
You will give the new room in the form of json.
You will ONLY respond with JSON.
You will always generate a room, even if it doesn't seem logical.
Your job is to generate new rooms.  The following is an example of a room in json format:
{"name": "hallway", "description": "A long hallway full of detritus.", "exits": ["east", "west"]}
"""

    @classmethod
    def new_room(cls, history):
        # First, we build the message log
        log = [{"role": "user", "content": cls.preamble}]
        log += [{"role": "user", "content": msg} for msg in history]
        log.append({"role": "user", "content": "Remember, I need this data in JSON format"})

        for i in range(3):

            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=log)
            data = response['choices'][0]['message']['content']

            data = data.replace("'", '"')
            data = data.replace(r"\n", '\n')

            result = re.search(cls.pattern, data, re.MULTILINE | re.DOTALL)
            if result is not None:
                return World.Room(name=result.group(1), description=result.group(2),
                                  exits=json.loads(result.group(3)))
            name = re.search(cls.pat_name, data, re.MULTILINE | re.DOTALL)
            desc = re.search(cls.pat_desc, data, re.MULTILINE | re.DOTALL)
            exits = re.search(cls.pat_exit, data, re.MULTILINE | re.DOTALL)
            if name is not None and desc is not None and exits is not None:
                print("Used method 2")
                return World.Room(name=name.group(1), description=desc.group(1),
                                  exits=exits.group(1))

            print(f"Bad data from OpenAI: {data}")

        return None

