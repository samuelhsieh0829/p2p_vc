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
import numpy as np
from collections import defaultdict

# Setup logger
log = setup_logger(__name__, INFO)
log.info("Starting client")

# Load environment variables from .env file
load_dotenv()
username = os.getenv("SELF_USERNAME") or os.getenv("USERNAME")
p2p_retry_time = float(os.getenv("P2P_RETRY_TIME", 1))
log.info(f"Username: {username}")

# Audio init
chunk = int(os.getenv("AUDIO_CHUNK", 1024))
sample_format = pyaudio.paInt16
channels = 1
fs = 44100

input_audio = pyaudio.PyAudio()
audio_in = input_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, input=True)

output_audio = pyaudio.PyAudio()
audio_out = output_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, output=True)

# Socket init
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 0))
s.settimeout(0.1)  # Set timeout for socket operations
PORT = s.getsockname()[1]

# Threading
stop_event = threading.Event()

# Main server
server_address = os.getenv("SERVER_ADDRESS")
server_http_port = int(os.getenv("SERVER_HTTP_PORT", 80))
# Get time offset
time_offset = 0
try:
    t0 = time.time()
    server_time = requests.get(f"http://{server_address}:{server_http_port}/api/time")
    t1 = time.time()
    rtt = t1 - t0
    server_time = server_time.json()["time"]
    time_offset = server_time + (rtt / 2) - time.time()
except requests.exceptions.RequestException as e:
    log.critical(f"Error connecting to server: {e}")
    sys.exit(1)

local_channel_member_list:list[dict] = [] # Temp list of members in the channel (to check if server side list updated)
connecting_list:list[dict] = [] # List of P2P connections user data
send_data = b"hello"

def mix_audio(audio_chunks):
    arrays = []
    for chunk in audio_chunks:
        if len(chunk) % 2 != 0:
            continue  # Skip malformed chunks
        arrays.append(np.frombuffer(chunk, dtype=np.int16))
    
    if not arrays:
        return b"\x00" * 2048  # Return silence if nothing to mix
    
    mixed = np.mean(arrays, axis=0).astype(np.int16)
    return mixed.tobytes()

def receive_audio():
    global s

    buffer_window = 0.02  # seconds (adjust for latency/quality tradeoff)
    peer_buffers = defaultdict(list)

    try:
        log.info("Start receiving data")
        last_playback = time.time()
        while not stop_event.is_set():
            now = time.time()

            try:
                data, addr = s.recvfrom(32768)
            except socket.timeout:
                continue

            if data == send_data:
                s.sendto(send_data, addr)
                log.info(f"Received NAT punch response from {addr}")
                continue

            if len(data) < 8:
                log.warning("Received data is too short")
                continue
            # Get timestamp
            timestamp_byte = data[:8]
            timestamp = struct.unpack(">d", timestamp_byte)[0]
            audio_data = data[8:]

            # Save by peer address
            peer_buffers[addr].append(audio_data)

            # Every 50ms (or so), mix and play
            if now - last_playback >= buffer_window:
                mixed_audio = mix_audio([chunk for chunks in peer_buffers.values() for chunk in chunks])
                if mixed_audio:
                    audio_out.write(mixed_audio)
                peer_buffers.clear()
                last_playback = now

            # audio_out.write(data[8:])

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
    # except OSError:
    #     pass
    finally:
        output_audio.terminate()
        log.info("Audio receive stopped")

def send_audio_data():
    global s, audio_in, connecting_list
    try:
        log.info("Start sending data")
        while not stop_event.is_set():
            try:
                audio = audio_in.read(chunk)
            except OSError:
                continue
            # Add timestamop
            for member in connecting_list:
                if member["name"] == username:
                    continue
                audio_out_target_location = (member["ip"], member["port"])
                timestamp = time.time()
                timestamp_bytes = struct.pack(">d", timestamp)
                s.sendto(timestamp_bytes+audio, audio_out_target_location)
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    finally:
        input_audio.terminate()
        log.info("Stopped sending audio")

def start_p2p(member:dict):
    global connecting_list, s
    log.info(f"Starting P2P connection to {member['name']} ({member['ip']}:{member['port']})")
    location = (member["ip"], member["port"])

    while not stop_event.is_set():
        if member not in local_channel_member_list:
            log.info(f"Member {member['name']} left the channel")
            log.info(f"Stopping P2P connection to {member['name']} ({member['ip']}:{member['port']})")
            break

        s.sendto(send_data, location)
        try:
            data, addr = s.recvfrom(1024)
            if data == send_data:
                log.info(f"{addr} NAT punch successful")
                if member not in connecting_list:
                    connecting_list.append(member)
                return
        except socket.timeout:
            pass
        except OSError:
            log.warning("Received wrong packet while P2P")
        finally:
            time.sleep(p2p_retry_time)

def fetch_channel(channel_id:int):
    try:
        response = requests.get(f"http://{server_address}:{server_http_port}/api/channel/{channel_id}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to server: {e}")
        return
    resp = response.json()
    log.debug(f"Response: {resp}")
    return resp

def fetch_channel_user_list(channel_id:int):
    try:
        response = requests.get(f"http://{server_address}:{server_http_port}/api/channel/{channel_id}/members")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to server: {e}")
        return
    resp = response.json()
    log.debug(f"Response: {resp}")
    return resp

def update_member(channel_id:int):
    global local_channel_member_list
    while not stop_event.is_set():
        data = fetch_channel_user_list(channel_id)
        if data is None:
            log.error("Failed to fetch channel user list")
            time.sleep(2)
            continue

        members = data.copy()
        if members == local_channel_member_list:
            time.sleep(2)
            continue
        else:
            if len(members) > len(local_channel_member_list):
                for member in members:
                    if member not in local_channel_member_list:
                        log.info(f"New member: {member['name']}")
                        local_channel_member_list.append(member)
                        if member["name"] == username:
                            continue
                        new_p2p_thread = threading.Thread(target=start_p2p, args=(member,))
                        new_p2p_thread.start()
            else:
                for member in local_channel_member_list.copy():
                    if member not in members:
                        if member["name"] == username:
                            stop_event.set()
                            continue
                        local_channel_member_list.remove(member)
                        for conn in connecting_list:
                            if conn["ip"] == member["ip"] and conn["port"] == member["port"]:
                                connecting_list.remove(conn)
                                log.info(f"Removed connection to {member['name']}")
            log.info(f"Updated member list: {local_channel_member_list}")

def join_channel(channel_id:int):
    response = requests.post(f"http://{server_address}:{server_http_port}/api/channel/{channel_id}/join")
    if response.status_code != 200:
        log.error(f"Error joining channel: {response.status_code} {response.json()}")
        return None
    resp = response.json()
    port = int(resp["port"])
    log.info(f"Port: {port}")
    s.settimeout(2)  # Set timeout for socket operations
    try:
        while True:
            username_bytes = username.encode('utf-8')
            username_length = len(username_bytes)
            packet = struct.pack(">II", channel_id, username_length) + username_bytes
            s.sendto(packet, (server_address, port))
            log.info(f"Join channel packet sent to {server_address}:{port}")
            try:
                data, addr = s.recvfrom(1024)
                if data == send_data:
                    log.info(f"Successfully joined channel {channel_id} as {username}")
                    s.settimeout(0.1)  # Reset timeout for socket operations
                    return True
                else:
                    log.error(f"Join channel failed, received: {data.decode()}")
                    return False
            except socket.timeout:
                log.warning("No response from server, retrying...")
                continue
            except OSError:
                log.warning("Received wrong packet")
                continue

    except:
        log.exception("Error sending join channel packet")
    # try:
    #     #######################
    #     #之後試試看改用socket請求
    #     #######################
    #     response = requests.post(f"http://{server_address}/api/channel/{channel_id}/join", json={"name": username, "port": PORT})
    #     response.raise_for_status()
    # except requests.exceptions.RequestException as e:
    #     log.error(f"Error connecting to server: {e}")
    #     return None
    # resp = response.json()
    # return resp

def leave_channel(channel_id:int):
    response = requests.post(f"http://{server_address}:{server_http_port}/api/channel/{channel_id}/leave", json={"name": username})
    if response.status_code != 200:
        log.error(f"Error leaving channel: {response.status_code} {response.json()}")

        return None
    resp = response.json()
    return resp

def main(channel_id:int=None):
    global local_channel_member_list
    if channel_id is None:
        channel_id = input("Enter channel ID: ")
        try:
            channel_id = int(channel_id)
        except ValueError:
            log.error("Invalid channel ID. Please enter a number.")
            return
    
    temp = join_channel(channel_id)
    if not temp:
        log.error("Failed to join channel")
        return

    channel_data = fetch_channel(channel_id)
    if channel_data is None:
        log.error("Channel not found")
        return
    
    sender_thread = threading.Thread(target=send_audio_data)
    sender_thread.start()

    receiver_thread = threading.Thread(target=receive_audio)
    receiver_thread.start()

    update_thread = threading.Thread(target=update_member, args=(channel_id,))
    update_thread.start()

    try:
        while True:
            cmd = input("Enter command (join/leave/exit): ").strip().lower()
            if cmd == "exit":
                log.info("Exiting...")
                break
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    finally:
        # leaving channel
        leave_channel(channel_id)
        log.info("Stopping threads...")
        stop_event.set()

        # Wait for threads to finish
        sender_thread.join()
        receiver_thread.join()
        update_thread.join()

        # Stop audio streams and close sockets
        audio_in.stop_stream()
        audio_in.close()
        input_audio.terminate()
        audio_out.stop_stream()
        audio_out.close()
        output_audio.terminate()
        s.close()

        log.info("Main stopped")
        exit()

if __name__ == "__main__":
    main()
