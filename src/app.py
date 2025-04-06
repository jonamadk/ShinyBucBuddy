from flask import Flask
from flask_cors import CORS
from ragapp import ragapp_bp
from user.views import user_bp  # Import the user Blueprint
# Import the auth Blueprint and init_oauth
from user.auth import auth_bp, init_oauth
from extensions import init_extensions, db
import os
import logging
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure JWT
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv(
    'JWT_SECRET_KEY')  # Replace with a secure key
app.config['SECRET_KEY'] = os.getenv(
    'JWT_SECRET_KEY')  # Add SECRET_KEY configuration
jwt = JWTManager(app)

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'POSTGRES_DB_URL')

# Initialize extensions
init_extensions(app)

# Initialize OAuth
init_oauth(app)


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Register Blueprints
app.register_blueprint(ragapp_bp)
# Add a prefix for user routes
app.register_blueprint(user_bp, url_prefix='/api')
# Register the auth Blueprint
app.register_blueprint(auth_bp, url_prefix='/api')

# Create database schema
with app.app_context():
    db.create_all()
    print("Database schema created successfully!")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
