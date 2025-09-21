import os
import json
import uuid
import logging
import chromadb
import tiktoken  # OpenAI tokenizer
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import EMBEDDING_MODEL_NAME, COLLECTION_NAME, OPENAI_API_KEY, JSON_FILE_PATH

# Constants
MAX_TOKENS = 1000  # Safe token limit
CHUNK_OVERLAP = 200 # Optional: slight overlap between chunks

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

# Define JSON path
json_path = os.path.join(JSON_FILE_PATH)

# Initialize ChromaDB HTTP client
chroma_client = chroma_client = chromadb.HttpClient(
    host="chroma-container",
    port=8000,
    settings=Settings(allow_reset=True, anonymized_telemetry=False)
)

# Initialize OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL_NAME
)

# Initialize tokenizer
tokenizer = tiktoken.encoding_for_model(EMBEDDING_MODEL_NAME)

def split_by_token_limit(text, max_tokens=MAX_TOKENS, overlap=CHUNK_OVERLAP):
    """Split text into chunks that stay within token limits using tiktoken."""
    tokens = tokenizer.encode(text)
    chunks = []

    for i in range(0, len(tokens), max_tokens - overlap):
        chunk_tokens = tokens[i:i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)

    return chunks

def process_and_push_data_to_chromadb():
    """Reset collection and push JSON data to ChromaDB in token-safe chunks."""
    try:
        # Test connection
        heartbeat = chroma_client.heartbeat()
        logger.debug(f"ChromaDB heartbeat response: {heartbeat}")

        # Delete existing collection
        chroma_client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted existing collection: {COLLECTION_NAME}")

        # Recreate collection
        collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=openai_ef
        )
        logger.info(f"Recreated collection: {COLLECTION_NAME}")

        # Load data
        with open(json_path, 'r') as file:
            data = json.load(file)
        logger.info("Loaded %d items from JSON file", len(data))

        # Process and add each document
        for item in data:
            text_data = item.get('document_content', '')
            if not text_data.strip():
                continue

            chunks = split_by_token_limit(text_data)

            for i, chunk in enumerate(chunks):
                doc_id = f"{uuid.uuid4()}_{i}"
                metadata = {
                    "document_title": item.get('document_title', 'No title'),
                    "document_link": item.get('document_link', 'No link available'),
                    "chunk_index": i
                }

                try:
                    embedding = openai_ef([chunk])
                    collection.add(
                        embeddings=embedding,
                        documents=[chunk],
                        ids=[doc_id],
                        metadatas=[metadata]
                    )
                    logger.info("Chunk %d added with ID %s", i, doc_id)
                except Exception as embed_err:
                    logger.error(f"Embedding failed for chunk {i}: {embed_err}")

        return f"Successfully embedded documents with token-aware splitting."

    except FileNotFoundError:
        logger.error("Input file not found")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON file")
        raise
    except Exception as e:
        logger.error(f"Failed to process and push data to ChromaDB: {str(e)}", exc_info=True)
        raise
