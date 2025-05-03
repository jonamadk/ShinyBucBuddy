import os
import json
import uuid
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import EMBEDDING_MODEL_NAME, COLLECTION_NAME, OPENAI_API_KEY
import tiktoken
from typing import List

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

def chunk_text(text: str, max_tokens: int = 8000) -> List[str]:
    """Split text into chunks that fit within token limit."""
    encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    tokens = encoding.encode(text)
    chunks = []
    
    current_chunk = []
    current_length = 0
    
    for token in tokens:
        if current_length + 1 <= max_tokens:
            current_chunk.append(token)
            current_length += 1
        else:
            # Convert tokens back to text and add to chunks
            chunks.append(encoding.decode(current_chunk))
            current_chunk = [token]
            current_length = 1
    
    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(encoding.decode(current_chunk))
    
    return chunks

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
        with open("Documents/final_merged_data.json", 'r') as file:
            data = json.load(file)
        logger.info("Loaded %d items from JSON file", len(data))

        # Process and push data to ChromaDB
        total_chunks = 0
        for item in data:
            text_data = item.get('document_content', '')
            base_metadata = {
                "document_title": item.get('document_title', 'No title'),
                "document_link": item.get('document_link', 'No link available')
            }

            # Split text into chunks if needed
            text_chunks = chunk_text(text_data)
            
            for chunk_idx, chunk in enumerate(text_chunks):
                doc_id = str(uuid.uuid4())
                
                # Add chunk information to metadata
                metadata = base_metadata.copy()
                if len(text_chunks) > 1:
                    metadata["chunk_index"] = chunk_idx
                    metadata["total_chunks"] = len(text_chunks)

                # Generate embedding
                try:
                    embedding = openai_ef([chunk])

                    # Upsert data into ChromaDB
                    collection.upsert(
                        embeddings=embedding,
                        documents=[chunk],
                        ids=[doc_id],
                        metadatas=[metadata]
                    )
                    total_chunks += 1
                    logger.info(f"Document chunk {chunk_idx + 1}/{len(text_chunks)} with ID {doc_id} pushed to ChromaDB")
                except Exception as e:
                    logger.error(f"Failed to process chunk {chunk_idx + 1}/{len(text_chunks)}: {str(e)}")
                    continue

        return f"Successfully embedded {total_chunks} document chunks from {len(data)} documents"

    except FileNotFoundError:
        logger.error("Input file not found")
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON file")
        raise
    except Exception as e:
        logger.error(f"Failed to process and push data to ChromaDB: {str(e)}", exc_info=True)
        raise