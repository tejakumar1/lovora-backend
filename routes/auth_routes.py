from flask import Blueprint, request, jsonify
from models import User
from config import db

auth = Blueprint("auth", __name__)

@auth.route("/register", methods=["POST"])
def register():
    data = request.json

    user = User(
        username=data["username"],
        mobile=data["mobile"],
        biometric_enabled=data["biometric_enabled"]
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True})

@auth.route("/login", methods=["POST"])
def login():
    identifier = request.json.get("identifier")

    user = User.query.filter(
        (User.mobile == identifier) | (User.username == identifier)
    ).first()

    if user:
        return jsonify({"exists": True, "user": {
            "username": user.username,
            "mobile": user.mobile
        }})

    return jsonify({"exists": False})