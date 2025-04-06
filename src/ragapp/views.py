from flask import Blueprint, request, jsonify
from .responseLLM import ResponseLLM
from .responselog import ResponseLogger
from .embedDoc import process_and_push_data_to_chromadb
import chromadb

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
        chromadb.heartbeat()  # Check ChromaDB connectivity
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
    """Handle user queries and return chatbot responses."""
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        response, top_n_document, citation_data, context_data, timestamp_data = response_llm.generate_filtered_response(
            query)
        response_logger.append_to_json_file({
            "query": query,
            "context": context_data,
            "response": response,
            "model": timestamp_data["Model"]
        })
        response_logger.time_stamp_append_to_json_file(timestamp_data)
        return jsonify({
            "query": query,
            "response": response,
            "citation_data": citation_data,
            "top": top_n_document,
            "timestamp": timestamp_data,
        }), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
