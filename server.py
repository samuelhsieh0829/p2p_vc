from flask import Flask, request, jsonify, render_template
import time

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/time")
def get_time():
    current_time = time.time()
    return jsonify({"time": current_time})

app.run(host="0.0.0.0", port=5000, debug=True)
