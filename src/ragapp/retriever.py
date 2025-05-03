import os
import logging
from sentence_transformers import CrossEncoder
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from config import OPENAI_API_KEY, COLLECTION_NAME, RERANKER_MODEL, EMBEDDING_MODEL_NAME

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/serverlogs/debug.log')
    ]
)
logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self):
        # Set environment variable to prevent tokenizers parallelism warning
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        # # Set up the dataset path and initialize the ChromaDB persistent client
        # os.makedirs(DATASET_PATH, exist_ok=True)

        # Ensure consistent settings for PersistentClient
        self.client = chromadb.HttpClient(
            host="chroma",
            port=8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )

        # Load the cross-encoder reranker model
        self.reranker = CrossEncoder(RERANKER_MODEL)

        # Initialize OpenAI embedding function
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBEDDING_MODEL_NAME
        )

    def retrieve_and_rerank(self, query, top_k=7):
        """
        Retrieves the top K documents based on cosine similarity to the query and
        reranks them using a cross-encoder for improved relevance.
        """
        # Load the specified collection from ChromaDB
        collection = self.client.get_collection(COLLECTION_NAME)

        # Generate embedding for the user query
        query_embedding = self.openai_ef([query])

        # Retrieve top-K initial results from ChromaDB using HNSW and cosine similarity
        initial_results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )

        documents = initial_results['documents'][0]
        ids = initial_results['ids'][0]
        metadata = initial_results.get('metadatas', [])[0]

        # Prepare pairs for reranking using document content
        pairs = [(query, doc) for doc in documents]

        # Perform reranking using the cross-encoder
        rerank_scores = self.reranker.predict(pairs)
        reranked_docs = sorted(
            zip(documents, metadata, rerank_scores),
            key=lambda x: x[2],
            reverse=True
        )

        # Extract the top reranked documents
        top_n_results = [
            {
                "document": doc,
                "score": float(score),  # Convert to standard Python float
                "document_link": meta.get('document_link', 'No link available'),
                "document_name": meta.get('document_title', 'Name not Available')
            }
            for doc, meta, score in reranked_docs[:5]
        ]

        citation_data = []
        context_data = []

        for idx, result in enumerate(top_n_results, start=1):
            citation_holder = {
                result["document_name"]: result['document_link']}
            context_documents = {f'document{idx}': result['document']}

            citation_data.append(citation_holder)
            context_data.append(context_documents)

        # Remove duplicates while maintaining order
        unique_citations = []
        seen = set()
        for data in citation_data:
            item = frozenset(data.items())
            if item not in seen:
                seen.add(item)
                unique_citations.append(data)

        # Sort the dictionaries by key
        citation_data = [dict(sorted(data.items()))
                         for data in unique_citations]

        return top_n_results, citation_data, context_data
