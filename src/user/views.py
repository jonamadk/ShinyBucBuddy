from flask import Blueprint, request, jsonify
from .models import User
from extensions import db, limiter
from marshmallow import Schema, fields, ValidationError, validates
import hashlib
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from ragapp.models import ChatConversation
import json
import re
import logging
from .serializers   import UserSchema

user_bp = Blueprint('user', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

user_schema = UserSchema()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()



@user_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def create_user():
    data = request.get_json()
    # Set context for confirm_password validation
    schema = user_schema
    schema.context = {'password': data.get('password')}
    errors = schema.validate(data)
    if errors:
        return jsonify(errors), 400

    hashed_password = hash_password(data['password'])
    user = User(
        email=data['email'],
        password=hashed_password,
        firstname=data.get('firstname'),
        lastname=data.get('lastname'),
        auth_provider='email'
    )
    db.session.add(user)
    db.session.commit()
    logger.info(f"User created: {data['email']}")
    return jsonify({'message': 'User created successfully'}), 201

@user_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login_user():
    data = request.get_json()
    try:
        email = data['email']
        password = data['password']
    except KeyError:
        logger.error("Login failed: Email and password are required")
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email, auth_provider='email').first()
    if not user or not user.password:
        logger.error(f"Login failed for {email}: Invalid email or Google auth required")
        return jsonify({'error': 'Invalid email or password. Use Google login if registered with Google.'}), 401

    hashed_password = hash_password(password)
    if user.password != hashed_password:
        logger.error(f"Login failed for {email}: Invalid password")
        return jsonify({'error': 'Invalid email or password'}), 401

    user.signinstatus = True
    db.session.commit()

    access_token = create_access_token(
        identity=json.dumps({"email": user.email}),
        expires_delta=timedelta(days=3)
    )

    user_data = {
        'email': user.email,
        'firstname': user.firstname,
        'lastname': user.lastname,
        'signinstatus': user.signinstatus,
        'auth_provider': user.auth_provider
    }

    logger.info(f"User logged in: {email}")
    return jsonify({
        'access_token': access_token,
        'user': user_data,
        'message': 'Login successful'
    }), 200

@user_bp.route('/auth/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Retrieve all conversations for the authenticated user."""
    try:
        identity = json.loads(get_jwt_identity())
        useremail = identity.get("email")
        user = User.query.filter_by(email=useremail).first()
        if not user or not user.signinstatus:
            logger.error(f"User not logged in: {useremail}")
            return jsonify({"error": "User not logged in"}), 401

        conversations = ChatConversation.query.filter_by(useremail=useremail).order_by(ChatConversation.created_at.desc()).all()
        conversations_data = [
            {
                "conversationId": str(conversation.conversationid),
                "title": conversation.title,
                "created_at": conversation.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for conversation in conversations
        ]

        logger.info(f"Retrieved {len(conversations_data)} conversations for user {useremail}")
        return jsonify({"conversations": conversations_data}), 200
    except Exception as e:
        logger.error(f"Error retrieving conversations: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error retrieving conversations: {str(e)}"}), 500