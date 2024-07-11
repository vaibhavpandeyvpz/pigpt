from dotenv import load_dotenv
from flask import Flask, request
import json
from openai import OpenAI
from os import getenv
from slack_sdk import WebClient
from tiktoken import encoding_for_model
from typing import Any, Dict, List

from pigpt.utililties import (
    ensure_token_limit,
    get_appliance_status,
    read_devices_list,
    toggle_appliance_on_off,
)

load_dotenv()

OPENAI_API_KEY = getenv("OPENAI_API_KEY")
OPENAI_ORGANIZATION_ID = getenv("OPENAI_ORGANIZATION_ID")
OPENAI_MODEL = getenv("OPENAI_MODEL")

SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN")

MAX_INPUT_TOKENS = 8 * 1024

app = Flask(__name__)

gpt = OpenAI(
    api_key=OPENAI_API_KEY,
    organization=OPENAI_ORGANIZATION_ID,
)

slack = WebClient(token=SLACK_BOT_TOKEN)

appliances = read_devices_list("devices.json")

history: Dict[str, List[Dict[str, Any]]] = {}

encoding = encoding_for_model(OPENAI_MODEL)

prefix = [
    {
        "role": "system",
        "content": """
        You are a bot named PiGPT designed to help control electrical appliances at home such as toggle them on/off, change fan speed etc. by interacting with the appliances connected to certain GPIO pins.
        If user's prompt is not related to your defined capabilities, just let them know you can only do certain stuff.
        """,
    },
    {
        "role": "system",
        "content": "Information on the connected appliances are as follows: "
        + json.dumps(
            list(
                map(
                    lambda x: {key: val for key, val in x.items() if key != "device"},
                    appliances,
                )
            )
        ),
    },
]

cache: Dict[str, Any] = {}


@app.get("/")
def index():
    return "OK"


@app.post("/slack/events")
def events():
    type = request.json["type"]
    if type == "url_verification":
        return request.json["challenge"]

    if type == "event_callback":
        event = request.json["event"]
        event_ts = event["event_ts"]
        if cache.get(event_ts):
            return "OK"

        cache[event_ts] = True

        bot_id = event.get("bot_id")
        if event["type"] == "message" and bot_id is None:
            channel = event["channel"]
            text = event["text"]

            messages = history.get(channel, []).copy()
            messages.append({"role": "user", "content": text})

            while True:
                ensure_token_limit(encoding, messages, MAX_INPUT_TOKENS)

                completion = gpt.chat.completions.create(
                    messages=prefix + messages,
                    model=OPENAI_MODEL,
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "get_appliance_status",
                                "description": "Tells whether a connected appliance on a GPIO pin is turned on or off.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "pin": {
                                            "type": "integer",
                                            "description": "GPIO pin no. of the connected appliance.",
                                        },
                                    },
                                    "required": ["pin"],
                                },
                            },
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "toggle_appliance_on_off",
                                "description": "Turns on/off a connected appliance on a GPIO pin.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "pin": {
                                            "type": "integer",
                                            "description": "GPIO pin no. of the connected appliance.",
                                        },
                                        "state": {
                                            "type": "string",
                                            "enum": ["on", "off"],
                                        },
                                    },
                                    "required": ["pin", "state"],
                                },
                            },
                        },
                    ],
                )

                reply = completion.choices[0].message
                messages.append(reply.to_dict())

                if reply.tool_calls is None:
                    _ = slack.chat_postMessage(channel=channel, text=reply.content)
                    history[channel] = messages

                    break

                for tc in reply.tool_calls:
                    args = json.loads(tc.function.arguments)
                    if tc.function.name == "get_appliance_status":
                        result = get_appliance_status(appliances, args)

                    if tc.function.name == "toggle_appliance_on_off":
                        args = json.loads(tc.function.arguments)
                        result = toggle_appliance_on_off(appliances, args)

                    messages.append(
                        {
                            "tool_call_id": tc.id,
                            "name": tc.function.name,
                            "role": "tool",
                            "content": result,
                        }
                    )

    return "OK"
