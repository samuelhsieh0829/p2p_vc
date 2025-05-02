from flask import Flask, request, jsonify, render_template, redirect
from channel import Channel
import time
import random
from logger import setup_logger, INFO
import threading
import socket
import struct

log = setup_logger(__name__, INFO)

app = Flask(__name__)

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind(("0.0.0.0", 0))
udp_socket.settimeout(2)  # Set a timeout for the socket to avoid blocking
udp_socket_port = udp_socket.getsockname()[1]
log.info(f"Join channel UDP listener started on port {udp_socket_port}")

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

@app.route("/api/channel/<int:channel_id>/members", methods=["GET"])
def get_channel_members(channel_id):
    for channel in channels:
        if channel_id in channel:
            members = channel[channel_id].members.copy()
            temp = []
            for member in members:
                temp.append(member.__dict__)
            return jsonify(temp), 200
    return "Channel not found", 404

# Channel index page
@app.route("/channels", methods=["GET"])
def list_channels():
    return render_template("channels.html")

# Create channel
@app.route("/api/channels/create", methods=["POST"])
def create_channel():
    if request.method == "POST":
        name = request.json.get["name"]
        description = request.json.get["description"]
        author = request.json.get["author"]
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

# Delete channel
@app.route("/api/channels/delete/", methods=["POST"])
def delete_channel(channel_id):
    global channels
    channel_id = request.json.get("channel_id")
    if not channel_id:
        return "Missing parameters", 400
    for channel in channels:
        if channel_id in channel:
            channels.remove(channel)
            return jsonify({"status": "ok"}), 200
    return jsonify({"status": "Channel not found"}), 404

@app.route("/channels/delete/<int:channel_id>", methods=["GET"])
def delete_channel_by_get(channel_id):
    global channels
    for channel in channels:
        if channel_id in channel:
            channels.remove(channel)
            return redirect("/channels")
    return "Channel not found", 404

# Join channel
# @app.route("/channel/<channel_id>/join", methods=["GET"])
# def join_channel(channel_id):
#     name = request.args.get("name")
#     ip = request.args.get("ip")
#     port = request.args.get("port")
#     log.info(f"Joining channel {channel_id} with name {name}, ip {ip}, port {port}")
#     if not name or not ip or not port:
#         return "Missing parameters", 400
#     for channel in channels:
#         if int(channel_id) in channel:
#             status = channel[int(channel_id)].add_member(name, ip, port)
#             if status is None:
#                 return redirect("/channels")
#             else:
#                 return status, 400
#     return "Channel not found", 404

# Channel join leave API
@app.route("/api/channel/<channel_id>/join", methods=["POST"])
def join_channel_api(channel_id):
    for channel in channels:
        if int(channel_id) in channel:
            # Send the UDP port back to the client
            return jsonify({"port": udp_socket_port}), 200
    return jsonify({"status": "Channel not found"}), 404
    # global channels
    # name = request.json.get("name")
    # port = request.json.get("port")
    # ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    # log.info(f"Joining channel {channel_id} with name {name}, ip {ip}, port {port}")
    # if not name or not ip or not port:
    #     return "Missing parameters", 400
    # for channel in channels:
    #     if int(channel_id) in channel:
    #         status = channel[int(channel_id)].add_member(name, ip, port)
    #         if status is None:
    #             channel_members = channel[int(channel_id)].members.copy()
    #             temp = []
    #             for member in channel_members:
    #                 if member.name != name:
    #                     temp.append(member.__dict__)
    #             return jsonify(temp), 200
    #         else:
    #             return jsonify({"status": status}), 400
    # return jsonify({"status": "Channel not found"}), 404

def nat_listener():
    try:
        while not running.is_set():
            try:
                data, addr = udp_socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                log.error("Socket error, exiting NAT listener")
                break
            log.info(f"Received Join request from {addr} with data: {data}")
            header = data[:8]
            channel_id, username_length = struct.unpack(">II", header)
            name = data[8:8+username_length].decode('utf-8')
            ip, port = addr
            log.info(f"Received Join request from {name} for channel {channel_id} with IP {ip} and port {port}")
            for channel in channels:
                if int(channel_id) in channel:
                    status = channel[int(channel_id)].add_member(name, ip, port)
                    if status is None:
                        udp_socket.sendto(b"hello", addr)
                        break
                    else:
                        log.error(f"Failed to add member {name} to channel {channel_id}: {status}")
                        udp_socket.sendto(b"Failed to add member", addr)
                        break
            udp_socket.sendto(b"Channel not found", addr)
    except KeyboardInterrupt:
        print("\nCtrl + C detected")
    except:
        log.exception("Error in NAT listener")
    finally:
        udp_socket.close()
        log.info("NAT listener stopped")

@app.route("/api/channel/<channel_id>/leave", methods=["POST"])
def leave_channel_api(channel_id):
    name = request.json.get("name")
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    log.info(f"{name} is leaving channel {channel_id} with ip {ip}")
    if not name or not ip:
        return "Missing parameters", 400
    for channel in channels:
        if int(channel_id) in channel:
            status = channel[int(channel_id)].remove_member(name)
            if status is None:
                return jsonify({"status": "ok"}), 200
            else:
                return jsonify({"status": status}), 400
    
    return jsonify({"status": "Channel not found"}), 404
            
if __name__ == "__main__":
    try:
        running = threading.Event()
        # Start the NAT listener in a separate thread
        nat_thread = threading.Thread(target=nat_listener, daemon=True)
        nat_thread.start()
        
        # Start the Flask server
        app.run(host="0.0.0.0", port=80, debug=True)
    finally:
        running.set()
        nat_thread.join()
