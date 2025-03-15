import os
import logging
from sentence_transformers import CrossEncoder
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from config import OPENAI_API_KEY, DATASET_PATH, COLLECTION_NAME, RERANKER_MODEL, EMBEDDING_MODEL_NAME

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/debug.log')
    ]
)
logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self):
        # Set environment variable to prevent tokenizers parallelism warning
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.client = chromadb.HttpClient(
            host="chroma",
            port = 8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False))


        # Load the cross-encoder reranker model
        self.reranker = CrossEncoder(RERANKER_MODEL)

        # Initialize OpenAI embedding function
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBEDDING_MODEL_NAME
        )

    def retrieve_and_rerank(self, query, top_k=5):
        """
        Retrieves the top K documents based on cosine similarity to the query and
        reranks them using a cross-encoder for improved relevance.
        """
      

            # Try to get the collection
        collection = self.client.get_collection(COLLECTION_NAME)
        logger.debug("Collection %s retrieved, total documents: %d", COLLECTION_NAME, collection.count())
       
        try:
            query_embedding = self.openai_ef([query])
            logger.debug("Query: %s, Embedding: %s", query, query_embedding)
        except Exception as e:
            logger.error("Failed to generate query embedding: %s", str(e))
            return [], [], []

        # Retrieve top-K initial results from ChromaDB
        try:
            initial_results = collection.query(
                query_embeddings=query_embedding,
                n_results=top_k
            )
            logger.debug("ChromaDB Query Results: %s", initial_results)
        except Exception as e:
            logger.error("ChromaDB query failed: %s", str(e))
            return [], [], []

        # Check if results are empty
        if not initial_results['documents'] or not initial_results['documents'][0]:
            logger.warning("No documents found for query: %s", query)
            return [], [], []  # Return empty lists for top_n_results, citation_data, context_data

        documents = initial_results['documents'][0]
        ids = initial_results['ids'][0]
        metadata = initial_results.get('metadatas', [[]])[0] or [{}] * len(documents)

        # Debug: Log the extracted data
        logger.debug("Documents: %s", documents)
        logger.debug("IDs: %s", ids)
        logger.debug("Metadata: %s", metadata)

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
                "score": score,
                "document_link": meta.get('document_link', 'No link available'),
                "document_name": meta.get('document_title', 'Name not Available')
            }
            for doc, meta, score in reranked_docs[:3]
        ]

        citation_data = []
        context_data = []

        for idx, result in enumerate(top_n_results, start=1):
            citation_holder = {result["document_name"]: result['document_link']}
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
        citation_data = [dict(sorted(data.items())) for data in unique_citations]

        return top_n_results, citation_data, context_data