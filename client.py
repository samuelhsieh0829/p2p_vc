import pyaudio
import socket
import struct
import sys
import time
import threading

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

def receive_audio():
    global s
    try:
        print("Start receiving data")
        while True:
            data, addr = s.recvfrom(8192)

            # Get timestamp
            timestamp_byte = data[:8]
            timestamp = struct.unpack(">d", timestamp_byte)[0]
            audio_out.write(data[8:])

            # Output Ping
            t_delta = time.time() - timestamp
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
        while True:
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

    sender_thread.join()
    receiver_thread.join()