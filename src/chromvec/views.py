# Blueprint setup
from flask import Blueprint, jsonify
from flask import Blueprint, jsonify
from chromadb import HttpClient
from chromadb.config import Settings
from config import COLLECTION_NAME
from .embedDoc import process_and_push_data_to_chromadb
import logging

chroma_bp = Blueprint('chroma_bp', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ChromaDB setup
chroma_client = HttpClient(
    host="chroma-container",
    port=8000,
    settings=Settings(allow_reset=True, anonymized_telemetry=False)
)


@chroma_bp.route('/health', methods=['GET'])
def health_check():
    """Check if the API and its dependencies are running."""
    try:
        health_status = {"status": "healthy", "message": "API is running"}
        chroma_client = HttpClient(
            host="chroma-container",
            port=8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        logger.debug(
            "Attempting to connect to ChromaDB at chroma-container:8000")
        response = chroma_client.heartbeat()
        logger.debug(f"ChromaDB heartbeat response: {response}")
        chroma_client.get_or_create_collection(name="health_check_collection")
        health_status["chromadb"] = "connected"
        logger.info("ChromaDB connection successful")
    except Exception as e:
        logger.error(f"ChromaDB connection failed: {str(e)}", exc_info=True)
        health_status = {
            "status": "unhealthy",
            "message": f"API is running, but ChromaDB is not accessible: {str(e)}"
        }
        return jsonify(health_status), 503
    return jsonify(health_status), 200


@chroma_bp.route('/embed', methods=['POST'])
def embed_documents():
    """Trigger document embedding process."""
    try:
        result = process_and_push_data_to_chromadb()
        logger.info(f"Embedding successful: {result}")
        return jsonify({"message": result}), 200
    except FileNotFoundError:
        logger.error("Input file not found for embedding")
        return jsonify({"error": "Input file not found"}), 404
    except Exception as e:
        logger.error(f"Embedding failed: {str(e)}", exc_info=True)
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500


@chroma_bp.route("/document/count", methods=["GET"])
def document_count():
    try:
        collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME
        )
        count = collection.count()
        return jsonify({"document_count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @chroma_bp.route("/collection/delete", methods=["DELETE"])
# def delete_collection():
#     try:
#         chroma_client.delete_collection(COLLECTION_NAME)
#         logger.info(f"Collection '{COLLECTION_NAME}' deleted successfully")
#         return jsonify({"message": f"Collection '{COLLECTION_NAME}' deleted successfully"}), 200
#     except Exception as e:
#         logger.error(f"Failed to delete collection: {str(e)}")
#         return jsonify({"error": str(e)}), 500
