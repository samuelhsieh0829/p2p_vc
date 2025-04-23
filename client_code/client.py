import pyaudio
import socket
import struct
import sys
import time
import threading
import requests
from logger import setup_logger, INFO
from dotenv import load_dotenv
import os

# Setup logger
log = setup_logger(__name__, INFO)
log.info("Starting client")

# Load environment variables from .env file
load_dotenv()
username = "samuelhsieh"#os.getenv("USERNAME")
log.info(f"Username: {username}")

# Audio init
chunk = 1024
sample_format = pyaudio.paInt16
channels = 1
fs = 44100

input_audio = pyaudio.PyAudio()
audio_in = input_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, input=True)

output_audio = pyaudio.PyAudio()
audio_out = output_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, output=True)

# Socket init
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio_in_target_location = ("0.0.0.0", 5001)
s.bind(audio_in_target_location)
s.setblocking(False)

# Threading
stop_event = threading.Event()

# Main server
server_address = "192.168.1.109:5000"
# Get time offset
time_offset = 0
try:
    t0 = time.time()
    server_time = requests.get(f"http://{server_address}/api/time")
    t1 = time.time()
    rtt = t1 - t0
    server_time = server_time.json()["time"]
    time_offset = server_time + (rtt / 2) - time.time()
except requests.exceptions.RequestException as e:
    log.critical(f"Error connecting to server: {e}")
    sys.exit(1)

def receive_audio():
    global s
    try:
        log.info("Start receiving data")
        while not stop_event.is_set():
            data, addr = s.recvfrom(8192)

            # Get timestamp
            timestamp_byte = data[:8]
            timestamp = struct.unpack(">d", timestamp_byte)[0]
            audio_out.write(data[8:])

            # Output Ping
            t_delta = time.time() + time_offset - timestamp
            sys.stdout.write(f"\rPing: {t_delta*1000:.2f} ms")
            sys.stdout.flush()

            # Check for latency
            # if t_delta > 0.03:
            #     log.warning(f"\nWarning: High latency detected: {t_delta*1000:.2f} ms, rebinding socket")
            #     s.close()
            #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #     s.bind(audio_in_target_location)
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    finally:
        output_audio.terminate()
        s.close()
        log.info("Stopped")

def send_audio_data(ip, port):
    global s, audio_in
    audio_out_target_location = (ip, port)
    try:
        log.info("Start sending data")
        while not stop_event.is_set():
            audio = audio_in.read(chunk)
            # Add timestamop
            timestamp = time.time()
            timestamp_bytes = struct.pack(">d", timestamp)
            s.sendto(timestamp_bytes+audio, audio_out_target_location)
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    finally:
        s.close()
        input_audio.terminate()
        log.info("Stopped")

def start_p2p(ip, port):
    global s
    location = (ip, port)

    send_data = b"hello"
    # Punch NAT by sending packet to peer
    s.sendto(send_data, location)
    # Start receiving
    while True:
        log.info("Waiting for NAT punch response")
        data, addr = s.recvfrom(1024)
        if data == send_data:
            log.info("NAT punch successful")
            break
        time.sleep(2)
        
def main(channel_id:int=None):
    while True:
        if channel_id is None:
            channel_id = input("Enter channel ID: ")
            try:
                channel_id = int(channel_id)
            except ValueError:
                log.error("Invalid channel ID. Please enter a number.")
                break
        try:
            response = requests.post(f"http://{server_address}/api/channel/{channel_id}/join", json={"name": username, "port": 5001})
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            log.error(f"Error connecting to server: {e}")
            return
        resp = response.json()
        log.info(f"Response: {resp}")
        break
                                                                                                     

if __name__ == "__main__":
    
    main()
    # sender_thread = threading.Thread(target=send_audio_data)
    # receiver_thread = threading.Thread(target=receive_audio)

    # sender_thread.start()
    # receiver_thread.start()

    # try:
    #     while True:
    #         pass
    # except KeyboardInterrupt:
    #     log.info("\nCtrl + C detected")
    #     stop_event.set()
    # finally:
    #     log.info("Stopped")