from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
import uuid


app = Flask(__name__)
CORS(app)
database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
    database_url = "postgresql://postgres:password@localhost:5432/lovora_db"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(150), nullable=True)
    biometric_enabled = db.Column(db.Boolean, default=False)

    posts = db.relationship('Post', backref='user', lazy=True)


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    caption = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    media = db.relationship('Media', backref='post', lazy=True)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    media_url = db.Column(db.Text)
    media_type = db.Column(db.String(20))


class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_like'),
    )


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

otp_store = {}

@app.route('/check-username', methods=['POST'])
def check_username():
    username = request.json.get("username")
    if not username:
        return jsonify({"error": "Username required"}), 400

    user = User.query.filter_by(username=username).first()
    return jsonify({"available": user is None})


@app.route('/check-mobile', methods=['POST'])
def check_mobile():
    mobile = request.json.get("mobile")
    if not mobile:
        return jsonify({"error": "Mobile required"}), 400

    user = User.query.filter_by(mobile=mobile).first()
    return jsonify({"exists": user is not None})


@app.route('/send-otp', methods=['POST'])
def send_otp():
    mobile = request.json.get("mobile")

    otp = "222222" if mobile == "2222222222" else "123456"
    otp_store[mobile] = otp

    return jsonify({"otp": otp})


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    otp = request.json.get("otp")
    valid = otp in otp_store.values() or otp == "222222"
    return jsonify({"verified": valid})


@app.route('/register', methods=['POST'])
def register():
    data = request.json

    if not data.get("username") or not data.get("mobile"):
        return jsonify({"error": "Missing fields"}), 400

    existing = User.query.filter_by(mobile=data["mobile"]).first()
    if existing:
        return jsonify({"error": "User already exists"}), 400

    last_user = User.query.order_by(User.id.desc()).first()
    if last_user:
        new_id = last_user.id + 1
    else:
        new_id = 300000

    user = User(
        id=new_id,
        username=data["username"],
        mobile=data["mobile"],
        biometric_enabled=data.get("biometric_enabled", False)
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "mobile": user.mobile
        }
    })


@app.route('/login', methods=['POST'])
def login():
    identifier = request.json.get("identifier")

    user = User.query.filter(
        (User.mobile == identifier) | (User.username == identifier)
    ).first()

    if not user:
        return jsonify({"exists": False})

    token = str(uuid.uuid4())

    return jsonify({
        "exists": True,
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "mobile": user.mobile,
            "email": user.email,
            "bio": user.bio,
            "location": user.location,
            "biometric_enabled": user.biometric_enabled
        }
    })
@app.route('/create-post', methods=['POST'])
def create_post():
    try:
        data = request.json

        # ✅ SAFE USER ID
        user_id = int(data.get("user_id", 0))

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "Invalid user"}), 400

        # ✅ SAFE TYPE
        post_type = data.get("type", "text")

        post = Post(
            user_id=user_id,
            type=post_type,
            caption=data.get("caption", "")
        )

        db.session.add(post)
        db.session.commit()

        # ✅ SAFE MEDIA HANDLING
        media_list = data.get("media", [])

        if isinstance(media_list, list):
            for m in media_list:
                db.session.add(Media(
                    post_id=post.id,
                    media_url=m.get("url", ""),
                    media_type=m.get("type", "file")
                ))

        db.session.commit()

        return jsonify({"success": True, "post_id": post.id})

    except Exception as e:
        print("🔥 CREATE POST ERROR:", str(e))  # 👈 VERY IMPORTANT
        return jsonify({"error": str(e)}), 500

@app.route('/update-post/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    try:
        data = request.json

        post = db.session.get(Post, post_id)

        if not post:
            return jsonify({"error": "Post not found"}), 404

        # 🔥 UPDATE CAPTION
        post.caption = data.get("caption", post.caption)

        db.session.commit()

        return jsonify({"success": True, "message": "Post updated"})

    except Exception as e:
        print("🔥 UPDATE POST ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/delete-post/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        post = db.session.get(Post, post_id)

        if not post:
            return jsonify({"error": "Post not found"}), 404

        # 🔥 DELETE MEDIA FIRST (IMPORTANT)
        Media.query.filter_by(post_id=post.id).delete()

        db.session.delete(post)
        db.session.commit()

        return jsonify({"success": True, "message": "Post deleted"})

    except Exception as e:
        print("🔥 DELETE POST ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/feed', methods=['GET'])
def get_feed():

    posts = Post.query.order_by(Post.created_at.desc()).all()

    result = []

    for p in posts:
        result.append({
            "post_id": p.id,
            "user": {
                "id": p.user.id,
                "username": p.user.username,
            },
            "type": p.type,
            "caption": p.caption,
            "media": [
                {"url": m.media_url, "type": m.media_type}
                for m in p.media
            ],
            "likes_count": len(p.likes),
            "comments_count": len(p.comments),
            "created_at": p.created_at.isoformat()
        })

    return jsonify(result)


@app.route('/like', methods=['POST'])
def like_post():
    data = request.json

    existing = Like.query.filter_by(
        user_id=data["user_id"],
        post_id=data["post_id"]
    ).first()

    if existing:
        return jsonify({"message": "Already liked"})

    db.session.add(Like(
        user_id=data["user_id"],
        post_id=data["post_id"]
    ))

    db.session.commit()
    return jsonify({"success": True})


@app.route('/comment', methods=['POST'])
def comment_post():
    data = request.json

    db.session.add(Comment(
        user_id=data["user_id"],
        post_id=data["post_id"],
        text=data["text"]
    ))

    db.session.commit()
    return jsonify({"success": True})

@app.route('/profile/<int:user_id>', methods=['GET', 'PATCH'])
def profile(user_id):
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()

        return jsonify({
            "user": {
                "id": user.id,
                "username": user.username,
                "mobile": user.mobile,
                "email": user.email,
                "bio": user.bio,
                "location": user.location,
                "biometric_enabled": user.biometric_enabled
            },
            "posts": [
                {
                    "id": post.id,
                    "caption": post.caption,
                    "type": post.type,
                    "media": [
                        {"url": m.media_url, "type": m.media_type}
                        for m in post.media
                    ]
                } for post in posts
            ],
            "posts_count": len(posts)
        })

    data = request.get_json() or {}

    if "username" in data:
        user.username = data["username"].strip()

    if "mobile" in data:
        user.mobile = data["mobile"].strip()

    if "email" in data:
        user.email = data["email"].strip()

    if "bio" in data:
        user.bio = data["bio"].strip()

    if "location" in data:
        user.location = data["location"].strip()

    if "biometric_enabled" in data:
        user.biometric_enabled = bool(data["biometric_enabled"])

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "mobile": user.mobile,
            "email": user.email,
            "bio": user.bio,
            "location": user.location,
            "biometric_enabled": user.biometric_enabled
        }
    })
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()

        return jsonify({
            "user": {
                "id": user.id,
                "username": user.username,
                "mobile": user.mobile,
                "biometric_enabled": user.biometric_enabled
            },
            "posts": [
                {
                    "id": post.id,
                    "caption": post.caption,
                    "type": post.type,
                    "media": [
                        {"url": m.media_url, "type": m.media_type}
                        for m in post.media
                    ]
                } for post in posts
            ],
            "posts_count": len(posts)
        })

    data = request.get_json() or {}

    username = data.get("username")
    mobile = data.get("mobile")
    biometric_enabled = data.get("biometric_enabled")

    if username is not None:
        username = username.strip()
        if not username:
            return jsonify({"error": "Username cannot be empty"}), 400

        existing_username = User.query.filter(
            User.username == username,
            User.id != user_id
        ).first()
        if existing_username:
            return jsonify({"error": "Username already taken"}), 400

        user.username = username

    if mobile is not None:
        mobile = mobile.strip()
        if not mobile:
            return jsonify({"error": "Mobile cannot be empty"}), 400

        existing_mobile = User.query.filter(
            User.mobile == mobile,
            User.id != user_id
        ).first()
        if existing_mobile:
            return jsonify({"error": "Mobile already exists"}), 400

        user.mobile = mobile

    if biometric_enabled is not None:
        user.biometric_enabled = bool(biometric_enabled)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "mobile": user.mobile,
            "biometric_enabled": user.biometric_enabled
        }
    })
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()

    return jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "mobile": user.mobile,
            "biometric_enabled": user.biometric_enabled
        },

        "posts": [
            {
                "id": post.id,
                "caption": post.caption,
                "type": post.type,
                "media": [
                    {
                        "url": m.media_url,
                        "type": m.media_type
                    } for m in post.media
                ]
            } for post in posts
        ],

        "posts_count": len(posts)
    })

@app.route('/')
def home():
    return jsonify({"status": "Lovora backend running 🚀"})

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
