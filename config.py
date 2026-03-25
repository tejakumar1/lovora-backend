from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

SQLALCHEMY_DATABASE_URI = "postgresql://postgres:password@localhost:5432/lovora_db"
SQLALCHEMY_TRACK_MODIFICATIONS = False