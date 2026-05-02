from extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"

    email = db.Column(db.String(120), primary_key=True,
                      unique=True, nullable=False)  # email as primary key
    password = db.Column(db.String(255), nullable=True)
    firstname = db.Column(db.String(100), nullable=True)
    lastname = db.Column(db.String(100), nullable=True)
    signinstatus = db.Column(db.Boolean, default=False, nullable=True)
    auth_provider = db.Column(db.String(50), nullable=False, default='email')  # Track auth method

    # FIX: Added for account lockout after failed login attempts
    failed_attempts = db.Column(db.Integer, default=0, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "email": self.email,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "signinstatus": self.signinstatus
        }