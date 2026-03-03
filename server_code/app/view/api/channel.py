from flask import Blueprint, jsonify, request

from app.core import server
from app.utils.logger import setup_logger
from app.utils.channel import Channel, LAN_Member

log = setup_logger(__name__)

channel_api = Blueprint('channel', __name__, url_prefix="/api/channel")

@channel_api.route("/<int:channel_id>", methods=["GET"])
def get_single_channel(channel_id):
    for channel in server.channels:
        if channel_id in channel:
            channel = channel[channel_id].__dict__.copy()
            channel["members"] = [member.get_user() for member in channel["members"]]
            return jsonify({"channel": channel})
    return "Channel not found", 404

@channel_api.route("/<int:channel_id>/members", methods=["GET"])
def get_channel_members(channel_id):
    for channel in server.channels:
        if channel_id in channel:
            members = channel[channel_id].members.copy()
            temp = []
            for member in members:
                temp.append(member.__dict__)
            return jsonify(temp), 200
    return "Channel not found", 404

# Channel join leave API
@channel_api.route("/<channel_id>/join", methods=["POST"])
def join_channel_api(channel_id):
    for channel in server.channels:
        if int(channel_id) in channel:
            # Send the UDP port back to the client
            return jsonify({"port": server.udp_socket_port}), 200
    return jsonify({"status": "Channel not found"}), 404

@channel_api.route("/<channel_id>/leave", methods=["POST"])
def leave_channel_api(channel_id):
    name = request.json.get("name")
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    log.info(f"{name} is leaving channel {channel_id} with ip {ip}")
    if not name or not ip:
        return "Missing parameters", 400
    for channel in server.channels:
        if int(channel_id) in channel:
            status = channel[int(channel_id)].remove_member(name)
            if status is None:
                # Remove the member from channels_lan if they exist there
                for channel_lan in server.channels_lan:
                    if int(channel_id) in channel_lan:
                        for member in channel_lan[int(channel_id)]:
                            if member.name == name:
                                channel_lan[int(channel_id)].remove(member)
                                break
                return jsonify({"status": "ok"}), 200
            else:
                return jsonify({"status": status}), 400
    
    return jsonify({"status": "Channel not found"}), 404

@channel_api.route("/<channel_id>/lan_ip", methods=["POST"])
def connect_lan(channel_id):
    name = request.json.get("name")
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    lan_ip = request.json.get("lan_ip")
    port = request.json.get("port")
    if not name or not lan_ip or not port:
        return "Missing parameters", 400
    
    channel_id = int(channel_id)
    # Check if the channel exists
    for channel in server.channels:
        if channel_id in channel:
            # Check if the channel already exists in channels_lan
            for channel_lan in server.channels_lan:
                if channel_id in channel_lan:
                    # Check if the member already exists in the channel
                    for member in channel_lan[channel_id]:
                        if member.name == name:
                            temp = [member.__dict__ for member in channel_lan[channel_id]]
                            return jsonify(temp), 200
                    channel_lan[channel_id].append(LAN_Member(name, ip, lan_ip, port))
                    temp = [member.__dict__ for member in channel_lan[channel_id]]
                    return jsonify(temp), 200
            # If the channel doesn't exist in channels_lan, create it
            channel_lan = {channel_id: [LAN_Member(name, ip, lan_ip, port)]}
            server.channels_lan.append(channel_lan)
            temp = [member.__dict__ for member in channel_lan[channel_id]]
            return jsonify(temp), 200
    # If the channel doesn't exist in channels, return an error
    return jsonify({"status": "Channel not found"}), 404