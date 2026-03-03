import time
import struct
import numpy as np
import threading
from collections import deque

from app.logger import setup_logger, INFO, DEBUG
from app.object.audio_obj import AudioIn
from app.object.socket_obj import UDPSocket
from app.const import *

log = setup_logger(__name__)

class SendAudio:
    def __init__(self, config, socket:UDPSocket, stop_event:threading.Event, connecting_list):
        self.config = config
        self.username = config["username"]
        self.s = socket
        self.chunk = config["audio_chunk"]
        self.stop_event = stop_event
        self.audio_queue = deque(maxlen=50)
        self.connecting_list = connecting_list

    def audio_get_loop(self):
        try:
            log.debug("Start audio input loop")
            with AudioIn(self.chunk) as input_audio:
                while not self.stop_event.is_set():
                    audio = input_audio.get()
                    if audio:
                        self.audio_queue.append(audio)
                    else:
                        log.debug("No audio data received")
        except KeyboardInterrupt:
            log.info("\nCtrl + C detected")
        finally:
            log.info("Stopped audio input loop")
    
    def start(self):
        try:
            log.debug("Start sending data")
            audioin_thread = threading.Thread(target=self.audio_get_loop, daemon=True)
            audioin_thread.start()
            while not self.stop_event.is_set():
                try:
                    audio = self.audio_queue.popleft()
                except IndexError:
                    continue
                # Add timestamop
                timestamp = time.time()
                timestamp_bytes = struct.pack(">d", timestamp)
                data = timestamp_bytes + audio
                for member in self.connecting_list:
                    if member["name"] == self.username:
                        continue
                    audio_out_target_location = (member["ip"], member["port"])
                    self.s.send(data, audio_out_target_location)

        except KeyboardInterrupt:
            log.info("\nCtrl + C detected")
        finally:
            log.info("Stopped sending audio")
            audioin_thread.join()