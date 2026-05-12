"""
calculator.py
-------------
Routes for the matrix calculator page and its JSON API endpoints.

The calculator page itself is rendered as HTML. The actual calculation
and history operations happen through small JSON endpoints that the
frontend JavaScript calls in the background (this pattern is called AJAX).
"""

from flask import Blueprint, render_template, request, jsonify, session

import database
import matrix_ops
from auth import login_required

# Blueprint for everything calculator-related
calc_bp = Blueprint("calculator", __name__)


# ---------------------------------------------------------------------------
# How session history caching works (the "session for speed" part):
#
# Every time we save a calculation to the database, we also keep the last
# N entries in `session["history_cache"]`. The frontend can show this
# instantly without a DB query. We refresh the cache from the DB whenever
# the user lands on the calculator page.
# ---------------------------------------------------------------------------
HISTORY_CACHE_SIZE = 20


def refresh_history_cache(user_id):
    """Reload the session's history cache from the database."""
    history = database.get_user_history(user_id, limit=HISTORY_CACHE_SIZE)
    session["history_cache"] = history
    return history


# ---------------------------------------------------------------------------
# Main calculator page
# ---------------------------------------------------------------------------
@calc_bp.route("/calculator")
@login_required
def calculator_page():
    """Render the calculator HTML, with history preloaded for the sidebar."""
    user_id = session["user_id"]
    history = refresh_history_cache(user_id)

    # Build initials for the avatar (e.g. "John Doe" -> "JD")
    name_parts = session.get("user_name", "User").split()
    if len(name_parts) >= 2:
        initials = (name_parts[0][0] + name_parts[-1][0]).upper()
    else:
        initials = name_parts[0][0].upper() if name_parts else "U"

    return render_template(
        "calculator.html",
        user_name=session.get("user_name", "User"),
        user_email=session.get("user_email", ""),
        user_initials=initials,
        history=history,
    )


# ---------------------------------------------------------------------------
# JSON API: perform a calculation
# ---------------------------------------------------------------------------
@calc_bp.route("/api/calculate", methods=["POST"])
@login_required
def api_calculate():
    """
    Receive Matrix A and Matrix B from the frontend, add them, save the
    result, and send everything back.

    Expected JSON body:
        { "matrix_a": [[...]], "matrix_b": [[...]] }

    Response on success:
        { "ok": true, "result": [[...]], "entry": {...history entry...} }

    Response on failure:
        { "ok": false, "error": "..." }   (with HTTP 400)
    """
    user_id = session["user_id"]

    # request.get_json(silent=True) returns None if the body isn't valid JSON,
    # instead of throwing — we handle that ourselves.
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "Missing or invalid JSON body."}), 400

    raw_a = payload.get("matrix_a")
    raw_b = payload.get("matrix_b")
    if raw_a is None or raw_b is None:
        return jsonify({"ok": False, "error": "Both matrix_a and matrix_b are required."}), 400

    # Step 1: clean the inputs (strings -> floats, empty -> 0)
    try:
        matrix_a = matrix_ops.parse_matrix_from_input(raw_a, "Matrix A")
        matrix_b = matrix_ops.parse_matrix_from_input(raw_b, "Matrix B")
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    # Step 2: do the math (this also validates sizes match)
    try:
        result = matrix_ops.add_matrices(matrix_a, matrix_b)
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    # Step 3: build the step-by-step breakdown (pure data, no DB storage needed)
    # Each cell gets {"label", "a", "b", "sum"} — frontend renders these as cards.
    steps = matrix_ops.build_steps(matrix_a, matrix_b, result)

    # Step 4: save to the database
    entry = database.save_calculation(user_id, matrix_a, matrix_b, result)

    # Step 4: update the session cache (newest first, capped at limit)
    cache = session.get("history_cache", [])
    cache.insert(0, entry)
    session["history_cache"] = cache[:HISTORY_CACHE_SIZE]

    return jsonify({"ok": True, "result": result, "steps": steps, "entry": entry})


# ---------------------------------------------------------------------------
# JSON API: get the user's history
# ---------------------------------------------------------------------------
@calc_bp.route("/api/history", methods=["GET"])
@login_required
def api_history():
    """Return the user's saved calculations as JSON, newest first."""
    user_id = session["user_id"]
    history = refresh_history_cache(user_id)
    return jsonify({"ok": True, "history": history})


# ---------------------------------------------------------------------------
# JSON API: delete one calculation
# ---------------------------------------------------------------------------
@calc_bp.route("/api/history/<int:calculation_id>", methods=["DELETE"])
@login_required
def api_delete_one(calculation_id):
    """Delete a single calculation by id (only if it belongs to this user)."""
    user_id = session["user_id"]
    was_deleted = database.delete_calculation(user_id, calculation_id)

    if not was_deleted:
        return jsonify({"ok": False, "error": "Calculation not found."}), 404

    # Refresh the cache so it stays in sync with the DB
    refresh_history_cache(user_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# JSON API: clear all history
# ---------------------------------------------------------------------------
@calc_bp.route("/api/history", methods=["DELETE"])
@login_required
def api_clear_history():
    """Delete every saved calculation for the current user."""
    user_id = session["user_id"]
    deleted_count = database.clear_user_history(user_id)
    session["history_cache"] = []
    return jsonify({"ok": True, "deleted": deleted_count})


# ---------------------------------------------------------------------------
# JSON API: get profile stats
# ---------------------------------------------------------------------------
@calc_bp.route("/api/profile", methods=["GET"])
@login_required
def api_profile_stats():
    """Return account stats (total calculations, joined date, etc.)."""
    user_id = session["user_id"]
    stats = database.get_user_stats(user_id)
    return jsonify({"ok": True, "stats": stats})


# ---------------------------------------------------------------------------
# JSON API: update profile (name / email / password)
# ---------------------------------------------------------------------------
@calc_bp.route("/api/profile", methods=["PATCH"])
@login_required
def api_profile_update():
    """
    Handle profile edits. The frontend sends only the fields it wants to change.

    Supported fields in the JSON body:
        { "action": "name",     "first_name": "…", "last_name": "…" }
        { "action": "email",    "email": "…" }
        { "action": "password", "current_password": "…",
                                "new_password": "…", "confirm_password": "…" }
    """
    from werkzeug.security import check_password_hash, generate_password_hash
    import re

    user_id = session["user_id"]
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "Missing request body."}), 400

    action = payload.get("action", "")

    # ── Change name ────────────────────────────────────────────────
    if action == "name":
        first = payload.get("first_name", "").strip()
        last  = payload.get("last_name",  "").strip()
        if not first or not last:
            return jsonify({"ok": False, "error": "First and last name are required."}), 400
        database.update_user_name(user_id, first, last)
        # Keep the session in sync so the page reflects the change immediately
        session["user_name"] = f"{first} {last}"
        return jsonify({"ok": True, "user_name": session["user_name"]})

    # ── Change email ───────────────────────────────────────────────
    if action == "email":
        new_email = payload.get("email", "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_email):
            return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400
        success = database.update_user_email(user_id, new_email)
        if not success:
            return jsonify({"ok": False, "error": "That email is already in use."}), 409
        session["user_email"] = new_email
        return jsonify({"ok": True, "email": new_email})

    # ── Change password ────────────────────────────────────────────
    if action == "password":
        current_pw  = payload.get("current_password", "")
        new_pw      = payload.get("new_password", "")
        confirm_pw  = payload.get("confirm_password", "")

        # Re-fetch the user so we can verify their current password
        user_row = database.find_user_by_id(user_id)
        if not user_row or not check_password_hash(user_row["password_hash"], current_pw):
            return jsonify({"ok": False, "error": "Current password is incorrect."}), 403
        if len(new_pw) < 8:
            return jsonify({"ok": False, "error": "New password must be at least 8 characters."}), 400
        if new_pw != confirm_pw:
            return jsonify({"ok": False, "error": "Passwords do not match."}), 400
        database.update_user_password(user_id, generate_password_hash(new_pw))
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "Unknown action."}), 400


# ---------------------------------------------------------------------------
# JSON API: compute steps only (no database write)
# Used by loadEntry() in the frontend to show step-by-step without
# creating a duplicate history record.
# ---------------------------------------------------------------------------
@calc_bp.route("/api/steps", methods=["POST"])
@login_required
def api_steps_only():
    """
    Compute and return step-by-step data for a given pair of matrices
    WITHOUT saving to the database.

    This endpoint exists specifically for "reload from history" — the user
    wants to see the step-by-step viewer for a past calculation, but we
    should NOT create a new history record just for that.

    Expected JSON body:
        { "matrix_a": [[...]], "matrix_b": [[...]] }

    Response:
        { "ok": true, "result": [[...]], "steps": [...] }
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "Missing request body."}), 400

    raw_a = payload.get("matrix_a")
    raw_b = payload.get("matrix_b")
    if raw_a is None or raw_b is None:
        return jsonify({"ok": False, "error": "Both matrix_a and matrix_b are required."}), 400

    try:
        matrix_a = matrix_ops.parse_matrix_from_input(raw_a, "Matrix A")
        matrix_b = matrix_ops.parse_matrix_from_input(raw_b, "Matrix B")
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    try:
        result = matrix_ops.add_matrices(matrix_a, matrix_b)
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    # build_steps is pure math — identical result to what was computed originally
    steps = matrix_ops.build_steps(matrix_a, matrix_b, result)

    # No database.save_calculation() call here — that is intentional
    return jsonify({"ok": True, "result": result, "steps": steps})