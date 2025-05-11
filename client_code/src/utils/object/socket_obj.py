import socket
import time
import threading

from utils.logger import setup_logger, INFO

class Data:
    def __init__(self, data=b'', ip=None, port=None, addr=None):
        self.data = data
        self.ip = ip
        self.port = port
        self.addr = addr
        self.timestamp = time.time()

class UDPSocket:
    def __init__(self, stop_event:threading.Event=None):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("0.0.0.0", 0))
        self.s.settimeout(0.1)  # Set timeout for socket operations
        self.PORT = self.s.getsockname()[1]
        self.LOCAL_IP = self.get_local_ip()
        self.stop_event = stop_event
        self.log = setup_logger(__name__, INFO)

    def set_timeout(self, timeout: float):
        self.s.settimeout(timeout)

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 不需實際送資料，只是觸發系統查詢路由表
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"  # fallback
        finally:
            s.close()
            return local_ip

    def send(self, data, addr):
        if not self.stop_event.is_set():
            self.s.sendto(data, addr)
        else:
            raise OSError("Socket Closed")

    def get(self, buffer=32768):
        while not self.stop_event.is_set():
            try:
                data, addr = self.s.recvfrom(buffer)
                return Data(data, addr[0], addr[1], addr)
            except socket.timeout:
                return Data(b'', None, None, None)
            except Exception:
                return Data(b'', None, None, None)
        self.log.warning("Main thread stopped")
        return Data(b'', None, None, None)

    def stop(self):
        self.s.close()
        self.log.info("Socket closed")
