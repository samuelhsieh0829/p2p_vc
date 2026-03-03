from flask import Blueprint, render_template

main_route = Blueprint('main_route', __name__)

@main_route.route("/")
def index():
    return render_template("index.html")

@main_route.route("/channels", methods=["GET"])
def list_channels():
    return render_template("channels.html")