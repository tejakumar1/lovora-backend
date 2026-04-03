from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask import url_for
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
    user = db.relationship('User', backref='comments')

class SavedPost(db.Model):
    __tablename__ = "saved_posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_saved_post'),
    )
otp_store = {}




@app.route('/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({"error": "Post not found"}), 404

        existing = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
        if existing:
            likes_count = Like.query.filter_by(post_id=post_id).count()
            return jsonify({
                "success": True,
                "liked": True,
                "likes_count": likes_count
            })

        db.session.add(Like(user_id=user_id, post_id=post_id))
        db.session.commit()

        likes_count = Like.query.filter_by(post_id=post_id).count()

        return jsonify({
            "success": True,
            "liked": True,
            "likes_count": likes_count
        })
    except Exception as e:
        print("LIKE ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/posts/<int:post_id>/like', methods=['DELETE'])
def unlike_post(post_id):
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()

        if like:
            db.session.delete(like)
            db.session.commit()

        likes_count = Like.query.filter_by(post_id=post_id).count()

        return jsonify({
            "success": True,
            "liked": False,
            "likes_count": likes_count
        })
    except Exception as e:
        print("UNLIKE ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({"error": "Post not found"}), 404

        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()

        return jsonify([
            {
                "id": c.id,
                "text": c.text,
                "created_at": c.created_at.isoformat(),
                "user": {
                    "id": c.user.id,
                    "username": c.user.username
                }
            }
            for c in comments
        ])
    except Exception as e:
        print("GET COMMENTS ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")
        text = (data.get("text") or "").strip()

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if not text:
            return jsonify({"error": "Comment text is required"}), 400

        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({"error": "Post not found"}), 404

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        comment = Comment(
            user_id=user_id,
            post_id=post_id,
            text=text
        )

        db.session.add(comment)
        db.session.commit()

        comments_count = Comment.query.filter_by(post_id=post_id).count()

        return jsonify({
            "success": True,
            "comments_count": comments_count,
            "comment": {
                "id": comment.id,
                "text": comment.text,
                "created_at": comment.created_at.isoformat(),
                "user": {
                    "id": user.id,
                    "username": user.username
                }
            }
        })
    except Exception as e:
        print("ADD COMMENT ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/posts/<int:post_id>/save', methods=['POST'])
def save_post(post_id):
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({"error": "Post not found"}), 404

        existing = SavedPost.query.filter_by(user_id=user_id, post_id=post_id).first()

        if existing:
            return jsonify({"success": True, "saved": True})

        db.session.add(SavedPost(user_id=user_id, post_id=post_id))
        db.session.commit()

        return jsonify({"success": True, "saved": True})
    except Exception as e:
        print("SAVE ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/posts/<int:post_id>/save', methods=['DELETE'])
def unsave_post(post_id):
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        saved = SavedPost.query.filter_by(user_id=user_id, post_id=post_id).first()

        if saved:
            db.session.delete(saved)
            db.session.commit()

        return jsonify({"success": True, "saved": False})
    except Exception as e:
        print("UNSAVE ERROR:", e)
        return jsonify({"error": str(e)}), 500

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

# FLUTTER-COMPATIBLE ENDPOINTS (Fixes your 404 errors)
@app.route('/like-post', methods=['POST', 'OPTIONS'])
def like_post_simple():
    data = request.get_json() or {}
    post_id = data.get("post_id")
    user_id = data.get("user_id")
    
    if not post_id or not user_id:
        return jsonify({"error": "post_id and user_id required"}), 400
    
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    
    existing = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing:
        likes_count = Like.query.filter_by(post_id=post_id).count()
        return jsonify({"success": True, "already_liked": True, "likes_count": likes_count})
    
    db.session.add(Like(user_id=user_id, post_id=post_id))
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "liked": True, 
        "likes_count": Like.query.filter_by(post_id=post_id).count()
    })

@app.route('/add-comment', methods=['POST', 'OPTIONS'])
def add_comment_simple():
    data = request.get_json() or {}
    post_id = data.get("post_id")
    user_id = data.get("user_id")
    text = (data.get("text") or "").strip()
    
    if not all([post_id, user_id, text]):
        return jsonify({"error": "Missing required fields"}), 400
    
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    
    comment = Comment(user_id=user_id, post_id=post_id, text=text)
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "comment_id": comment.id,
        "comments_count": Comment.query.filter_by(post_id=post_id).count()
    })

@app.route('/share/post/<int:post_id>', methods=['GET'])
def share_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404

    return jsonify({
        "post_id": post.id,
        "username": post.user.username,
        "caption": post.caption,
        "type": post.type,
        "media": [
            {"url": m.media_url, "type": m.media_type}
            for m in post.media
        ],

    "share_url": url_for("share_post", post_id=post.id, _external=True)    })

@app.route('/')
def home():
    return jsonify({"status": "Lovora backend running 🚀"})

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
