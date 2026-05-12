"""
auth.py
-------
All login / signup / logout routes live here.

We use a Flask "Blueprint" — think of it as a sub-app for related routes.
This keeps auth code separate from calculator code, but everything still
runs as one combined Flask app on one port.
"""

import re
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

import database

# Create the blueprint. The name "auth" is used internally by Flask.
auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Helper: login_required decorator
# ---------------------------------------------------------------------------
def login_required(view_function):
    """
    Decorator that redirects to the login page if no user is signed in.

    Usage:
        @app.route("/secret")
        @login_required
        def secret_page():
            return "Hello, logged-in user!"

    A "decorator" wraps a function and runs extra code before/after it.
    @wraps(view_function) keeps the original function's name visible to Flask.
    """
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view_function(*args, **kwargs)
    return wrapped_view


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    """Quick check that an email looks like an email."""
    return bool(EMAIL_PATTERN.match(email))


def is_strong_enough_password(password):
    """
    Returns (is_ok, message).
    Keeping the rule simple: at least 8 characters.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    return True, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show login form (GET) or process login attempt (POST)."""
    # If already logged in, send them to the calculator
    if "user_id" in session:
        return redirect(url_for("calculator.calculator_page"))

    if request.method == "POST":
        # Grab + clean the inputs
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Basic emptiness check
        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html")

        # Look the user up in the database
        user_row = database.find_user_by_email(email)

        # If user exists AND their stored hash matches the password they typed
        if user_row and check_password_hash(user_row["password_hash"], password):
            # Save info we want to remember between requests
            session["user_id"] = user_row["id"]
            session["user_email"] = user_row["email"]
            session["user_name"] = f"{user_row['first_name']} {user_row['last_name']}"
            return redirect(url_for("calculator.calculator_page"))

        # We deliberately use the SAME message for "wrong email" and
        # "wrong password" so attackers can't tell which is which.
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Show signup form (GET) or create a new account (POST)."""
    if "user_id" in session:
        return redirect(url_for("calculator.calculator_page"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("confirm_password", "")
        agreed_to_terms = request.form.get("terms")

        # Run checks one by one — show the first error we find
        if not first_name or not last_name:
            flash("Please enter your first and last name.", "error")
        elif not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
        elif not agreed_to_terms:
            flash("You must agree to the Terms of Service.", "error")
        else:
            is_password_ok, password_error = is_strong_enough_password(password)
            if not is_password_ok:
                flash(password_error, "error")
            elif password != password_confirm:
                flash("Passwords do not match.", "error")
            else:
                # All checks passed — try to create the user.
                # We hash the password so plain text is NEVER stored.
                password_hash = generate_password_hash(password)
                new_user_id = database.create_user(
                    email=email,
                    password_hash=password_hash,
                    first_name=first_name,
                    last_name=last_name,
                )

                if new_user_id is None:
                    # The database said this email already exists
                    flash("An account with that email already exists.", "error")
                else:
                    flash("Account created! Please log in.", "success")
                    return redirect(url_for("auth.login"))

    return render_template("signup.html")


@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    """
    Password reset placeholder.

    A real reset flow needs email sending + secure tokens, which is beyond
    a school project. We show a generic success message either way so
    attackers can't use this page to discover which emails are registered.
    """
    if request.method == "POST":
        flash("If that email exists, a reset link has been sent.", "success")
    return render_template("forgot.html")


@auth_bp.route("/logout")
def logout():
    """Clear the session and send the user back to login."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
