from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from user.models import User
from datetime import datetime
from .responseLLM import ResponseLLM
from .responselog import ResponseLogger
from extensions import db
from .models import ChatHistory, ChatConversation, UnauthenticatedSession, ChatFeedback
import json
import logging
from extensions import limiter

ragapp_bp = Blueprint('ragapp', __name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

response_llm = ResponseLLM()
response_logger = ResponseLogger(response_file="logs/responselogs/response_data.json",
                                 timestamp_file="logs/responselogs/response_timestamp.json")

def parse_conversation_id(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw == "" or raw.lower() in ("undefined", "null", "none"):
            return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


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
    conversation_id = parse_conversation_id(data.get("conversation_id"))
    user_consent = data.get("user_consent", None)  # Consent flag from frontend

    if not userquery:
        logger.error("No user query provided")
        return jsonify({"error": "Query is required"}), 400

    # --- Metric: record when prompt was received ---
    prompt_received_at = datetime.utcnow()

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

        full_conversation_history = [
            {
                "userquery": h.userquery,
                "llmresponse": h.llmresponse,
            }
            for h in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.asc()).all()
        ]

        llmresponse, top_5_retrieved, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
            userquery, history_userquery, conversation_history=full_conversation_history
        )

        # --- Metric: record when response was generated ---
        response_generated_at = datetime.utcnow()
        response_time_ms = (response_generated_at - prompt_received_at).total_seconds() * 1000

        # Extract token count from token_details
        token_count = token_details.get("Token Count") if isinstance(token_details, dict) else None

        new_history = ChatHistory(
            conversationid=conversation_id,
            useremail=None,
            userquery=userquery,
            llmresponse=llmresponse,
            top_5_retrieved=top_5_retrieved,
            top_n_document=top_n_document,
            citation_data=citation_data,
            prompt_received_at=prompt_received_at,
            response_generated_at=response_generated_at,
            response_time_ms=response_time_ms,
            timestamp=prompt_received_at,
            token_count=token_count,
            user_consent=user_consent,
        )
        db.session.add(new_history)

        # Update last_updated on the conversation — tracks session end time
        convo = ChatConversation.query.filter_by(conversationid=conversation_id).first()
        if convo:
            convo.last_updated = datetime.utcnow()

        db.session.commit()
        logger.debug(f"Saved chat history for conversation {conversation_id} — response time: {response_time_ms:.0f}ms")

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
        conversation_id = parse_conversation_id(data.get("conversation_id"))
        user_consent = data.get("user_consent", None)  # Consent flag from frontend

        if not userquery:
            logger.error("No user query provided for authenticated chat")
            return jsonify({"error": "Query is required"}), 400

        # --- Metric: record when prompt was received ---
        prompt_received_at = datetime.utcnow()

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

        formatted_time = prompt_received_at.strftime("%Y-%m-%d %H:%M:%S")

        try:
            history_userquery = []
            full_conversation_history = []

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

                full_conversation_history = [
                    {
                        "userquery": h.userquery,
                        "llmresponse": h.llmresponse,
                    }
                    for h in ChatHistory.query.filter_by(
                        conversationid=conversation_id
                    ).order_by(ChatHistory.timestamp.asc()).all()
                ]

            try:
                llmresponse, top_5_retrieved, top_n_document, citation_data, context_data, token_details = response_llm.generate_filtered_response(
                    userquery, history_userquery, conversation_history=full_conversation_history
                )
            except Exception as e:
                logger.error(f"LLM disabled/failing. Falling back without OpenAI. Error: {str(e)}", exc_info=True)
                llmresponse = (
                    "⚠️ LLM is currently disabled (no OpenAI key/quota). "
                    "The app is running locally, but I can't generate an AI answer right now."
                )
                top_5_retrieved = []
                top_n_document = []
                citation_data = []
                context_data = []
                token_details = {"llm": "disabled", "error": str(e)}

            # --- Metric: record when response was generated ---
            response_generated_at = datetime.utcnow()
            response_time_ms = (response_generated_at - prompt_received_at).total_seconds() * 1000

            # Extract token count from token_details
            token_count = token_details.get("Token Count") if isinstance(token_details, dict) else None

            chat_history = ChatHistory(
                useremail=user.email,
                conversationid=conversation_id,
                userquery=userquery,
                llmresponse=llmresponse,
                top_5_retrieved=top_5_retrieved,
                top_n_document=top_n_document,
                citation_data=citation_data,
                prompt_received_at=prompt_received_at,
                response_generated_at=response_generated_at,
                response_time_ms=response_time_ms,
                timestamp=prompt_received_at,
                token_count=token_count,
                user_consent=user_consent,
            )

            conversation_history = {chat_history.conversationid: [{
                "userquery": userquery,
                "llmresponse": llmresponse,
                "citation_data": citation_data,
                "query-timestamp": formatted_time,
                "user": user.email
            }]}

            db.session.add(chat_history)

            # Update last_updated on the conversation — tracks session end time
            convo = ChatConversation.query.filter_by(conversationid=conversation_id).first()
            if convo:
                convo.last_updated = datetime.utcnow()

            db.session.commit()
            logger.debug(f"Saved authenticated chat history for conversation {conversation_id} — response time: {response_time_ms:.0f}ms")

            response_data = {
                "user_type": "Authenticated",
                "user": user.email,
                "conversation_id": conversation_id,
                "conversation_history": conversation_history,
                "token-details": token_details,
                "documents": top_n_document,
                "citation_data": citation_data,
            }

            response_logger.append_to_json_file(response_data)
            logger.info(f"Authenticated chat response generated for conversation {conversation_id}")
            return jsonify(response_data), 200

        except Exception as e:
            logger.error(f"Authenticated chat error: {str(e)}", exc_info=True)
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    return handle_post()


@ragapp_bp.route('/auth/conversations', methods=['GET'])
@jwt_required()
def get_user_conversations():
    """Fetch all conversations for the authenticated user."""
    try:
        identity = json.loads(get_jwt_identity())
        useremail = identity.get("email")
        user = User.query.filter_by(email=useremail).first()
        if not user or not user.signinstatus:
            return jsonify({"error": "User not logged in"}), 401

        conversations = ChatConversation.query.filter_by(
            useremail=useremail
        ).order_by(ChatConversation.created_at.desc()).all()

        result = []
        for conv in conversations:
            result.append({
                "conversationid": conv.conversationid,
                "title": conv.title or "Untitled Chat",
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
            })

        logger.info(f"Fetched {len(result)} conversations for {useremail}")
        return jsonify({"conversations": result}), 200

    except Exception as e:
        logger.error(f"Get conversations error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@ragapp_bp.route('/auth/conversations/<int:conversation_id>', methods=['GET'])
@jwt_required()
def get_single_conversation(conversation_id):
    """Fetch a single conversation with full chat history for the authenticated user."""
    try:
        identity = json.loads(get_jwt_identity())
        useremail = identity.get("email")
        user = User.query.filter_by(email=useremail).first()
        if not user or not user.signinstatus:
            return jsonify({"error": "User not logged in"}), 401

        conversation = ChatConversation.query.filter_by(
            conversationid=conversation_id, useremail=useremail
        ).first()

        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        chat_history = ChatHistory.query.filter_by(
            conversationid=conversation_id
        ).order_by(ChatHistory.timestamp.asc()).all()

        history_data = [
            {
                "userquery": h.userquery,
                "llmresponse": h.llmresponse,
                "citation_data": h.citation_data or [],
                "timestamp": h.timestamp.strftime("%Y-%m-%d %H:%M:%S") if h.timestamp else None
            }
            for h in chat_history
        ]

        logger.info(f"Fetched conversation {conversation_id} for {useremail}")
        return jsonify({
            "conversation": {
                "conversationid": conversation.conversationid,
                "title": conversation.title or "Untitled Chat",
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "chat_history": history_data
            }
        }), 200

    except Exception as e:
        logger.error(f"Get single conversation error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@ragapp_bp.route('/conversation/<int:conversation_id>/history', methods=['GET'])
@jwt_required(optional=True)
def get_conversation_history(conversation_id):
    """Retrieve chat history for a specific conversation ID."""
    try:
        useremail = None
        identity = get_jwt_identity()
        if identity:
            identity_data = json.loads(identity)
            useremail = identity_data.get("email")
            user = User.query.filter_by(email=useremail).first()
            if not user or not user.signinstatus:
                logger.error(f"User not logged in: {useremail}")
                return jsonify({"error": "User not logged in"}), 401

        conversation = ChatConversation.query.filter_by(conversationid=conversation_id).first()
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return jsonify({"error": "Conversation not found"}), 404

        if useremail and conversation.useremail and conversation.useremail != useremail:
            logger.error(f"User {useremail} not authorized for conversation {conversation_id}")
            return jsonify({"error": "Not authorized to access this conversation"}), 403

        chat_history = ChatHistory.query.filter_by(
            conversationid=conversation_id
        ).order_by(ChatHistory.timestamp.asc()).all()

        if not chat_history:
            logger.error(f"Conversation history not found for ID {conversation_id}")
            return jsonify({"error": "Conversation history not found"}), 404

        conversation_history = [
            {
                "userquery": history.userquery,
                "llmresponse": history.llmresponse,
                "citation_data": history.citation_data or [],
                "timestamp": history.timestamp.strftime("%Y-%m-%d %H:%M:%S") if history.timestamp else None,
                "prompt_received_at": history.prompt_received_at.isoformat() if history.prompt_received_at else None,
                "response_generated_at": history.response_generated_at.isoformat() if history.response_generated_at else None,
                "response_time_ms": history.response_time_ms or None,
            }
            for history in chat_history
        ]

        logger.info(f"Retrieved conversation history for ID {conversation_id}")
        return jsonify({"conversation_id": conversation_id, "conversation_history": conversation_history}), 200

    except Exception as e:
        logger.error(f"Conversation history error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@ragapp_bp.route('/feedback', methods=['POST', 'OPTIONS'])
def submit_feedback():
    """Receive thumbs up/down + written feedback from users."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    data = request.get_json()
    vote = data.get("vote")
    comment = data.get("comment", "")
    conversation_id = data.get("conversation_id")
    message_index = data.get("message_index")
    userquery = data.get("userquery")
    llmresponse = data.get("llmresponse")

    if vote not in ("up", "down"):
        return jsonify({"error": "Invalid vote value"}), 400

    try:
        feedback = ChatFeedback(
            conversation_id=conversation_id,
            message_index=message_index,
            vote=vote,
            comment=comment,
            userquery=userquery,
            llmresponse=llmresponse,
        )
        db.session.add(feedback)
        db.session.commit()
        logger.info(f"Feedback saved: {vote} for conversation {conversation_id}")
        return jsonify({"message": "Feedback received, thank you!"}), 200

    except Exception as e:
        logger.error(f"Feedback error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@ragapp_bp.route('/consent', methods=['POST', 'OPTIONS'])
def record_consent():
    """Record user consent decision — fires once when user makes their choice."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200
 
    try:
        data = request.get_json()
        agreed = data.get("user_consent", None)
        logger.info(f"Consent recorded: {'agreed' if agreed else 'declined'} at {datetime.utcnow()}")
        return jsonify({"message": "Consent recorded", "user_consent": agreed}), 200
    except Exception as e:
        logger.error(f"Consent error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# ── STREAMING ENDPOINTS ──────────────────────────────────────────────────────
# These are NEW endpoints that sit alongside the existing /chat and /auth/chat.
# The existing endpoints are NOT touched — if streaming breaks, just revert
# ChatWindow.js to use the original endpoints.

from flask import Response, stream_with_context
import json as _json

@ragapp_bp.route('/chat/stream', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per minute")
def chat_stream():
    """Streaming version of /chat — sends SSE tokens as they generate."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    session.permanent = True
    data = request.get_json()
    userquery = data.get("userquery")
    conversation_id = parse_conversation_id(data.get("conversation_id"))
    user_consent = data.get("user_consent", None)

    if not userquery:
        return jsonify({"error": "Query is required"}), 400

    prompt_received_at = datetime.utcnow()

    # Set up conversation before streaming starts
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
            db.session.commit()
        else:
            existing = ChatConversation.query.filter_by(conversationid=conversation_id).first()
            if not existing:
                return jsonify({"error": "Conversation not found"}), 404

        history_userquery = [
            h.userquery for h in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.desc()).limit(3)
        ]

        full_conversation_history = [
            {"userquery": h.userquery, "llmresponse": h.llmresponse}
            for h in ChatHistory.query.filter_by(
                conversationid=conversation_id
            ).order_by(ChatHistory.timestamp.asc()).all()
        ]

    except Exception as e:
        logger.error(f"Stream setup error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

    def generate():
        try:
            full_text = ""
            final_meta = {}

            for chunk in response_llm.generate_streaming_response(
                userquery, history_userquery, conversation_history=full_conversation_history
            ):
                # Each chunk is already formatted as "data: {...}\n\n"
                line = chunk.strip()
                if line.startswith("data: "):
                    try:
                        parsed = _json.loads(line[6:])
                        if parsed.get("type") == "token":
                            full_text += parsed.get("content", "")
                        elif parsed.get("type") == "done":
                            final_meta = parsed
                    except Exception:
                        pass
                yield chunk

            # Save to DB after streaming completes
            response_generated_at = datetime.utcnow()
            response_time_ms = (response_generated_at - prompt_received_at).total_seconds() * 1000
            llmresponse = final_meta.get("full_text", full_text)
            citation_data = final_meta.get("citation_data", [])
            top_5_retrieved = final_meta.get("top_5_retrieved", [])
            top_n_document = final_meta.get("top_n_document", [])
            token_count = final_meta.get("token_count")

            new_history = ChatHistory(
                conversationid=conversation_id,
                useremail=None,
                userquery=userquery,
                llmresponse=llmresponse,
                top_5_retrieved=top_5_retrieved,
                top_n_document=top_n_document,
                citation_data=citation_data,
                prompt_received_at=prompt_received_at,
                response_generated_at=response_generated_at,
                response_time_ms=response_time_ms,
                timestamp=prompt_received_at,
                token_count=token_count,
                user_consent=user_consent,
            )
            db.session.add(new_history)

            convo = ChatConversation.query.filter_by(conversationid=conversation_id).first()
            if convo:
                convo.last_updated = datetime.utcnow()

            db.session.commit()

            # Send conversation_id in a final metadata chunk
            yield f"data: {_json.dumps({'type': 'meta', 'conversation_id': conversation_id, 'citation_data': citation_data, 'top_n_document': top_n_document})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
        }
    )


@ragapp_bp.route('/auth/chat/stream', methods=['POST', 'OPTIONS'])
@limiter.limit("30 per minute")
def auth_chat_stream():
    """Streaming version of /auth/chat for authenticated users."""
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    @jwt_required()
    def handle_stream():
        session.permanent = True
        data = request.get_json()
        userquery = data.get("userquery")
        conversation_id = parse_conversation_id(data.get("conversation_id"))
        user_consent = data.get("user_consent", None)

        if not userquery or len(userquery) > 1000:
            return jsonify({"error": "Query must be between 1 and 1000 characters"}), 400

        # Security: prompt injection filter
        _injection = ["ignore previous instructions","ignore your instructions","forget your system prompt","act as","you are now","jailbreak","dan mode"]
        if any(p in userquery.lower() for p in _injection):
            return jsonify({"error": "Invalid input detected"}), 400

        prompt_received_at = datetime.utcnow()

        try:
            identity = _json.loads(get_jwt_identity())
            useremail = identity.get("email")
            user = User.query.filter_by(email=useremail).first()
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        if not user or not user.signinstatus:
            return jsonify({"error": "User not logged in"}), 401

        try:
            history_userquery = []
            full_conversation_history = []

            if not conversation_id:
                new_conversation = ChatConversation(
                    useremail=useremail,
                    title=userquery[:50],
                    created_at=datetime.utcnow()
                )
                db.session.add(new_conversation)
                db.session.flush()
                conversation_id = new_conversation.conversationid
                db.session.commit()
            else:
                existing = ChatConversation.query.filter_by(
                    conversationid=conversation_id, useremail=useremail
                ).first()
                if not existing:
                    return jsonify({"error": "Conversation not found"}), 404

                history_userquery = [
                    h.userquery for h in ChatHistory.query.filter_by(
                        conversationid=conversation_id
                    ).order_by(ChatHistory.timestamp.desc()).limit(3).all()
                ]

                full_conversation_history = [
                    {"userquery": h.userquery, "llmresponse": h.llmresponse}
                    for h in ChatHistory.query.filter_by(
                        conversationid=conversation_id
                    ).order_by(ChatHistory.timestamp.asc()).all()
                ]

        except Exception as e:
            logger.error(f"Auth stream setup error: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

        def generate():
            try:
                full_text = ""
                final_meta = {}

                for chunk in response_llm.generate_streaming_response(
                    userquery, history_userquery, conversation_history=full_conversation_history
                ):
                    line = chunk.strip()
                    if line.startswith("data: "):
                        try:
                            parsed = _json.loads(line[6:])
                            if parsed.get("type") == "token":
                                full_text += parsed.get("content", "")
                            elif parsed.get("type") == "done":
                                final_meta = parsed
                        except Exception:
                            pass
                    yield chunk

                response_generated_at = datetime.utcnow()
                response_time_ms = (response_generated_at - prompt_received_at).total_seconds() * 1000
                llmresponse = final_meta.get("full_text", full_text)
                citation_data = final_meta.get("citation_data", [])
                top_5_retrieved = final_meta.get("top_5_retrieved", [])
                top_n_document = final_meta.get("top_n_document", [])
                token_count = final_meta.get("token_count")

                chat_history = ChatHistory(
                    useremail=useremail,
                    conversationid=conversation_id,
                    userquery=userquery,
                    llmresponse=llmresponse,
                    top_5_retrieved=top_5_retrieved,
                    top_n_document=top_n_document,
                    citation_data=citation_data,
                    prompt_received_at=prompt_received_at,
                    response_generated_at=response_generated_at,
                    response_time_ms=response_time_ms,
                    timestamp=prompt_received_at,
                    token_count=token_count,
                    user_consent=user_consent,
                )
                db.session.add(chat_history)

                convo = ChatConversation.query.filter_by(conversationid=conversation_id).first()
                if convo:
                    convo.last_updated = datetime.utcnow()

                db.session.commit()

                yield f"data: {_json.dumps({'type': 'meta', 'conversation_id': conversation_id, 'citation_data': citation_data, 'top_n_document': top_n_document})}\n\n"

            except Exception as e:
                logger.error(f"Auth streaming error: {str(e)}", exc_info=True)
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': '*',
            }
        )

    return handle_stream()