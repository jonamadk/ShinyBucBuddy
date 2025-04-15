from extensions import db


class User(db.Model):
    __tablename__ = "users"

    email = db.Column(db.String(120), primary_key=True,
                      unique=True, nullable=False)  # email as primary key
    password = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(100), nullable=True)
    lastname = db.Column(db.String(100), nullable=True)
    signinstatus = db.Column(db.Boolean, default=False, nullable=True)

    def to_dict(self):
        return {
            "email": self.email,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "signinstatus": self.signinstatus
        }
