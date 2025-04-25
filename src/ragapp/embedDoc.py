import os
import json
import uuid
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import EMBEDDING_MODEL_NAME, COLLECTION_NAME, OPENAI_API_KEY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/serverlogs/chromadb_push.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize ChromaDB HTTP client
chroma_client = chromadb.HttpClient(
    host="chroma-container",
    port=8000,
    settings=Settings(allow_reset=True, anonymized_telemetry=False)
)

# Initialize OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL_NAME
)

def process_and_push_data_to_chromadb():
    """Process data from JSON file and push it to ChromaDB."""
    try:
        # Test connection with heartbeat
        heartbeat = chroma_client.heartbeat()
        logger.debug(f"ChromaDB heartbeat response: {heartbeat}")

        # Access or create the collection
        collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=openai_ef
        )
        logger.info(f"Collection '{COLLECTION_NAME}' accessed or created successfully")

        # Load data from JSON file
        with open("Documents/combined_data_with_metadata.json", 'r') as file:
            data = json.load(file)
        logger.info("Loaded %d items from JSON file", len(data))

        # Process and push data to ChromaDB
        for item in data:
            doc_id = str(uuid.uuid4())
            text_data = item.get('document_content', '')
            metadata = {
                "document_title": item.get('document_title', 'No title'),
                "document_link": item.get('document_link', 'No link available')
            }

            # Generate embedding
            embedding = openai_ef([text_data])

            # Upsert data into ChromaDB
            collection.upsert(
                embeddings=embedding,
                documents=[text_data],
                ids=[doc_id],
                metadatas=[metadata]
            )
            logger.info("Document with ID %s pushed to ChromaDB", doc_id)

        return f"Successfully embedded {len(data)} documents"

    except FileNotFoundError:
        logger.error("Input file not found")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON file")
        raise
    except Exception as e:
        logger.error(f"Failed to process and push data to ChromaDB: {str(e)}", exc_info=True)
        raise