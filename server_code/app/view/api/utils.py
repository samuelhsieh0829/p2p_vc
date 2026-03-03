import time

from flask import Blueprint, jsonify

utils_api = Blueprint('util', __name__, url_prefix="/api")

# Get server time
@utils_api.route("/time")
def get_time():
    current_time = time.time()
    return jsonify({"time": current_time})