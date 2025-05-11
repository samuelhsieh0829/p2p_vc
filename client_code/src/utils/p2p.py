import time
import threading

from utils.fetch import Fetch
from utils.const import *
from utils.logger import setup_logger, INFO, DEBUG
from utils.object.socket_obj import UDPSocket

class P2PManager:
    def __init__(self, config, socket:UDPSocket, stop_event:threading.Event, connecting_list:list):
        self.config = config
        self.username = config["username"]
        self.server_address = config["server_address"]
        self.debug = config["debug"]
        self.p2p_retry_time = config["p2p_retry_time"]
        self.auto_lan = config["auto_lan"]
        self.socket = socket
        self.stop_event = stop_event
        self.server = Fetch(config, self.socket)
        self.run = True
        self.local_channel_member_list = []
        self.connecting_list = connecting_list

        log_level = INFO if not config["debug"] else DEBUG
        self.log = setup_logger(__name__, log_level)

    def update_member(self, channel_id:int):
        for member in self.server.channel_user_list(channel_id):
            if member["name"] == self.username:
                self_ip = member["ip"]
                self.log.debug(f"Self IP: {self_ip}")
                break

        while not self.stop_event.is_set():
            data = self.server.channel_user_list(channel_id)
            if data is None:
                self.log.error("Failed to fetch channel user list")
                time.sleep(2)
                continue

            members = data.copy()
            if members == self.local_channel_member_list:
                time.sleep(2)
                continue
            else:
                # 成員增加
                if len(members) > len(self.local_channel_member_list):
                    for member in members:
                        if member not in self.local_channel_member_list:

                            self.log.info(f"New member: {member['name']}")

                            # Check if the member is in the same LAN
                            found = False
                            if self.server.is_same_lan(member["ip"], self_ip) and (member["name"] != self.username) and self.auto_lan: # Disable Lan Feature
                                self.log.info(f"Same LAN: {member['name']} ({member['ip']}:{member['port']})")
                                resp = self.server.lan_ip(self_ip, channel_id)
                                if resp.status_code != 200:
                                    if resp.status_code == 500:
                                        self.log.error("Server error")
                                        time.sleep(2)
                                        continue
                                    self.log.error(f"Error sending LAN IP: {resp.status_code} {resp.json()}")
                                    continue

                                # Check if the member in the same LAN already POST their IP
                                for lan_member in resp.json():
                                    if lan_member["name"] == member["name"]:
                                        self.log.info(f"New member: {lan_member['name']} ({lan_member['lan_ip']}:{lan_member['port']})")
                                        member_info = {
                                            "name": lan_member["name"],
                                            "ip": lan_member["lan_ip"],
                                            "port": lan_member["port"]
                                        }
                                        self.local_channel_member_list.append(member_info)
                                        self.socket.send(send_data, (lan_member["lan_ip"], lan_member["port"]))
                                        new_p2p_thread = threading.Thread(target=self.start_p2p, args=(member_info,))
                                        new_p2p_thread.start()
                                        found = True

                                # Wait for the member to POST their IP
                                count = 0
                                while not found:
                                    count += 1
                                    resp2 = self.server.lan_ip(self_ip, channel_id)
                                    if resp2.json() == resp.json():
                                        self.log.info("Waiting for LAN IP...")
                                        pass
                                    else:
                                        self.log.info("LAN IP found")
                                        for lan_member in resp2.json():
                                            if lan_member["name"] == member["name"]:
                                                self.log.info(f"New member: {lan_member['name']} ({lan_member['lan_ip']}:{lan_member['port']})")
                                                member_info = {
                                                    "name": lan_member["name"],
                                                    "ip": lan_member["lan_ip"],
                                                    "port": lan_member["port"]
                                                }
                                                self.local_channel_member_list.append(member_info)
                                                self.socket.send(send_data, (lan_member["lan_ip"], lan_member["port"]))
                                                new_p2p_thread = threading.Thread(target=self.start_p2p, args=(member_info,))
                                                new_p2p_thread.start()
                                                found = True
                                    if found:
                                        break
                                    if count > 10:
                                        self.log.error("LAN IP not found")
                                        break
                                    time.sleep(1)
                            if not found:
                                self.local_channel_member_list.append(member)
                                if member["name"] == self.username:
                                    continue

                                self.socket.send(send_data, (member["ip"], member["port"]))
                                new_p2p_thread = threading.Thread(target=self.start_p2p, args=(member,))
                                new_p2p_thread.start()
                    self.log.debug(f"Updated member list: {self.local_channel_member_list}")
                # 成員減少
                elif len(members) < len(self.local_channel_member_list):
                    for member in self.local_channel_member_list.copy():
                        if member not in members:
                            if member["name"] == self.username:
                                self.stop_event.set()
                                continue
                            self.local_channel_member_list.remove(member)
                            for conn in self.connecting_list:
                                if conn["ip"] == member["ip"] and conn["port"] == member["port"]:
                                    self.connecting_list.remove(conn)
                                    self.log.info(f"Removed connection to {member['name']}")
                    self.log.debug(f"Updated member list: {self.local_channel_member_list}")
                # 成員不變
                else:
                    pass # 之後再說 幹


    def start_p2p(self, member:dict):
        self.log.debug(f"Starting P2P connection to {member['name']} ({member['ip']}:{member['port']})")
        location = (member["ip"], member["port"])

        while not self.stop_event.is_set():
            if member not in self.local_channel_member_list:
                self.log.info(f"Member {member['name']} left the channel")
                self.log.debug(f"Stopping P2P connection to {member['name']} ({member['ip']}:{member['port']})")
                break

            self.socket.send(send_data, location)
            try:
                data = self.socket.get(1024)
                if data.addr != location:
                    continue
                if data.data == send_data or data.data == confirm_data:
                    self.log.debug(f"{data.addr} NAT punch successful")
                    self.log.info(f"Connected to {member['name']}")
                    if member not in self.connecting_list:
                        self.connecting_list.append(member)
                    for i in range(10):
                        self.socket.send(confirm_data, location)
                    return
            except OSError:
                self.log.debug("Received wrong packet while P2P")
            finally:
                time.sleep(self.p2p_retry_time)