from flask import Flask
from flask_cors import CORS
from flask_session import Session  # Add this import
from ragapp import ragapp_bp
# Import models explicitly to ensure they're registered
from ragapp.models import ChatHistory  # Add this import
from user.views import user_bp
from user.auth import auth_bp, init_oauth
from extensions import init_extensions, db
import os
import logging
import tempfile  # For temporary session files
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Session configuration (important for OAuth)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configure server-side sessions
app.config['SESSION_TYPE'] = 'filesystem'
# Temporary directory for sessions
app.config['SESSION_FILE_DIR'] = tempfile.mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
Session(app)  # Initialize Flask-Session

# Configure JWT
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('POSTGRES_DB_URL')

# Initialize extensions
init_extensions(app)

# Initialize OAuth
init_oauth(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Register Blueprints
app.register_blueprint(ragapp_bp)
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api')

# Create database schema
with app.app_context():
    db.create_all()
    print("Database schema created successfully!")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
