from flask import Blueprint, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token
from .models import db, User
import os

auth_bp = Blueprint('auth', __name__)

# Initialize OAuth
oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth with the Flask app."""
    oauth.init_app(app)


google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url=os.getenv('GOOGLE_DISCOVERY_URL'),
    client_kwargs={
        'scope': 'openid email profile',
    }
)


@auth_bp.route('/auth/login')
def google_login():
    """Redirect to Google for login."""
    redirect_uri = url_for('auth.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/callback')
def google_callback():
    """Handle Google OAuth callback."""
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token)

    # Check if user exists in the database
    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        # Create a new user if not found
        user = User(
            username=user_info['name'],
            email=user_info['email'],
            password=''  # No password for Google login
        )
        db.session.add(user)
        db.session.commit()

    # Generate JWT token for the user
    access_token = create_access_token(
        identity={"id": user.id, "email": user.email})

    return jsonify({
        "access_token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    })
