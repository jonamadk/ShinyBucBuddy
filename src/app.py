from flask import Flask, request, render_template, jsonify
import subprocess
from responseLLM import generate_filtered_response
from responselog import ResponseLogger

app = Flask(__name__, template_folder='../templates')
logger = ResponseLogger(response_file="../logs/response_data.json", timestamp_file="../logs/response_timestamp.json")

# Embedding Endpoint
@app.route('/embed', methods=['POST'])
def embed_documents():
    try:
        # Execute embeddingDoc.py
        subprocess.run(['python3', 'Adaembedding.py'], check=True)
        return jsonify({"message": "Embedding completed successfully!"}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Embedding failed: {e}"}), 500

# Chat Endpoint
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        # Generate a response using the chatbot logic
        response, top_n_document, citation_data, context_data, timestamp_data = generate_filtered_response(query)

        # Prepare data to save into the JSON file
        response_data_holder = {
            "query": query,
            "context": context_data,
            "response": response,
            "model": timestamp_data["Model"]
        }

        # Save the query and response to a JSON file
        logger.append_to_json_file(response_data_holder)
        logger.time_stamp_append_to_json_file(timestamp_data)

        # Return the response to the user
        return jsonify({"query": query, "response": response, "citation_data": citation_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Chat Page
@app.route('/')
def chat_page():
    return render_template('chat.html')

if __name__ == "__main__":
    app.run(port=8000, debug=True)