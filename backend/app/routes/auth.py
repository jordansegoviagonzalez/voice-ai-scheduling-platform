from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from app.errors import ApiError
from app.services.session_security import clear_admin_session, require_admin_session, start_admin_session

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth/admin")


@auth_bp.route("/login", methods=["POST"])
def login() -> ResponseReturnValue:
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise ApiError("BAD_REQUEST", "Email and password are required.", 400)

    # Safely normalize email
    email = email.strip().lower()

    if email == current_app.config["ADMIN_EMAIL"].strip().lower() and password == current_app.config["ADMIN_PASSWORD"]:
        start_admin_session(
            name=current_app.config["ADMIN_NAME"],
            email=current_app.config["ADMIN_EMAIL"],
            role="admin_provider",
        )

        return jsonify(
            {
                "authenticated": True,
                "name": current_app.config["ADMIN_NAME"],
                "email": current_app.config["ADMIN_EMAIL"],
                "role": "admin_provider",
            }
        ), 200

    raise ApiError("UNAUTHORIZED", "Invalid credentials", 401)


@auth_bp.route("/session", methods=["GET"])
def get_session_info() -> ResponseReturnValue:
    require_admin_session()

    return jsonify(
        {
            "authenticated": True,
            "name": current_app.config["ADMIN_NAME"],
            "email": current_app.config["ADMIN_EMAIL"],
            "role": "admin_provider",
        }
    ), 200


@auth_bp.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    clear_admin_session()
    return jsonify({"success": True}), 200
