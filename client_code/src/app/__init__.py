import threading

from app.object.socket_obj import UDPSocket
from app.receive_audio import ReceiveAudio
from app.send_audio import SendAudio
from app.p2p import P2PManager
from app.fetch import Fetch
from app.const import *
from app.logger import setup_logger, INFO, DEBUG

class Client:
    def __init__(self, config:dict):
        self.config = config
        self.username = config["username"]
        self.p2p_retry_time = config["p2p_retry_time"]
        self.audio_chunk = config["audio_chunk"]
        self.server_address = config["server_address"]
        self.debug = config["debug"]

        self.running = threading.Event()

        self.socket = UDPSocket(self.running)
        self.server = Fetch(config, self.socket)
        self.local_channel_member_list = []
        self.connecting_list = []

        
        
        log_level = INFO if not config["debug"] else DEBUG
        self.log = setup_logger(__name__, log_level)
        self.log.debug(f"Client initialized with config: {config}")

    def run(self, channel_id=None):
        try:
            threads_started = False
            # Join channel
            if channel_id is None:
                channel_id = input("Enter channel ID: ")
                try:
                    channel_id = int(channel_id)
                except ValueError:
                    self.log.error("Invalid channel ID. Please enter a number.")
                    return
            
            temp = self.server.join_channel(channel_id)
            if temp is None:
                self.log.error("Failed to join channel")
                temp = self.server.leave_channel(channel_id)
                return
            
            channel_data = self.server.channel(channel_id)
    
            if channel_data is None:
                self.log.error("Channel not found")
                return
            
            for member in self.server.channel_user_list(channel_id):
                if member["name"] == self.username:
                    self_ip = member["ip"]
                    self.log.debug(f"Self IP: {self_ip}")
                    break
            
            threads_started = True
            self.send_audio = SendAudio(self.config, self.socket, self.running, self.connecting_list)
            send_audio_thread = threading.Thread(target=self.send_audio.start, daemon=True)
            send_audio_thread.start()

            self.receive_audio = ReceiveAudio(self.config, self.socket, self.running, self.connecting_list)
            receive_audio_thread = threading.Thread(target=self.receive_audio.start, daemon=True)
            receive_audio_thread.start()
            
            self.p2p_manager = P2PManager(self.config, self.socket, self.running, self.connecting_list)
            self.p2p_manager.local_channel_member_list = self.local_channel_member_list
            p2p_manager_thread = threading.Thread(target=self.p2p_manager.update_member, args=(channel_id,), daemon=True)
            p2p_manager_thread.start()

            while not self.running.is_set():
                cmd = input("Enter command (exit): ")
                if cmd == "exit":
                    self.log.info("Exiting...")
                    break
                else:
                    self.log.error("Unknown command")
        except KeyboardInterrupt:
            self.log.info("\nCtrl + C detected")
        except Exception:
            self.log.exception("Error in main loop")
        finally:
            temp = self.server.leave_channel(channel_id)
            self.running.set()
            if threads_started:
                send_audio_thread.join()
                receive_audio_thread.join()
                p2p_manager_thread.join()
            self.log.info("Stopped all threads")
            self.socket.stop()
            return False