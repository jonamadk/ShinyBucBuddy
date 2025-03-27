import os
import json
import uuid
import logging
from openai import OpenAI
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import OPENAI_API_KEY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            'logs/serverlogs/chromadb_push.log')  # Local log file
    ]
)
logger = logging.getLogger(__name__)

# Replace with your API key (consider moving to .env file in production)
OPENAI_API_KEY_IS = OPENAI_API_KEY
INPUT_FILE = "Documents/combined_data_with_metadata.json"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY_IS)

# Initialize ChromaDB HTTP client
chroma_client = chromadb.HttpClient(
    host="chroma",  # Use localhost since running locally
    port=8000,      # Use the host port from docker-compose.yml
    settings=Settings(allow_reset=True)
)

# Define embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-large"
)


def get_embedding(text, model="text-embedding-3-large"):
    """Generate embedding for a given text using OpenAI."""
    text = text.replace("\n", " ")
    try:
        response = client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(
            "Failed to generate embedding for text '%s': %s", text[:50], str(e))
        raise


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
        with open(INPUT_FILE, 'r') as file:
            data = json.load(file)
        logger.info("Loaded %d items from %s", len(data), INPUT_FILE)
    except FileNotFoundError:
        logger.error("Input file %s not found", INPUT_FILE)
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from %s", INPUT_FILE)
        raise

    # Process and push data to ChromaDB
    item_count = 0
    total_items = 0

    for item in data:
        item_count += 1
        doc_id = str(uuid.uuid4())
        text_data = item.get('document_content', '')

        # Extract metadata with error handling
        try:
            tag1, tag2, tag3, tag4, tag5, description = item.get(
                'metadata', ['', '', '', '', '', ''])
            metadata_text = f"{tag1}, {tag2}, {tag3}, {tag4}, {tag5}, {description}"
        except (IndexError, TypeError):
            metadata_text = ""

        document_title = item.get('document_title', 'No title')
        document_link = item.get(
            'document_link', 'Source Link has expired. Cross-validate the response')

        combined_text = f"Metadata: {metadata_text} Content: {text_data}"

        # Prepare metadata
        metadata = {
            "document_title": document_title,
            "document_link": document_link
        }

        try:
            # Generate embedding
            embedding = get_embedding(
                combined_text, model="text-embedding-3-large")

            # Upsert data into ChromaDB
            collection.upsert(
                embeddings=[embedding],
                documents=[combined_text],
                ids=[doc_id],
                metadatas=[metadata]
            )

            total_items += 1
            logger.info("Item %d pushed to ChromaDB with ID %s",
                        item_count, doc_id)
        except Exception as e:
            logger.error("Failed to upsert item %d: %s", item_count, str(e))
            continue

    logger.info("Total documents pushed: %d", total_items)
    return f"Total documents pushed: {total_items}"
