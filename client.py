import pyaudio
import socket
import struct
import sys
import time
import threading
import ntplib
import requests

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
IP = input("Enter the IP address of the target: ")
audio_out_target_location = (IP, 5001)

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
    print(f"Error connecting to server: {e}")
    sys.exit(1)

def receive_audio():
    global s
    try:
        print("Start receiving data")
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
            if t_delta > 0.03:
                print(f"\nWarning: High latency detected: {t_delta*1000:.2f} ms, rebinding socket")
                s.close()
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(audio_in_target_location)
    except KeyboardInterrupt:
        print("\nCtrl + C detected")
    finally:
        output_audio.terminate()
        s.close()
        print("Stopped")

def send_audio_data():
    global s, audio_in
    try:
        print("Start sending data")
        while not stop_event.is_set():
            audio = audio_in.read(chunk)
            # Add timestamop
            timestamp = time.time()
            timestamp_bytes = struct.pack(">d", timestamp)
            s.sendto(timestamp_bytes+audio, audio_out_target_location)
    except KeyboardInterrupt:
        print("\nCtrl + C detected")
    finally:
        s.close()
        input_audio.terminate()
        print("Stopped")

if __name__ == "__main__":
    
    sender_thread = threading.Thread(target=send_audio_data)
    receiver_thread = threading.Thread(target=receive_audio)

    sender_thread.start()
    receiver_thread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nCtrl + C detected")
        stop_event.set()
    finally:
        print("Stopped")