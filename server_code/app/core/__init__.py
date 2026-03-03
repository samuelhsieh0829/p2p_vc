import struct
import socket
import threading

from app.utils.channel import Channel, LAN_Member
from app.utils.logger import setup_logger


log = setup_logger(__name__)

class Server:
    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("0.0.0.0", 0))
        self.udp_socket.settimeout(2)  # Set a timeout for the socket to avoid blocking
        self.udp_socket_port = self.udp_socket.getsockname()[1]
        log.info(f"Join channel UDP listener started on port {self.udp_socket_port}")

        self.channels:list[dict[int, Channel]] = []
        self.channels_lan:list[dict[int, list[LAN_Member]]] = [] # [{channel_id: [{name :str, ip: str, lan_ip :str, port: int}]}]
        
        self.running = None
        self.nat_thread = threading.Thread(target=self.nat_listener, daemon=True)

    def nat_listener(self):
        try:
            while not self.running.is_set():
                try:
                    data, addr = self.udp_socket.recvfrom(1024)
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
                for channel in self.channels:
                    if int(channel_id) in channel:
                        status = channel[int(channel_id)].add_member(name, ip, port)
                        if status is None:
                            self.udp_socket.sendto(b"hello", addr)
                            break
                        else:
                            log.error(f"Failed to add member {name} to channel {channel_id}: {status}")
                            self.udp_socket.sendto(b"Failed to add member", addr)
                            break
                self.udp_socket.sendto(b"Channel not found", addr)
        except KeyboardInterrupt:
            print("\nCtrl + C detected")
        except:
            log.exception("Error in NAT listener")
        finally:
            self.udp_socket.close()
            log.info("NAT listener stopped")

    def set_event(self, event:threading.Event):
        self.running = event

    def run(self):
        if self.running is None:
            log.critical("Running event has not set")
        self.nat_thread.start()

server = Server()