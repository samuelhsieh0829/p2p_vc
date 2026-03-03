from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .view.main import main_route
from .view.api.channel import channel_api
from .view.api.channels import channels_api
from .view.api.utils import utils_api

from .utils.logger import setup_logger, INFO


log = setup_logger(__name__, INFO)

def init_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    app.register_blueprint(main_route)
    app.register_blueprint(channel_api)
    app.register_blueprint(channels_api)
    app.register_blueprint(utils_api)
    return app