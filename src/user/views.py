from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError
from datetime import timedelta
from extensions import db
from .models import User
from .serializers import UserSchema
import bcrypt
import json
from ragapp.models import ChatHistory
from ragapp.serializers import ChatHistorySchema

user_bp = Blueprint('user', __name__)
user_schema = UserSchema()
users_schema = UserSchema(many=True)


@user_bp.route('/register', methods=['POST'])
def create_user():
    """Register a new user."""
    data = request.get_json()
    errors = user_schema.validate(data)
    if errors:
        return jsonify(errors), 400

    try:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({"error": "Email already exists"}), 400

        # Hash the password before storing it
        hashed_password = bcrypt.hashpw(
            data['password'].encode('utf-8'), bcrypt.gensalt())

        new_user = User(

            email=data['email'],
            password=hashed_password.decode('utf-8'),
            firstname=data.get('firstname'),    # New field
            # Changed from last_name to lastname
            lastname=data.get('lastname'),
            signinstatus=False
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify(user_schema.dump(new_user)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/login', methods=['POST'])
def login():
    try:
        verify_jwt_in_request()
        current_user = get_jwt_identity()
        if current_user:
            return jsonify({"message": "User already logged in", "user": current_user}), 200
    except NoAuthorizationError:
        pass  # No valid token found, proceed with login

    # Continue with normal login
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # Query the user by email
    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        return jsonify({"error": "Invalid email or password"}), 401

    # Generate JWT token with 3 days expiry
    access_token = create_access_token(
        identity=json.dumps({"email": user.email}),
        expires_delta=timedelta(days=3)
    )
    user.signinstatus = True
    db.session.commit()
   
    

    # Fetch user's chat history
    try:
        chat_history = ChatHistory.query.filter_by(
            useremail=user.email)
        
        chat_history = ChatHistory.query.filter_by(
            useremail=user.email).order_by(ChatHistory.timestamp.desc()).all()
        chat_history_schema = ChatHistorySchema(many=True)
        chat_history_data = chat_history_schema.dump(chat_history)
    except:
        chat_history_data = None
        
    # Return the token, user details, and chat history
    return jsonify({
        "access_token": access_token,
        "user": {
            "email": user.email,
            "signinstatus": user.signinstatus,
            "firstname": user.firstname,
            "lastname": user.lastname,
       
        },
        "chat_history": chat_history_data
    }), 200


@user_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """Retrieve all users (auth required)."""
    users = User.query.all()
    return users_schema.jsonify(users), 200


@user_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Retrieve a single user by ID (auth required)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return user_schema.jsonify(user), 200


@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update an existing user's details, including password."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    errors = user_schema.validate(data, partial=True)
    if errors:
        return jsonify(errors), 400

    try:

        user.email = data.get('email', user.email)
        user.firstname = data.get('firstname', user.firstname)  # New field
        # Changed from last_name to lastname
        user.lastname = data.get('lastname', user.lastname)

        # If a new password is provided, hash it before saving
        if 'password' in data:
            hashed_password = bcrypt.hashpw(
                data['password'].encode('utf-8'), bcrypt.gensalt())
            user.password = hashed_password.decode(
                'utf-8')  # Store as a string

        db.session.commit()
        return jsonify(user_schema.dump(user)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete a user by ID (auth required)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
