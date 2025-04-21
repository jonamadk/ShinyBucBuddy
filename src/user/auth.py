from flask import Blueprint, redirect, url_for, jsonify, session, request, current_app
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token
from .models import db, User
import os
import secrets
import logging
import time
import json
from datetime import timedelta
logger = logging.getLogger(__name__)
from flask_cors import CORS

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()


CORS(auth_bp, supports_credentials=True)

def init_oauth(app):
    """Initialize OAuth with the Flask app."""
    oauth.init_app(app)

    # Register Google OAuth
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url=os.getenv('GOOGLE_DISCOVERY_URL'),
        client_kwargs={
            'scope': 'openid email profile',
            'prompt': 'select_account',  # Force account selection
        }
    )


@auth_bp.route('/auth/login')
def google_login():
    """Redirect to Google for login."""
    # Generate a unique state parameter for CSRF protection
    state = secrets.token_urlsafe(16)

    # Store state in session with timestamp
    session.clear()  # Clear any existing session data
    session['oauth_state'] = state
    session['oauth_state_time'] = time.time()

    # Create the redirect URI
    redirect_uri = url_for('auth.google_callback', _external=True)
    logger.info(f"Login - Redirect URI: {redirect_uri}")
    logger.info(f"Login - State: {state}")
    logger.info(
        f"Login - Session ID: {session.sid if hasattr(session, 'sid') else 'No SID'}")

    # Store all session data for debugging
    logger.info(f"Login - Full session: {session}")

    return oauth.google.authorize_redirect(redirect_uri, state=state)


@auth_bp.route('/auth/callback')
def google_callback():
    """Handle callback from Google after authentication."""
    try:
        logger.info(f"Callback - Request args: {request.args}")
        logger.info(f"Callback - Session: {session}")
        logger.info(
            f"Callback - Session ID: {session.sid if hasattr(session, 'sid') else 'No SID'}")

        # Get and verify state parameter
        request_state = request.args.get('state')
        session_state = session.get('oauth_state')

        logger.info(f"Callback - Request state: {request_state}")
        logger.info(f"Callback - Session state: {session_state}")

        if not session_state:
            logger.error("No state found in session")
            return jsonify({"error": "No state found in session"}), 400

        if request_state != session_state:
            logger.error(f"State mismatch: {request_state} vs {session_state}")
            return jsonify({"error": "Invalid state parameter"}), 400

        # Get auth code from request
        code = request.args.get('code')
        if not code:
            logger.error("No auth code in request")
            return jsonify({"error": "No authorization code received"}), 400

        # Exchange the auth code for a token
        logger.info("About to get access token")
        token = oauth.google.authorize_access_token()
        logger.info("Token obtained successfully")

        # Get the nonce from the session
        state_key = f"_state_google_{request_state}"
        state_data = session.get(state_key, {})
        nonce = state_data.get('data', {}).get(
            'nonce') if isinstance(state_data, dict) else None

        logger.info(f"Retrieved nonce: {nonce}")

        # Get user info from the token with the nonce
        user_info = oauth.google.parse_id_token(token, nonce=nonce)
        if not user_info:
            logger.error("Failed to parse ID token")
            return jsonify({"error": "Failed to get user info"}), 400

        logger.info(f"User info obtained: {user_info.get('email')}")

        # Check if user exists in the database
        user = User.query.filter_by(email=user_info.get('email')).first()
        if not user:
            # Create new user if not found
            user = User(
                firstname=user_info.get('given_name', ''),
                lastname=user_info.get('family_name', ''),
                email=user_info.get('email'),
                password=''  # Placeholder; password not needed for OAuth
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"New user created: {user.email}")
        else:
            logger.info(f"Existing user found: {user.email}")

        # Create a JWT token
        access_token = create_access_token(
        identity=json.dumps({"email": user.email}),
        expires_delta=timedelta(days=3)
    )

        return jsonify({
            "access_token": access_token,
            "user": {
                "email": user.email,
                "firstname": user.firstname,
                "lastname": user.lastname
            }
        })                                                                                                                                                                                                                                                      

    except Exception as e:
        logger.error(f"Error in callback: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
