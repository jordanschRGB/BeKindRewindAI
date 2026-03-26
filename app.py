"""Flask application factory."""

import os
from flask import Flask


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config["OUTPUT_DIR"] = os.path.join(
        os.path.expanduser("~"), "Videos", "MemoryVault"
    )
    app.config["CONFIG_DIR"] = os.path.join(
        os.path.expanduser("~"), ".memoryvault"
    )

    # Ensure bundled deps are on PATH
    from engine.deps import add_bin_to_path
    add_bin_to_path()

    from api import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def home():
        from flask import render_template
        return render_template("home.html")

    @app.route("/setup")
    def setup():
        from flask import render_template
        return render_template("setup.html")

    @app.route("/session")
    def session_page():
        from flask import render_template
        return render_template("session.html")

    @app.route("/library")
    def library_page():
        from flask import render_template
        return render_template("library.html")

    @app.route("/settings")
    def settings_page():
        from flask import render_template
        return render_template("settings.html")

    @app.route("/chat")
    def chat_page():
        from flask import render_template
        return render_template("chat.html")

    return app
