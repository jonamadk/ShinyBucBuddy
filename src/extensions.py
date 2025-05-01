from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


db = SQLAlchemy()

# Limiter setup
limiter = Limiter(
    key_func=get_remote_address,  # Fallback key func (IP based)
    default_limits=["25 per hour"],  # Global default if needed
)



def init_extensions(app):
    db.init_app(app)
    limiter.init_app(app)

