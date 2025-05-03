from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from user.models import User
from datetime import datetime
from .responseLLM import ResponseLLM
from .responselog import ResponseLogger
from extensions import db
from .models import ChatHistory, ChatConversation, UnauthenticatedSession
import json
import logging
from extensions import limiter

ragapp_bp = Blueprint('ragapp', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize ResponseLLM and ResponseLogger
response_llm = ResponseLLM()
response_logger = ResponseLogger(response_file="logs/responselogs/response_data.json",
                                 timestamp_file="logs/responselogs/response_timestamp.json")


'''
USER BASED RATE LIMITOR, ALTERNATIVE TO IP BASED
def get_user_email():
    try:
        identity = json.loads(get_jwt_identity())
        return identity.get("email", "anonymous")
    except:
        return "anonymous"
IMPLEMENTATION: @limiter.limit("10 per minute", key_func=get_user_email) 
'''



@ragapp_bp.route('/chat', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per minute")
def chat():
    """Handle user queries and maintain conversation history."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    session.permanent = True
    data = request.get_json()
    userquery = data.get("userquery")
    conversation_id = data.get("conversation_id")
    conversation_id = int(conversation_id) if conversation_id else None
    session_id = session.sid

    if not userquery:
        logger.error("No user query provided")
        return jsonify({"error": "Query is required"}), 400

    try:
        if not conversation_id:
            new_conversation = ChatConversation(
                useremail=None,
                title=userquery[:50],
                created_at=datetime.utcnow()
            )
            db.session.add(new_conversation)
            db.session.flush()
            conversation_id = new_conversation.conversationid
            logger.debug(f"Created new conversation: {conversation_id}")
        else:
            existing_conversation = ChatConversation.query.filter_by(
                conversationid=conversation_id
            ).first()
            if not existing_conversation:
                logger.error(f"Conversation {conversation_id} not found")
                return jsonify({"error": "Conversation history not found"}), 404

        history_userquery = [
            history.userquery for history in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.desc()).limit(3)
        ]

        llmresponse, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
            userquery, history_userquery
        )

        new_history = ChatHistory(
            conversationid=conversation_id,
            useremail=None,
            userquery=userquery,
            llmresponse=llmresponse,
            top_n_document=top_n_document,
            citation_data=citation_data,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_history)
        db.session.commit()
        logger.debug(f"Saved chat history for conversation {conversation_id}")

        conversation_history = [
            {
                "userquery": history.userquery,
                "llmresponse": history.llmresponse,
                "timestamp": history.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            for history in ChatHistory.query.filter_by(conversationid=conversation_id)
            .order_by(ChatHistory.timestamp.asc())
        ]

        response_data = {
            "user_type": "Un-Authenticated",
            "conversation_id": conversation_id,
            "conversation_history": {str(conversation_id): conversation_history},
            "token-details": token_details,
            "documents": top_n_document,
            
        }

        response_logger.append_to_json_file(response_data)
        logger.info(f"Chat response generated for conversation {conversation_id}")
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@ragapp_bp.route('/auth/chat', methods=['POST', 'OPTIONS'])
@limiter.limit("30 per minute")
def auth_chat():
    """Authenticated chat endpoint with conversation support."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    @jwt_required()
    def handle_post():
        session.permanent = True
        data = request.get_json()
        userquery = data.get("userquery")
        conversation_id = data.get("conversation_id")

        if not userquery:
            logger.error("No user query provided for authenticated chat")
            return jsonify({"error": "Query is required"}), 400

        try:
            identity = json.loads(get_jwt_identity())
            useremail = identity.get("email")
            user = User.query.filter_by(email=useremail).first()
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}", exc_info=True)
            return jsonify({"error": f"Invalid token or user lookup failed: {str(e)}"}), 401

        if not user or not user.signinstatus:
            logger.error(f"User not logged in: {useremail}")
            return jsonify({"error": "User not logged in"}), 401

        time_is = datetime.now()
        formatted_time = time_is.strftime("%Y-%m-%d %H:%M:%S")
        try:
            history_userquery = []
            if not conversation_id:
                new_conversation = ChatConversation(
                    useremail=useremail,
                    title=userquery[:50],
                    created_at=formatted_time
                )
                db.session.add(new_conversation)
                db.session.flush()
                conversation_id = new_conversation.conversationid
                logger.debug(f"Created new authenticated conversation: {conversation_id}")
            else:
                existing_conversation = ChatConversation.query.filter_by(
                    conversationid=conversation_id, useremail=useremail
                ).first()
                if not existing_conversation:
                    logger.error(f"Authenticated conversation {conversation_id} not found for {useremail}")
                    return jsonify({"error": "Conversation not found"}), 404

                history_userquery = [
                    history.userquery for history in ChatHistory.query.filter_by(
                        conversationid=conversation_id
                    ).order_by(ChatHistory.timestamp.desc()).limit(3).all()
                ]

            llmresponse, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
                userquery, history_userquery
            )

            chat_history = ChatHistory(
                useremail=user.email,
                conversationid=conversation_id,
                userquery=userquery,
                llmresponse=llmresponse,
                top_n_document=top_n_document,
                citation_data=citation_data,
                timestamp=formatted_time
            )

            conversation_history = {chat_history.conversationid: [{
                "userquery": userquery,
                "llmresponse": llmresponse,
                "query-timestamp": formatted_time,
                "user": user.email
            }]}

            db.session.add(chat_history)
            db.session.commit()
            logger.debug(f"Saved authenticated chat history for conversation {conversation_id}")

            response_data = {
                "user_type": "Authenticated",
                "user": user.email,
                "conversation_id": conversation_id,
                "conversation_history": conversation_history,
                "token-details": token_details,
                "documents": top_n_document,
            }

            response_logger.append_to_json_file(response_data)
            logger.info(f"Authenticated chat response generated for conversation {conversation_id}")
            return jsonify(response_data), 200

        except Exception as e:
            logger.error(f"Authenticated chat error: {str(e)}", exc_info=True)
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    return handle_post()

@ragapp_bp.route('/conversation/<int:conversation_id>/history', methods=['GET'])
@jwt_required(optional=True)
def get_conversation_history(conversation_id):
    """Retrieve chat history for a specific conversation ID, with user validation for authenticated requests."""
    try:
        # Check if user is authenticated
        useremail = None
        identity = get_jwt_identity()
        if identity:
            identity_data = json.loads(identity)
            useremail = identity_data.get("email")
            user = User.query.filter_by(email=useremail).first()
            if not user or not user.signinstatus:
                logger.error(f"User not logged in: {useremail}")
                return jsonify({"error": "User not logged in"}), 401

        # Fetch conversation
        conversation = ChatConversation.query.filter_by(conversationid=conversation_id).first()
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return jsonify({"error": "Conversation not found"}), 404

        # For authenticated users, verify conversation ownership
        if useremail and conversation.useremail and conversation.useremail != useremail:
            logger.error(f"User {useremail} not authorized for conversation {conversation_id}")
            return jsonify({"error": "Not authorized to access this conversation"}), 403

        # Fetch chat history
        chat_history = ChatHistory.query.filter_by(conversationid=conversation_id).order_by(ChatHistory.timestamp.asc()).all()
        if not chat_history:
            logger.error(f"Conversation history not found for ID {conversation_id}")
            return jsonify({"error": "Conversation history not found"}), 404

        conversation_history = [
            {
                "userquery": history.userquery,
                "llmresponse": history.llmresponse,
                "timestamp": history.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            for history in chat_history
        ]

        logger.info(f"Retrieved conversation history for ID {conversation_id}")
        return jsonify({"conversation_id": conversation_id, "conversation_history": conversation_history}), 200

    except Exception as e:
        logger.error(f"Conversation history error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500