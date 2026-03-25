from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
CORS(app)

# ==============================
# 🔥 DATABASE CONFIG (RENDER FIX)
# ==============================
database_url = os.getenv("DATABASE_URL")

# 🔥 Fix for Render (postgres → postgresql)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# 🔥 Fallback for local (optional)
if not database_url:
    database_url = "postgresql://postgres:password@localhost:5432/lovora_db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================
# 🔥 MODEL
# ==============================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    mobile = db.Column(db.String(15), unique=True)
    biometric_enabled = db.Column(db.Boolean, default=False)

# ==============================
# 🔥 TEMP OTP STORE
# ==============================
otp_store = {}

# ==============================
# 🔥 CHECK USERNAME
# ==============================
@app.route('/check-username', methods=['POST'])
def check_username():
    username = request.json.get("username")

    user = User.query.filter_by(username=username).first()

    return jsonify({"available": user is None})

# ==============================
# 🔥 CHECK MOBILE
# ==============================
@app.route('/check-mobile', methods=['POST'])
def check_mobile():
    mobile = request.json.get("mobile")

    user = User.query.filter_by(mobile=mobile).first()

    return jsonify({"exists": user is not None})

# ==============================
# 🔥 SEND OTP
# ==============================
@app.route('/send-otp', methods=['POST'])
def send_otp():
    mobile = request.json.get("mobile")

    # 🔥 Test number
    otp = "222222" if mobile == "2222222222" else "123456"

    otp_store[mobile] = otp

    return jsonify({"otp": otp})

# ==============================
# 🔥 VERIFY OTP
# ==============================
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    otp = request.json.get("otp")

    valid = otp in otp_store.values() or otp == "222222"

    return jsonify({"verified": valid})

# ==============================
# 🔥 REGISTER
# ==============================
@app.route('/register', methods=['POST'])
def register():
    data = request.json

    existing = User.query.filter_by(mobile=data["mobile"]).first()
    if existing:
        return jsonify({"error": "User already exists"}), 400

    user = User(
        username=data["username"],
        mobile=data["mobile"],
        biometric_enabled=data.get("biometric_enabled", False)
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "success": True,
        "user": {
            "username": user.username,
            "mobile": user.mobile
        }
    })

# ==============================
# 🔥 LOGIN
# ==============================
@app.route('/login', methods=['POST'])
def login():
    identifier = request.json.get("identifier")

    user = User.query.filter(
        (User.mobile == identifier) | (User.username == identifier)
    ).first()

    if user:
        return jsonify({
            "exists": True,
            "user": {
                "username": user.username,
                "mobile": user.mobile,
                "biometric_enabled": user.biometric_enabled
            }
        })

    return jsonify({"exists": False})

# ==============================
# 🔥 HEALTH CHECK (IMPORTANT)
# ==============================
@app.route('/')
def home():
    return jsonify({"status": "Lovora backend running 🚀"})

# ==============================
# 🔥 DB INIT
# ==============================
with app.app_context():
    db.create_all()

# ⚠️ REMOVE app.run() for Render