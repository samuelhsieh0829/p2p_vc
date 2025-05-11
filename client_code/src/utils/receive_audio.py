import time
from collections import defaultdict, deque
import struct
import sys
import numpy as np
import threading

from utils.logger import setup_logger, INFO, DEBUG
from utils.object.audio_obj import AudioOut
from utils.object.socket_obj import UDPSocket
from utils.fetch import Fetch
from utils.const import *

class ReceiveAudio:
    def __init__(self, config, socket:UDPSocket, stop_event:threading.Event, connecting_list):
        self.config = config
        self.s = socket
        self.chunk = config["audio_chunk"]
        self.play_queue = deque(maxlen=10)
        self.peer_pings = {}
        self.buffer_started = False
        self.connecting_list = connecting_list

        self.stop_event = stop_event

        log_level = INFO if not config["debug"] else DEBUG
        self.log = setup_logger(__name__, log_level)
        
        t0 = time.time()
        server_time = Fetch(config).get_time()
        t1 = time.time()
        rtt = t1 - t0
        t_server = float(server_time)
        self.time_offset = t_server + (rtt / 2) - t1

    def mix_audio(self, audio_chunks: list[bytes]) -> bytes:
        if not audio_chunks:
            return b''

        arrays = []
        for chunk in audio_chunks:
            # 確保 chunk 不是空的，而且大小是2的倍數
            if not chunk or len(chunk) % 2 != 0:
                continue
            try:
                arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                arrays.append(arr)
            except ValueError:
                self.log.exception(f"Error converting chunk to numpy array")
                continue
            
        if not arrays:
            return b''

        # 保護：強制對齊成相同最小長度，防止 np.sum 出錯
        min_len = min(len(arr) for arr in arrays)
        arrays = [arr[:min_len] for arr in arrays]

        mixed = np.sum(arrays, axis=0)
        mixed = np.clip(mixed, -32768, 32767)  # 防止爆音

        return mixed.astype(np.int16).tobytes()

    def start(self):
        buffer_window = 0.02  # seconds (adjust for latency/quality tradeoff)
        peer_buffers = defaultdict(list)

        try:
            self.log.debug("Start receiving data")
            last_playback = time.time()
            last_ping_display = time.time()
            playback_thread = threading.Thread(target=self.audio_playback_loop, daemon=True)
            playback_thread.start()
            while not self.stop_event.is_set():
                now = time.time()

                data = self.s.get()
                
                # Check if the data is valid
                if data.data == send_data:
                    self.log.debug(f"Received NAT punch response from {data.addr}")
                    self.s.send(confirm_data, data.addr)
                    continue
                
                if data.data == confirm_data:
                    self.log.debug(f"Received NAT punch confirmation from {data.addr}")
                    continue
                
                if data.data == b'':
                    continue

                if len(data.data) < 8:
                    self.log.warning("Received data is too short")
                    continue
                
                if data.addr not in self.connecting_list:
                    self.log.debug(f"Received data from unknown peer: {data.addr}")
                    continue

                # Get timestamp
                timestamp_byte = data.data[:8]
                timestamp = struct.unpack(">d", timestamp_byte)[0]
                audio_data = data[8:]

                # Save by peer address
                peer_buffers[data.addr].append(audio_data)

                # 計算,顯示Ping
                t_delta = (time.time() + self.time_offset) - timestamp
                # self.peer_pings[data.addr] = t_delta

                sys.stdout.write("\r")
                sys.stdout.write(f"Ping: {t_delta*1000:.2f} ms  ")
                sys.stdout.flush()

                # if now - last_ping_display >= 0.5:
                #     self.display_ping()
                #     last_ping_display = now

                # Every 50ms (or so), mix and play
                if now - last_playback >= buffer_window:
                    chunks = [chunk for chunks in peer_buffers.values() for chunk in chunks]
                    mixed = self.mix_audio(chunks)

                    if mixed:
                        self.play_queue.append(mixed)

                    peer_buffers.clear()
                    last_playback = now
                
                if not self.buffer_started and len(self.play_queue) >= 3:
                    self.buffer_started = True

        except KeyboardInterrupt:
            self.log.info("\nCtrl + C detected")
        # except OSError:
        #     pass
        finally:
            self.log.info("Audio receive stopped")
            playback_thread.join()

    def display_ping(self):
        sys.stdout.write("\r")
        for addr, ping in self.peer_pings.items():
            sys.stdout.write(f"Ping {addr}: {ping*1000:.2f} ms  ")
        sys.stdout.flush()
        self.peer_pings.clear()

    def audio_playback_loop(self):
        try:
            with AudioOut(self.chunk) as audio_out:
                self.log.debug("Audio playback started")
                while not self.stop_event.is_set():
                    if not self.play_queue:
                        continue

                    sound = self.play_queue.popleft()
                    audio_out.play(sound)

                    # Optional: Add a small delay to prevent CPU overload
                    time.sleep(0.001)
        except KeyboardInterrupt:
            self.log.info("\nCtrl + C detected")
        finally:
            self.log.info("Audio playback stopped")
