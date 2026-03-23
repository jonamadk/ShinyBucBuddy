from flask import Blueprint, request, jsonify, redirect, session
from flask_jwt_extended import create_access_token
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import google_auth_oauthlib.flow
from .models import User
from extensions import db
import os
import json
from urllib.parse import quote
from dotenv import load_dotenv
from datetime import timedelta

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

load_dotenv()

auth_bp = Blueprint('auth', __name__)

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8000/api/auth/callback"
FRONTEND_REDIRECT_URI = "http://localhost:3000/signin"
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

@auth_bp.route('auth/login')
def login_with_google():
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Store state in session
    session['oauth_state'] = state

    # Store code_verifier if PKCE was used
    cv = getattr(flow, '_code_verifier', None) or getattr(flow, 'code_verifier', None)
    if cv:
        session['code_verifier'] = cv

    return redirect(authorization_url)


@auth_bp.route('auth/callback')
def auth_callback():
    try:
        state = session.get('oauth_state', request.args.get('state'))
        code_verifier = session.get('code_verifier')

        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state
        )

        # Restore code_verifier so fetch_token can use it
        if code_verifier:
            flow.code_verifier = code_verifier

        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        token_request = google_requests.Request()
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, token_request, GOOGLE_CLIENT_ID)

        email = id_info.get("email")
        firstname = id_info.get("given_name")
        lastname = id_info.get("family_name")

        user = User.query.filter_by(email=email).first()
        if user:
            user.signinstatus = True
            db.session.commit()
        else:
            user = User(
                email=email,
                password=None,
                firstname=firstname,
                lastname=lastname,
                signinstatus=True,
                auth_provider='google'
            )
            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(
            identity=json.dumps({"email": user.email}),
            expires_delta=timedelta(days=3)
        )

        user_data = {
            "email": user.email,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "signinstatus": user.signinstatus,
            "auth_provider": user.auth_provider
        }

        session.pop('oauth_state', None)
        session.pop('code_verifier', None)

        return redirect(f"{FRONTEND_REDIRECT_URI}?user={quote(json.dumps(user_data))}&token={access_token}")

    except Exception as e:
        return jsonify({"error": f"Google OAuth failed: {str(e)}"}), 500