from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_session import Session
from ragapp.views import ragapp_bp
from ragapp.models import ChatHistory
from user.views import user_bp
from user.auth import auth_bp
from extensions import init_extensions, db
import os
import logging
import tempfile
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from datetime import timedelta
import chromadb
from chromadb.config import Settings

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure CORS for all routes
CORS(app, resources={
    r"/*": {
        "origins": "http://localhost:3000",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

chroma_client = chromadb.HttpClient(
    host="chroma",
    port=8000,
    settings=Settings(allow_reset=True, anonymized_telemetry=False)
)

# Session configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = tempfile.mkdtemp()
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
Session(app)

# Configure JWT
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('POSTGRES_DB_URL')

# Initialize extensions
init_extensions(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Register Blueprints
app.register_blueprint(ragapp_bp, url_prefix='/api')
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api')

# Handle OPTIONS requests for all endpoints
@app.before_request
def handle_options_request():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

# Custom 404 handler for API routes
@app.errorhandler(404)
def not_found(error):
    response = jsonify({"error": "Not Found", "message": "The requested API endpoint does not exist."})
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
    return response, 404

# Create database schema
with app.app_context():
    db.create_all()
    print("Database schema created successfully!")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)