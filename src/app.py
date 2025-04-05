from flask import Flask
from flask_cors import CORS
from ragapp import ragapp_bp
import os
import logging

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Register Blueprints
app.register_blueprint(ragapp_bp)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
