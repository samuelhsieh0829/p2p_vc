import time
import random
import socket
import struct
import threading

from flask import Flask, request, jsonify, render_template, redirect

from app import init_app
from app.core import server


if __name__ == "__main__":
    try:
        running = threading.Event()
        server.set_event(running)
        server.run()

        # Start the Flask server
        app = init_app()
        app.run(host="0.0.0.0", port=10001)
    finally:
        running.set()
        server.nat_thread.join()
