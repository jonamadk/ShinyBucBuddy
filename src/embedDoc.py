import os
import json
import uuid
import logging
import chromadb
from chromadb.config import Settings
from config import EMBEDDING_MODEL_NAME

from chromadb.utils import embedding_functions
from config import OPENAI_API_KEY, DATASET_PATH

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

# Initialize ChromaDB persistent client
os.makedirs(DATASET_PATH, exist_ok=True)




settings = Settings(
    allow_reset=True,
    anonymized_telemetry=False
)


chroma_client = chromadb.PersistentClient(
    path=DATASET_PATH,
    settings=settings
)

# Initialize OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL_NAME
)


def process_and_push_data_to_chromadb():
    """Process data from JSON file and push it to ChromaDB."""
    # Access or create the collection
    try:
        collection = chroma_client.get_or_create_collection(
            name="web_information",
            embedding_function=openai_ef
        )
        logger.info(
            "Collection 'web_information' accessed or created successfully")
    except Exception as e:
        logger.error(
            "Failed to access or create collection 'web_information': %s", str(e))
        raise

    # Load data from JSON file
    try:
        with open("Documents/combined_data_with_metadata.json", 'r') as file:
            data = json.load(file)
        logger.info("Loaded %d items from JSON file", len(data))
    except FileNotFoundError:
        logger.error("Input file not found")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON file")
        raise

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
