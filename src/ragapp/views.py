from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from user.models import User
from datetime import datetime
from .responseLLM import ResponseLLM
from .responselog import ResponseLogger
from .embedDoc import process_and_push_data_to_chromadb
import chromadb
from extensions import db
from .models import ChatHistory, ChatConversation, UnauthenticatedSession
import json
# Check ChromaDB connectivity by attempting a simple operation
from chromadb.config import Settings
from chromadb import HttpClient


ragapp_bp = Blueprint('ragapp', __name__)

# Initialize ResponseLLM and ResponseLogger
response_llm = ResponseLLM()
response_logger = ResponseLogger(response_file="logs/responselogs/response_data.json",
                                 timestamp_file="logs/responselogs/response_timestamp.json")

# Health Check Endpoint for ChromaServer Not PersitentDB


@ragapp_bp.route('/health', methods=['GET'])
def health_check():
    """Check if the API and its dependencies are running."""
    try:
        health_status = {"status": "healthy", "message": "API is running"}
        chroma_client = HttpClient(
            host="chroma",
            port=8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )

        chroma_client.get_or_create_collection(name="health_check_collection")
        health_status["chromadb"] = "connected"
    except Exception as e:
        health_status = {
            "status": "unhealthy",
            "message": f"API is running, but ChromaDB is not accessible: {str(e)}"
        }
        return jsonify(health_status), 503

    return jsonify(health_status), 200

# Embed Documents Endpoint


@ragapp_bp.route('/embed', methods=['POST'])
def embed_documents():
    """Trigger document embedding process."""
    try:
        result = process_and_push_data_to_chromadb()
        return jsonify({"message": result}), 200
    except FileNotFoundError:
        return jsonify({"error": "Input file not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500

# Chat Endpoint


@ragapp_bp.route('/chat', methods=['POST'])
def chat():
    """Handle user queries and maintain conversation history."""
    session.permanent = True
    data = request.get_json()
    userquery = data.get("userquery")
    conversation_id = data.get("conversation_id")  # Optional: frontend passes it if continuing a chat
    conversation_id = int(conversation_id) if conversation_id else None
    session_id = session.sid  # Get the session ID

    if not userquery:
        return jsonify({"error": "Query is required"}), 400

    try:
        # Handle new conversation
        if not conversation_id:
            # Create a new conversation in the database
            new_conversation = ChatConversation(
                useremail=None,  # Set to None for unauthenticated users
                title=userquery[:50],  # Use the first query as the title
                created_at=datetime.utcnow()
            )
            db.session.add(new_conversation)
            db.session.flush()  # Flush to get the new conversation ID
            conversation_id = new_conversation.conversationid

        # Handle existing conversation
        else:
            # Retrieve the conversation from the database
            existing_conversation = ChatConversation.query.filter_by(
                conversationid=conversation_id
            ).first()
            if not existing_conversation:
                return jsonify({"error": "Conversation history not found"}), 404

        # Retrieve the last 4 user queries from the database
        history_userquery = [
            history.userquery for history in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.desc()).limit(4)
        ]

        # Get LLM response
        llmresponse, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
            userquery, history_userquery
        )

        # Save the query and response in the database
        new_history = ChatHistory(
            conversationid=conversation_id,
            useremail=None,  # Set to None for unauthenticated users
            userquery=userquery,
            llmresponse=llmresponse,
            top_n_document=top_n_document,
            citation_data=citation_data,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_history)
        db.session.commit()

        # Retrieve the full conversation history for the response
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

        # Log the response data
        response_logger.append_to_json_file(response_data)

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# Authenticated Chat Endpoint
@ragapp_bp.route('/auth/chat', methods=['POST'])
@jwt_required()
def auth_chat():
    """Authenticated chat endpoint with conversation support."""
    session.permanent = True
    data = request.get_json()
    userquery = data.get("userquery")
    # Optional: frontend passes it if continuing a chat
    conversation_id = data.get("conversation_id")

    if not userquery:
        return jsonify({"error": "Query is required"}), 400

    # Decode JWT
    try:
        identity = json.loads(get_jwt_identity())
        useremail = identity.get("email")
        user = User.query.filter_by(email=useremail).first()
    except Exception as e:
        return jsonify({"error": f"Invalid token or user lookup failed: {str(e)}"}), 401

    if not user or not user.signinstatus:
        return jsonify({"error": "User not logged in"}), 401

    time_is = datetime.now()
    formatted_time = time_is.strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Create new conversation if one doesn't exist
        history_userquery = []  # Initialize history_userquery
        if not conversation_id:
            new_conversation = ChatConversation(
                useremail=useremail,
                title="New Chat",  # Or auto-generate from userquery if you want
                created_at=formatted_time
            )
            db.session.add(new_conversation)
            db.session.flush()  # Flush to get new ID before commit
            conversation_id = new_conversation.conversationid
        else:
            # Ensure conversation exists and belongs to the user
            existing_conversation = ChatConversation.query.filter_by(
                conversationid=conversation_id, useremail=useremail
            ).first()
            if not existing_conversation:
                return jsonify({"error": "Conversation not found"}), 404

            # Retrieve the last 4 userquery entries from ChatHistory for this conversation
            history_userquery = [
                history.userquery for history in ChatHistory.query.filter_by(
                    conversationid=conversation_id
                ).order_by(ChatHistory.timestamp.desc()).limit(4).all()
            ]

        # Get LLM response
        llmresponse, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
            userquery, history_userquery
        )

        # Store in chat history
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
            "query-timestamp": formatted_time
        }]}

        db.session.add(chat_history)
        db.session.commit()

        response_data = {

            "user_type": "Authenticated",
            "conversation_id": conversation_id,
            "conversation_history": conversation_history,
            "token-details": token_details,
            "documents": top_n_document,

        }

        response_logger.append_to_json_file(response_data)
        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
