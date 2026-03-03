import random

from flask import Blueprint, request, jsonify, redirect

from app.core import server
from app.utils.logger import setup_logger
from app.utils.channel import Channel, LAN_Member

log = setup_logger(__name__)

channels_api = Blueprint('channels', __name__, url_prefix="/api/channels")

# Get channel list
@channels_api.route("/", methods=["GET", "POST"])
def get_channels():
    channel_list = []
    for channel in server.channels:
        for channel_id in channel:
            temp = channel[channel_id].__dict__
            channel_list.append({"id": channel_id, "name": temp["name"], "author": temp["author"]})
    return jsonify({"channels": channel_list})

# Create channel
@channels_api.route("/create", methods=["POST"])
def create_channel():
    name = request.json.get("name")
    description = request.json.get("description")
    author = request.json.get("author")
    if not name or not description or not author:
        log.error("Missing parameters")
        return "Missing parameters", 400
    try:
        channel_id = int(request.json.get("channel_id"))
        if channel_id in server.channels:
            channel_id = None
        if channel_id < 10000 or channel_id > 99999:
            channel_id = None
    except:
        channel_id = None
    if not channel_id:
        while True:
            channel_id = random.randint(10000, 99999)
            if channel_id not in server.channels:
                break
    channel = Channel(channel_id, name, description, author)
    server.channels.append({channel_id: channel})
    return "ok", 200

@channels_api.route("/create", methods=["GET"])
def create_channel_by_get():
    if request.method == "GET":
        name = request.args.get("name")
        description = request.args.get("description")
        author = request.args.get("author")
        try:
            channel_id = int(request.args.get("channel_id"))
            if channel_id in server.channels:
                channel_id = None
            if channel_id < 10000 or channel_id > 99999:
                channel_id = None
        except:
            channel_id = None
        
        if not name or not description or not author:
            return "Missing parameters", 400
        if not channel_id:
            while True:
                channel_id = random.randint(10000, 99999)
                if channel_id not in server.channels:
                    break
        channel = Channel(channel_id, name, description, author)
        server.channels.append({channel_id: channel})
        return redirect("/channels")

# Delete channel
@channels_api.route("/delete/", methods=["POST"])
def delete_channel(channel_id):
    channel_id = request.json.get("channel_id")
    if not channel_id:
        return "Missing parameters", 400
    for channel in server.channels:
        if channel_id in channel:
            server.channels.remove(channel)
            return jsonify({"status": "ok"}), 200
    return jsonify({"status": "Channel not found"}), 404

@channels_api.route("/delete/<int:channel_id>", methods=["GET"])
def delete_channel_by_get(channel_id):
    for channel in server.channels:
        if channel_id in channel:
            server.channels.remove(channel)
            return redirect("/channels")
    return "Channel not found", 404