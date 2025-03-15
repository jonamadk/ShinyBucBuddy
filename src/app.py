from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
from responseLLM import generate_filtered_response
from responselog import ResponseLogger
import chromadb
from chromadb.config import Settings

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
logger = ResponseLogger(response_file="logs/response_data.json", timestamp_file="logs/response_timestamp.json")

# Initialize ChromaDB client for health check
chroma_client = chromadb.HttpClient(
            host="chroma",
            port = 8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False))

# Health Check Endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Check if the API and its dependencies are running."""
    try:
        # Check Flask app status
        health_status = {"status": "healthy", "message": "API is running"}

        # Check ChromaDB connectivity
        chroma_client.heartbeat()  # Simple ping to ChromaDB
        health_status["chromadb"] = "connected"
    except Exception as e:
        health_status = {
            "status": "unhealthy",
            "message": f"API is running, but ChromaDB is not accessible: {str(e)}"
        }
        return jsonify(health_status), 503  # Service Unavailable

    return jsonify(health_status), 200

# Embedding Endpoint
@app.route('/embed', methods=['POST'])
def embed_documents():
    """
    Endpoint to trigger document embedding process.
    Returns success or error message.
    """
    try:
        # Execute embedding script (assumes Adaembedding.py exists)
        subprocess.run(['python3', 'Adaembedding.py'], check=True)
        return jsonify({"message": "Embedding completed successfully!"}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500
    except FileNotFoundError:
        return jsonify({"error": "Embedding script (Adaembedding.py) not found"}), 404

# Chat Endpoint
@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint to handle user queries and return chatbot responses.
    Expects a JSON body with 'query' field.
    """
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        # Generate response using the LLM and retrieval logic
        response, top_n_document, citation_data, context_data, timestamp_data = generate_filtered_response(query)

        # Log the response and timestamp
        response_data_holder = {
            "query": query,
            "context": context_data,
            "response": response,
            "model": timestamp_data["Model"]
        }
        logger.append_to_json_file(response_data_holder)
        logger.time_stamp_append_to_json_file(timestamp_data)

        # Return response to the client
        return jsonify({
            "query": query,
            "response": response,
            "citation_data": citation_data,
            "top":top_n_document,
            "timestamp": timestamp_data,
            
        }), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)