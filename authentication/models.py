from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    forename = db.Column(db.String(255), nullable=False)
    surname = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(64), nullable=False)


