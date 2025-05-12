import requests
import ipaddress
import struct

from app.object.socket_obj import UDPSocket
from app.logger import setup_logger, INFO, DEBUG
from app.const import *

class Fetch:
    def __init__(self, config, socket:UDPSocket=None):
        self.config = config
        self.username = config["username"]
        self.server_address = config["server_address"]
        self.debug = config["debug"]
        self.socket = socket
        self.session = requests.Session()
        self.local_channel_member_list = []
        self.connecting_list = []

        log_level = INFO if not config["debug"] else DEBUG
        self.log = setup_logger(__name__, log_level)

    def get_time(self):
        try:
            response = self.session.get(f"http://{self.server_address}/api/time")
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.log.error(f"Error connecting to server: {e}")
            return
        resp = response.json()["time"]
        self.log.debug(f"Response: {resp}")
        return resp

    def channel(self, channel_id:int):
        try:
            response = self.session.get(f"http://{self.server_address}/api/channel/{channel_id}")
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.log.error(f"Error connecting to server: {e}")
            return
        resp = response.json()
        self.log.debug(f"Response: {resp}")
        return resp

    def channel_user_list(self, channel_id:int):
        try:
            response = self.session.get(f"http://{self.server_address}/api/channel/{channel_id}/members")
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.log.error(f"Error connecting to server: {e}")
            return
        resp = response.json()
        self.log.debug(f"Response: {resp}")
        return resp

    def is_same_lan(self, ip1, ip2):
        try:
            net1 = ipaddress.IPv4Address(ip1)
            net2 = ipaddress.IPv4Address(ip2)
            # 比對前兩段或前三段的 IP（視情況而定）
            return str(net1).split('.')[:3] == str(net2).split('.')[:3]
        except:
            return False

    def lan_ip(self, self_ip:str, channel_id:int):
        try:
            resp = self.session.post(f"http://{self.server_address}/api/channel/{channel_id}/lan_ip", json={"name": self.username, "ip": self_ip, "lan_ip": self.socket.LOCAL_IP, "port": self.socket.PORT})
        except requests.exceptions.RequestException as e:
            self.log.error(f"Error connecting to server: {e}")
            return None
        finally:
            self.log.debug(f"LAN IP sent: {self_ip}")
            return resp

    def join_channel(self, channel_id:int):
        if self.socket is None:
            self.log.error("Socket is not initialized")
            return None
        
        response = self.session.post(f"http://{self.server_address}/api/channel/{channel_id}/join")
        if response.status_code != 200:
            self.log.error(f"Error joining channel: {response.status_code} {response.json()}")
            return None
        resp = response.json()
        port = int(resp["port"])
        self.log.debug(f"Port: {port}")
        try:
            self.socket.set_timeout(2.0)
            while True:
                username_bytes = self.username.encode('utf-8')
                username_length = len(username_bytes)
                packet = struct.pack(">II", channel_id, username_length) + username_bytes
                self.socket.send(packet, (self.server_address, port))
                self.log.debug(f"Join channel packet sent to {self.server_address}:{port}")
                try:
                    data = self.socket.get(1024)

                    if data.data == b'':
                        self.log.debug("No data received")
                        continue

                    # if addr[0] != self.server_address or addr[1] != port:
                    #     self.log.warning(f"Received packet from unexpected address: {addr}")
                    #     continue
                    if data.data == send_data:
                        self.log.info(f"Successfully joined channel {channel_id} as {self.username}")
                        self.socket.set_timeout(0.1)  # Reset timeout for socket operations
                        return True
                    else:
                        self.log.error(f"Join channel failed, received: {data.data.decode()}")
                        return False
                except OSError:
                    self.log.warning("Received wrong packet")
                    continue
        except:
            self.log.exception("Error sending join channel packet")

    def leave_channel(self, channel_id:int):
        response = self.session.post(f"http://{self.server_address}/api/channel/{channel_id}/leave", json={"name": self.username})
        if response.status_code != 200:
            self.log.error(f"Error leaving channel: {response.status_code} {response.json()}")

            return None
        resp = response.json()
        return resp