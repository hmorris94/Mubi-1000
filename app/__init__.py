"""The Mubi 1000 — Flask application."""

from flask import Flask
from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix
from .blueprint import create_blueprint

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
Compress(app)
app.register_blueprint(create_blueprint(), url_prefix="/")
