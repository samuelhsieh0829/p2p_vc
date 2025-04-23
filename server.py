from flask import Flask, request, jsonify, render_template, redirect
from channel import Channel
import time
import random
from logger import setup_logger, INFO

log = setup_logger(__name__, INFO)

app = Flask(__name__)

channels:list[dict[int, Channel]] = []

@app.route("/")
def index():
    return render_template("index.html")

# Get server time
@app.route("/api/time")
def get_time():
    current_time = time.time()
    return jsonify({"time": current_time})

# Get channel list
@app.route("/api/channels", methods=["GET", "POST"])
def get_channels():
    channel_list = []
    for channel in channels:
        for channel_id in channel:
            temp = channel[channel_id].__dict__
            channel_list.append({"id": channel_id, "name": temp["name"], "author": temp["author"]})
    return jsonify({"channels": channel_list})

@app.route("/api/channel/<int:channel_id>", methods=["GET"])
def get_single_channel(channel_id):
    for channel in channels:
        if channel_id in channel:
            channel = channel[channel_id].__dict__.copy()
            channel["members"] = [member.get_user() for member in channel["members"]]
            return jsonify({"channel": channel})
    return "Channel not found", 404

# Channel index page
@app.route("/channels", methods=["GET"])
def list_channels():
    return render_template("channels.html")

# Create channel
@app.route("/api/channels/create", methods=["POST"])
def create_channel():
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        author = request.form["author"]
        if not name or not description or not author:
            return "Missing parameters", 400
        while True:
            channel_id = random.randint(10000, 99999)
            if channel_id not in channels:
                break
        channel = Channel(channel_id, name, description, author)
        channels.append({channel_id: channel})
        return "ok", 200

@app.route("/channels/create", methods=["GET"])
def create_channel_by_get():
    if request.method == "GET":
        name = request.args.get("name")
        description = request.args.get("description")
        author = request.args.get("author")
        if not name or not description or not author:
            return "Missing parameters", 400
        while True:
            channel_id = random.randint(10000, 99999)
            if channel_id not in channels:
                break
        channel = Channel(channel_id, name, description, author)
        channels.append({channel_id: channel})
        return redirect("/channels")
    
@app.route("/channel/<channel_id>/join", methods=["GET"])
def join_channel(channel_id):
    name = request.args.get("name")
    ip = request.args.get("ip")
    port = request.args.get("port")
    log.info(f"Joining channel {channel_id} with name {name}, ip {ip}, port {port}")
    if not name or not ip or not port:
        return "Missing parameters", 400
    for channel in channels:
        if int(channel_id) in channel:
            status = channel[int(channel_id)].add_member(name, ip, port)
            if status is None:
                return redirect("/channels")
            else:
                return status, 400
    return "Channel not found", 404

app.run(host="0.0.0.0", port=5000, debug=True)
