from gpiozero import Device, LED, OutputDevice
from gpiozero.pins.mock import MockFactory
import json
from os import getenv
from tiktoken import Encoding
from typing import Any, Dict, List


def ensure_token_limit(
    encoding: Encoding, messages: List[Dict[str, Any]], max: int = 512
):
    def get_token_count(m: Dict[str, Any]) -> int:
        return (
            len(encoding.encode(m["content"]))
            if "content" in m and m["content"] is not None
            else 0
        )

    total = sum(get_token_count(m) for m in messages)

    while total > max or messages[0]["role"] != "user":
        message = messages.pop(0)
        total -= get_token_count(message)


def get_appliance_status(appliances: List[Dict[str, Any]], args: Dict[str, Any]) -> str:
    y = next((x for x in appliances if x["pin"] == args["pin"]), None)
    if y is None:
        return "Could not find any such appliance."

    return (
        f"{y['name']} is currently turned on."
        if y["device"].value
        else f"{y['name']} is currently turned off."
    )


def toggle_appliance_on_off(
    appliances: List[Dict[str, Any]], args: Dict[str, Any]
) -> str:
    y = next((x for x in appliances if x["pin"] == args["pin"]), None)
    if y is None:
        return "Could not find any such appliance."

    if args["state"] == "on":
        y["device"].on()

        return f"Turned on the {y['name']}."
    else:
        y["device"].off()

        return f"Turned off the {y['name']}."


def read_devices_list(path: str) -> List[Dict[str, Any]]:
    f = open(path)
    devices = json.load(f)
    f.close()

    if getenv("MOCK_GPIO") is not None:
        Device.pin_factory = MockFactory()

    def setup_gpio_device(x: Dict[str, Any]):
        device = (
            OutputDevice(x["pin"], active_high=True, initial_value=False)
            if x["type"] == "relay"
            else LED(x["pin"])
        )
        x.update({"device": device})

        return x

    devices = [setup_gpio_device(x) for x in devices]

    return devices
