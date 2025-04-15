import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Constants
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DATASET_PATH = os.path.join(os.getcwd(), "BUCDB")
COLLECTION_NAME = "web_information"
RERANKER_MODEL = 'cross-encoder/ms-marco-MiniLM-L-12-v2'
# EMBEDDING_MODEL_NAME = "text-embedding-ada-002"
EMBEDDING_MODEL_NAME =  "text-embedding-3-large"
SENTENCE_TRANSFORMER_MODEL_NAME = "all-MiniLM-L6-v2"
# For PostgreSQL user storage

