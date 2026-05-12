"""
app.py
------
This is the entry point. Run this file to start the web server:

    python app.py

Then open http://localhost:5000 in your browser.

What this file does:
  1. Creates the Flask app
  2. Sets up the database (creates tables if missing)
  3. Registers the auth and calculator blueprints (their routes)
  4. Defines the root "/" route and the "/home" landing page
"""

from flask import Flask, redirect, url_for, session, render_template

import database
from auth import auth_bp
from calculator import calc_bp


def create_app():
    """
    Build and configure the Flask app.

    Using a factory function (create_app) instead of a global `app` is a
    common Flask pattern. It makes testing easier and keeps imports clean.
    """
    app = Flask(__name__)

    # secret_key signs the session cookie so users can't tamper with it.
    # Change this to a long random string before sharing the project.
    app.secret_key = "change-this-secret-key-for-production-use"

    # Create DB tables on first run (safe to call every startup)
    database.init_database()

    # Register the auth routes (/login, /signup, /logout, /forgot)
    app.register_blueprint(auth_bp)

    # Register the calculator routes (/calculator, /api/calculate, etc.)
    app.register_blueprint(calc_bp)

    # ── Root "/" ─────────────────────────────────────────────────
    # Logged-in  → jump straight to the calculator
    # Logged-out → show the landing/home page
    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("calculator.calculator_page"))
        return redirect(url_for("home"))

    # ── Landing page "/home" ──────────────────────────────────────
    # Public — anyone can view this without an account.
    # If an already-logged-in user visits, redirect them to the app.
    @app.route("/home")
    def home():
        if "user_id" in session:
            return redirect(url_for("calculator.calculator_page"))
        return render_template("home.html")

    return app


# Only runs when you execute `python app.py` directly (not on import)
if __name__ == "__main__":
    app = create_app()
    # debug=True enables auto-reload and detailed error pages.
    # Set to False before deploying publicly.
    app.run(debug=True, port=5000)

