from flask import Blueprint, request, jsonify
from .models import User
from extensions import db
from marshmallow import Schema, fields, ValidationError, validates
import hashlib
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies
from datetime import timedelta
from ragapp.models import ChatConversation
import json
import re
import logging

user_bp = Blueprint('user', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class UserSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    confirm_password = fields.Str(required=True, load_only=True)
    firstname = fields.Str(required=False, allow_none=True)
    lastname = fields.Str(required=False, allow_none=True)

    @validates('email')
    def validate_email(self, value, **kwargs):
        if User.query.filter_by(email=value).first():
            raise ValidationError('Email already exists')

    @validates('password')
    def validate_password(self, value, **kwargs):
        if len(value) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not re.search(r'[0-9]', value):
            raise ValidationError('Password must contain at least one number')

    @validates('confirm_password')
    def validate_confirm_password(self, value, **kwargs):
        if value != self.context.get('password'):
            raise ValidationError('Passwords do not match')

user_schema = UserSchema()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@user_bp.route('/register', methods=['POST'])
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


@user_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout the user by revoking the token and updating signin status."""
    try:
        identity = get_jwt_identity()

        # Handle both cases: email as plain string or JSON string with "email" key
        try:
            # Attempt to parse as JSON object (for normal login)
            identity_data = json.loads(identity)
            user_email = identity_data.get("email")
        except (json.JSONDecodeError, TypeError):
            # If parsing fails, assume identity is directly the email (for OAuth login)
            user_email = identity

        if not user_email:
            return jsonify({"error": "Invalid token format"}), 400

        # Query the user by email
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        user.signinstatus = False
        db.session.commit()

        response = jsonify({"message": "User logged out successfully"})
        unset_jwt_cookies(response)

        return response, 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



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