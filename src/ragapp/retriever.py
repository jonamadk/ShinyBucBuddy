import os
import logging
from sentence_transformers import CrossEncoder, SentenceTransformer, util
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
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.client = chromadb.HttpClient(
            host="chroma",
            port=8000,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )

        self.reranker = CrossEncoder(RERANKER_MODEL)

        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBEDDING_MODEL_NAME
        )

        # Lightweight model for checking content overlap between doc and answer
        self.similarity_model = SentenceTransformer("all-MiniLM-L6-v2")

    def is_citation_relevant(self, doc_text, llm_answer, threshold=0.4):
        """
        Check if a document is genuinely relevant to the LLM answer
        by comparing their semantic similarity.
        Only citations where the document meaningfully overlaps with
        what the LLM actually said will be shown to the user.
        """
        try:
            doc_embedding = self.similarity_model.encode(
                doc_text[:500], convert_to_tensor=True)
            answer_embedding = self.similarity_model.encode(
                llm_answer[:500], convert_to_tensor=True)
            similarity = util.cos_sim(doc_embedding, answer_embedding).item()
            logger.debug(f"Citation similarity score: {round(similarity, 3)}")
            return similarity >= threshold
        except Exception as e:
            logger.error(f"Citation relevance check failed: {e}")
            return True  # Default to showing if check fails

    def retrieve_and_rerank(self, query, top_k=7, llm_answer=None):
        """
        Retrieves the top K documents based on cosine similarity to the query,
        reranks using a cross-encoder, then filters citations by:
        1. Reranker score threshold (0.3)
        2. Content overlap with LLM answer (only shows relevant citations)
        3. Max 2 citations shown to user

        Returns:
            top_5_retrieved  - top 5 docs BEFORE reranking (for metrics)
            top_n_results    - top docs AFTER reranking (passed to LLM)
            citation_data    - filtered citations (max 2, relevant only)
            context_data     - document text for the reranked docs
        """
        RELEVANCE_THRESHOLD = 0.3
        MAX_CITATIONS = 2
        OVERLAP_THRESHOLD = 0.4

        collection = self.client.get_collection(COLLECTION_NAME)
        query_embedding = self.openai_ef([query])

        initial_results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )

        documents = initial_results['documents'][0]
        ids = initial_results['ids'][0]
        metadata = initial_results.get('metadatas', [])[0]

        # Top 5 BEFORE reranking (for metrics logging)
        top_5_retrieved = [
            {
                "document_name": meta.get('document_title', 'Name not Available'),
                "document_link": meta.get('document_link', 'No link available'),
                "preview": doc[:200]
            }
            for doc, meta in zip(documents[:5], metadata[:5])
        ]

        # Rerank
        pairs = [(query, doc) for doc in documents]
        rerank_scores = self.reranker.predict(pairs)
        reranked_docs = sorted(
            zip(documents, metadata, rerank_scores),
            key=lambda x: x[2],
            reverse=True
        )

        # Filter by reranker threshold
        top_n_results = [
            {
                "document": doc,
                "score": float(score),
                "document_link": meta.get('document_link', 'No link available'),
                "document_name": meta.get('document_title', 'Name not Available')
            }
            for doc, meta, score in reranked_docs[:5]
            if float(score) >= RELEVANCE_THRESHOLD
        ]

        logger.debug(
            f"Reranker: {len(reranked_docs[:5])} docs retrieved, "
            f"{len(top_n_results)} passed threshold of {RELEVANCE_THRESHOLD}. "
            f"Scores: {[round(float(s), 3) for _, _, s in reranked_docs[:5]]}"
        )

        # Build context for LLM
        context_data = [
            {f'document{idx}': result['document']}
            for idx, result in enumerate(top_n_results, start=1)
        ]

        # Filter citations by content overlap with LLM answer
        # If llm_answer provided, only show citations where the doc
        # actually contributed to the answer
        citation_candidates = []
        for result in top_n_results:
            if llm_answer:
                if self.is_citation_relevant(
                        result['document'], llm_answer, OVERLAP_THRESHOLD):
                    citation_candidates.append(result)
            else:
                citation_candidates.append(result)

        # Cap at MAX_CITATIONS
        citation_candidates = citation_candidates[:MAX_CITATIONS]

        # Build deduplicated citation data
        citation_data = []
        seen = set()
        for result in citation_candidates:
            entry = {result["document_name"]: result['document_link']}
            item = frozenset(entry.items())
            if item not in seen:
                seen.add(item)
                citation_data.append(dict(sorted(entry.items())))

        logger.debug(
            f"Citations after overlap filter: {len(citation_data)} "
            f"(max {MAX_CITATIONS}, overlap threshold {OVERLAP_THRESHOLD})"
        )

        return top_5_retrieved, top_n_results, citation_data, context_data