import os
import json

from app.logger import setup_logger, INFO, DEBUG
from app import Client


path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# Load config from JSON file
try:
    with open("config.json", "r") as f:
        config = json.load(f)
        if "username" in config and "p2p_retry_time" in config and "audio_chunk" in config and "server_address" in config and "server_port" in config and "auto_lan" in config and "debug" in config:
            pass
        else:
            raise FileNotFoundError("Missing required keys in config.json")
        
except FileNotFoundError:
    username = input("Enter your username: ")
    p2p_retry_time = 0.1
    with open("config.json", "w") as f:
        config = {
            "username": username,
            "p2p_retry_time": p2p_retry_time,
            "audio_chunk": 2048,
            "server_address": "vc.itzowo.net",
            "server_port": 80,
            "auto_lan": True,
            "debug": False
        }
        json.dump(config, f, indent=4)

# Setup logger
if config["debug"]:
    log_level = DEBUG
else:
    log_level = INFO
log = setup_logger(__name__, log_level)
log.info("Starting client")


username = config["username"]
p2p_retry_time = config["p2p_retry_time"]

log.info(f"Username: {username}")


def main():
    client = Client(config)
    channel_id = input("Enter channel ID: ")
    try:
        channel_id = int(channel_id)
    except ValueError:
        log.error("Invalid channel ID. Please enter a number.")
        return False

    return client.run(channel_id)


if __name__ == "__main__":
    run = True
    while run:
        try:
            run = main()
        except KeyboardInterrupt:
            log.info("\nCtrl + C detected")
            run = False
        except Exception:
            log.exception("Error in main loop")
            run = False
    input("Press Enter to exit...")