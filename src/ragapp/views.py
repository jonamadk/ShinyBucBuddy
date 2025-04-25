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
from chromadb.config import Settings
from chromadb import HttpClient

ragapp_bp = Blueprint('ragapp', __name__)

# Initialize ResponseLLM and ResponseLogger
response_llm = ResponseLLM()
response_logger = ResponseLogger(response_file="logs/responselogs/response_data.json",
                                 timestamp_file="logs/responselogs/response_timestamp.json")

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

@ragapp_bp.route('/chat', methods=['POST', 'OPTIONS'])
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

        else:
            existing_conversation = ChatConversation.query.filter_by(
                conversationid=conversation_id
            ).first()
            if not existing_conversation:
                return jsonify({"error": "Conversation history not found"}), 404

        history_userquery = [
            history.userquery for history in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.desc()).limit(4)
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
        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@ragapp_bp.route('/auth/chat', methods=['POST', 'OPTIONS'])
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
            return jsonify({"error": "Query is required"}), 400

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
            else:
                existing_conversation = ChatConversation.query.filter_by(
                    conversationid=conversation_id, useremail=useremail
                ).first()
                if not existing_conversation:
                    return jsonify({"error": "Conversation not found"}), 404

                history_userquery = [
                    history.userquery for history in ChatHistory.query.filter_by(
                        conversationid=conversation_id
                    ).order_by(ChatHistory.timestamp.desc()).limit(4).all()
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

            response_data = {
                "user_type": "Authenticated",
                "user": user.email,
                "conversation_id": conversation_id,
                "conversation_history": conversation_history,
                "token-details": token_details,
                "documents": top_n_document,
            }

            response_logger.append_to_json_file(response_data)
            return jsonify(response_data), 200

        except Exception as e:
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    return handle_post()

@ragapp_bp.route('/conversation/<int:conversation_id>/history', methods=['GET'])
def get_conversation_history(conversation_id):
    """Retrieve chat history for a specific conversation ID."""
    try:
        chat_history = ChatHistory.query.filter_by(conversationid=conversation_id).order_by(ChatHistory.timestamp.asc()).all()

        if not chat_history:
            return jsonify({"error": "Conversation history not found"}), 404

        conversation_history = [
            {
                "userquery": history.userquery,
                "llmresponse": history.llmresponse,
                "timestamp": history.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            for history in chat_history
        ]

        return jsonify({"conversation_id": conversation_id, "conversation_history": conversation_history}), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500