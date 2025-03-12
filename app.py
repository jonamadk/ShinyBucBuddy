from flask import Flask, request, render_template, jsonify
import subprocess
import json
import os
from responseLLM import generate_filtered_response

app = Flask(__name__)

# Function to save query-response pairs to a JSON file
def append_to_json_file(response_data_holder):
    file_path = "response_data.json"
    try:
        # Check if the file exists and is non-empty
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # File exists and contains data, so load it and append
            with open(file_path, "r+") as file:
                try:
                    # Load existing data into a list
                    data = json.load(file)
                except json.JSONDecodeError:
                    # If the file is empty or has invalid JSON, initialize as an empty list
                    data = []
                # Append the new dictionary
                data.append(response_data_holder)
                # Go back to the beginning of the file and truncate it
                file.seek(0)
                json.dump(data, file, indent=4)
                file.truncate()  # Remove any remaining old content
        else:
            # If the file doesn't exist or is empty, create it with an initial list
            with open(file_path, "w") as file:
                json.dump([response_data_holder], file, indent=4)
    except OSError as e:
        print(f"Error accessing file {file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
        
def time_stamp_append_to_json_file(response_data_holder):
    file_path = "response_timestamp.json"
    try:
        # Check if the file exists and is non-empty
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # File exists and contains data, so load it and append
            with open(file_path, "r+") as file:
                try:
                    # Load existing data into a list
                    data = json.load(file)
                except json.JSONDecodeError:
                    # If the file is empty or has invalid JSON, initialize as an empty list
                    data = []
                # Append the new dictionary
                data.append(response_data_holder)
                # Go back to the beginning of the file and truncate it
                file.seek(0)
                json.dump(data, file, indent=4)
                file.truncate()  # Remove any remaining old content
        else:
            # If the file doesn't exist or is empty, create it with an initial list
            with open(file_path, "w") as file:
                json.dump([response_data_holder], file, indent=4)
    except OSError as e:
        print(f"Error accessing file {file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


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
        response, top_n_document, citation_data, context_data, timestamp_data  = generate_filtered_response(query)
        # print(response)
        # Prepare data to save into the JSON file
        response_data_holder = {
            "query": query,
            "context": context_data,
            "response": response,
            "model":timestamp_data["Model"]
            
        }
        
        # Save the query and response to a JSON file
        append_to_json_file(response_data_holder)
        time_stamp_append_to_json_file(timestamp_data)

        # Return the response to the user
        return jsonify({"query": query,  "response": response, "citation_data":citation_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Chat Page
@app.route('/')
def chat_page():
    return render_template('chat.html')

if __name__ == "__main__":
    app.run(port=8000, debug=True)
