import sys
import os
from collections import defaultdict, deque
import numpy as np
import socket
import json
import time
import threading
import struct
import ipaddress

import pyaudio
import requests

from logger import setup_logger, INFO, DEBUG

path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# Load config from JSON file
try:
    with open("config.json", "r") as f:
        config = json.load(f)
        if "username" in config and "p2p_retry_time" in config and "audio_chunk" in config and "server_address" in config and "server_port" in config and "auto_lan" in config and "debug" in config:
            pass
        else:
            raise FileNotFoundError("Missing required keys in config.json")
        
except FileNotFoundError:
    username = input("Enter your username: ")
    p2p_retry_time = 0.1
    with open("config.json", "w") as f:
        config = {
            "username": username,
            "p2p_retry_time": p2p_retry_time,
            "audio_chunk": 2048,
            "server_address": "vc.itzowo.net",
            "server_port": 80,
            "auto_lan": True,
            "debug": False
        }
        json.dump(config, f, indent=4)

# Setup logger
if config["debug"]:
    log_level = DEBUG
else:
    log_level = INFO
log = setup_logger(__name__, log_level)
log.info("Starting client")


username = config["username"]
p2p_retry_time = config["p2p_retry_time"]

log.info(f"Username: {username}")

# 之後把init內的東西把它做成模組(audio, socket)

# Audio init
chunk = config["audio_chunk"]
sample_format = pyaudio.paInt16
channels = 1
fs = 44100

input_audio = pyaudio.PyAudio()
audio_in = input_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, input=True)

output_audio = pyaudio.PyAudio()
audio_out = output_audio.open(format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, output=True)

# Socket init
def get_local_ip():
    # 建立一個 UDP socket，連到一個非內網的虛擬位址
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

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 0))
s.settimeout(0.1)  # Set timeout for socket operations
PORT = s.getsockname()[1]
LOCAL_IP = get_local_ip()
log.debug(f"Local IP: {LOCAL_IP}")

# Threading
stop_event = threading.Event()

# Main server
server_address = config["server_address"]
session = requests.Session()

# Get time offset
time_offset = 0
try:
    t0 = time.time()
    server_time = session.get(f"http://{server_address}/api/time")
    t1 = time.time()
    rtt = t1 - t0
    t_server = float(server_time.json()["time"])
    time_offset = t_server + (rtt / 2) - t1
except requests.exceptions.RequestException as e:
    log.critical(f"Error connecting to server: {e}")
    sys.exit(1)

self_ip = ""
auto_lan = config["auto_lan"]
local_channel_member_list:list[dict] = [] # Temp list of members in the channel (to check if server side list updated)
connecting_list:list[dict] = [] # List of P2P connections user data
play_queue = deque(maxlen=10)
buffer_started = False
send_data = b"hello"
confirm_data = b"confirm"

def mix_audio(audio_chunks: list[bytes]) -> bytes:
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
            log.exception(f"Error converting chunk to numpy array")
            continue
        
    if not arrays:
        return b''

    # 保護：強制對齊成相同最小長度，防止 np.sum 出錯
    min_len = min(len(arr) for arr in arrays)
    arrays = [arr[:min_len] for arr in arrays]

    mixed = np.sum(arrays, axis=0)
    mixed = np.clip(mixed, -32768, 32767)  # 防止爆音

    return mixed.astype(np.int16).tobytes()


def receive_audio():
    global s, play_queue, audio_out, buffer_started

    buffer_window = 0.02  # seconds (adjust for latency/quality tradeoff)
    peer_buffers = defaultdict(list)

    try:
        log.debug("Start receiving data")
        last_playback = time.time()

        while not stop_event.is_set():
            now = time.time()

            try:
                data, addr = s.recvfrom(32768)
            except socket.timeout:
                continue
            
            # Check if the data is valid
            if data == send_data:
                log.debug(f"Received NAT punch response from {addr}")
                s.sendto(confirm_data, addr)
                continue
            
            if data == confirm_data:
                log.debug(f"Received NAT punch confirmation from {addr}")
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

            # 計算,顯示Ping
            t_delta = (time.time() + time_offset) - timestamp
            sys.stdout.write(f"\rPing: {t_delta*1000:.2f} ms")
            sys.stdout.flush()

            # Every 50ms (or so), mix and play
            if now - last_playback >= buffer_window:
                chunks = [chunk for chunks in peer_buffers.values() for chunk in chunks]
                mixed = mix_audio(chunks)

                if mixed:
                    play_queue.append(mixed)

                peer_buffers.clear()
                last_playback = now
            
            if not buffer_started and len(play_queue) >= 3:
                buffer_started = True

    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    # except OSError:
    #     pass
    finally:
        output_audio.terminate()
        log.info("Audio receive stopped")

def audio_playback_loop():
    global play_queue, audio_out, buffer_started
    try:
        while not stop_event.is_set():
            if play_queue and buffer_started:
                audio_out.write(play_queue.popleft())
            else:
                time.sleep(0.005)
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
    finally:
        audio_out.stop_stream()
        audio_out.close()
        log.info("Audio playback stopped")

def send_audio_data():
    global s, audio_in, connecting_list
    try:
        log.debug("Start sending data")
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
    log.debug(f"Starting P2P connection to {member['name']} ({member['ip']}:{member['port']})")
    location = (member["ip"], member["port"])

    while not stop_event.is_set():
        if member not in local_channel_member_list:
            log.info(f"Member {member['name']} left the channel")
            log.debug(f"Stopping P2P connection to {member['name']} ({member['ip']}:{member['port']})")
            break

        s.sendto(send_data, location)
        try:
            data, addr = s.recvfrom(1024)
            if addr != location:
                continue
            if data == send_data or data == confirm_data:
                log.debug(f"{addr} NAT punch successful")
                log.info(f"Connected to {member['name']}")
                if member not in connecting_list:
                    connecting_list.append(member)
                for i in range(10):
                    s.sendto(confirm_data, location)
                return
        except socket.timeout:
            pass
        except OSError:
            log.debug("Received wrong packet while P2P")
        finally:
            time.sleep(p2p_retry_time)

def fetch_channel(channel_id:int):
    try:
        response = session.get(f"http://{server_address}/api/channel/{channel_id}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to server: {e}")
        return
    resp = response.json()
    log.debug(f"Response: {resp}")
    return resp

def fetch_channel_user_list(channel_id:int):
    try:
        response = session.get(f"http://{server_address}/api/channel/{channel_id}/members")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"Error connecting to server: {e}")
        return
    resp = response.json()
    log.debug(f"Response: {resp}")
    return resp

def is_same_lan(ip1, ip2):
    try:
        net1 = ipaddress.IPv4Address(ip1)
        net2 = ipaddress.IPv4Address(ip2)
        # 比對前兩段或前三段的 IP（視情況而定）
        return str(net1).split('.')[:3] == str(net2).split('.')[:3]
    except:
        return False

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
            # 成員增加
            if len(members) > len(local_channel_member_list):
                for member in members:
                    if member not in local_channel_member_list:

                        log.info(f"New member: {member['name']}")

                        # Check if the member is in the same LAN
                        found = False
                        if is_same_lan(member["ip"], self_ip) and (member["name"] != username) and auto_lan:
                            log.info(f"Same LAN: {member['name']} ({member['ip']}:{member['port']})")
                            resp = session.post(f"http://{server_address}/api/channel/{channel_id}/lan_ip", json={"name": username, "ip": self_ip, "lan_ip": LOCAL_IP, "port": PORT})
                            if resp.status_code != 200:
                                if resp.status_code == 500:
                                    log.error("Server error")
                                    time.sleep(2)
                                    continue
                                log.error(f"Error sending LAN IP: {resp.status_code} {resp.json()}")
                                continue
                            log.info(f"LAN IP sent: {resp.json()}")

                            # Check if the member in the same LAN already POST their IP
                            for lan_member in resp.json():
                                if lan_member["name"] == member["name"]:
                                    log.info(f"New member: {lan_member['name']} ({lan_member['lan_ip']}:{lan_member['port']})")
                                    member_info = {
                                        "name": lan_member["name"],
                                        "ip": lan_member["lan_ip"],
                                        "port": lan_member["port"]
                                    }
                                    local_channel_member_list.append(member_info)
                                    s.sendto(send_data, (lan_member["lan_ip"], lan_member["port"]))
                                    new_p2p_thread = threading.Thread(target=start_p2p, args=(member_info,))
                                    new_p2p_thread.start()
                                    found = True

                            # Wait for the member to POST their IP
                            count = 0
                            while not found:
                                count += 1
                                resp2 = session.post(f"http://{server_address}/api/channel/{channel_id}/lan_ip", json={"name": username, "ip": self_ip, "lan_ip": LOCAL_IP, "port": PORT})
                                if resp2.json() == resp.json():
                                    log.info("Waiting for LAN IP...")
                                    pass
                                else:
                                    log.info("LAN IP found")
                                    for lan_member in resp2.json():
                                        if lan_member["name"] == member["name"]:
                                            log.info(f"New member: {lan_member['name']} ({lan_member['lan_ip']}:{lan_member['port']})")
                                            member_info = {
                                                "name": lan_member["name"],
                                                "ip": lan_member["lan_ip"],
                                                "port": lan_member["port"]
                                            }
                                            local_channel_member_list.append(member_info)
                                            s.sendto(send_data, (lan_member["lan_ip"], lan_member["port"]))
                                            new_p2p_thread = threading.Thread(target=start_p2p, args=(member_info,))
                                            new_p2p_thread.start()
                                            found = True
                                if found:
                                    break
                                if count > 10:
                                    log.error("LAN IP not found")
                                    break
                                time.sleep(1)
                        if not found:
                            local_channel_member_list.append(member)
                            if member["name"] == username:
                                continue

                            s.sendto(send_data, (member["ip"], member["port"]))
                            new_p2p_thread = threading.Thread(target=start_p2p, args=(member,))
                            new_p2p_thread.start()
                log.debug(f"Updated member list: {local_channel_member_list}")
            # 成員減少
            elif len(members) < len(local_channel_member_list):
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
                log.debug(f"Updated member list: {local_channel_member_list}")
            # 成員不變
            else:
                pass # 之後再說 幹

def join_channel(channel_id:int):
    response = session.post(f"http://{server_address}/api/channel/{channel_id}/join")
    if response.status_code != 200:
        log.error(f"Error joining channel: {response.status_code} {response.json()}")
        return None
    resp = response.json()
    port = int(resp["port"])
    log.debug(f"Port: {port}")
    s.settimeout(2)  # Set timeout for socket operations
    try:
        while True:
            username_bytes = username.encode('utf-8')
            username_length = len(username_bytes)
            packet = struct.pack(">II", channel_id, username_length) + username_bytes
            s.sendto(packet, (server_address, port))
            log.debug(f"Join channel packet sent to {server_address}:{port}")
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

def leave_channel(channel_id:int):
    response = session.post(f"http://{server_address}/api/channel/{channel_id}/leave", json={"name": username})
    if response.status_code != 200:
        log.error(f"Error leaving channel: {response.status_code} {response.json()}")

        return None
    resp = response.json()
    return resp

def main(channel_id:int=None):
    global local_channel_member_list, self_ip
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
        temp = leave_channel(channel_id)
        return

    channel_data = fetch_channel(channel_id)
    
    if channel_data is None:
        log.error("Channel not found")
        return
    
    for member in fetch_channel_user_list(channel_id):
        if member["name"] == username:
            self_ip = member["ip"]
            log.debug(f"Self IP: {self_ip}")
            break

    sender_thread = threading.Thread(target=send_audio_data)
    sender_thread.start()

    receiver_thread = threading.Thread(target=receive_audio)
    receiver_thread.start()

    play_back_thread = threading.Thread(target=audio_playback_loop)
    play_back_thread.start()

    update_thread = threading.Thread(target=update_member, args=(channel_id,))
    update_thread.start()

    try:
        while True:
            run = True
            print()
            cmd = input("Enter command (exit): ").strip().lower()
            if cmd == "exit":
                log.info("Exiting...")
                run = False
                break
            # elif cmd == "leave":
            #     log.info("Leaveing channel")
            #     break
            else:
                log.info("Invalid command")
                continue
    except KeyboardInterrupt:
        log.info("\nCtrl + C detected")
        run = False
    except Exception:
        log.exception("Error")
        run = False
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
        return run

if __name__ == "__main__":
    run = True
    while run:
        try:
            run = main()
        except KeyboardInterrupt:
            log.info("\nCtrl + C detected")
            run = False
        except Exception:
            log.exception("Error in main loop")
            run = False
    input("Press Enter to exit...")