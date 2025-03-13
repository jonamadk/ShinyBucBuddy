import os
import time
import ollama
from openai import OpenAI
from retriever import Retriever
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from config import OPENAI_API_KEY, SENTENCE_TRANSFORMER_MODEL_NAME
from sentence_transformers import SentenceTransformer, util

# Initialize API clients
client = OpenAI(api_key=OPENAI_API_KEY)

# Define LLM
llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.5)

# Load sentence transformer model for similarity computation
similarity_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)

# Simple in-memory history store (mimicking k=1 behavior)
conversation_history = []  # List to store messages; limited to last 2 (1 turn)

# Define query rewrite prompt
rewrite_query_prompt = """
Based on the provided user {question} and the conversational {history}, rewrite the query based on previous conversations in precisely and concisely adhering to context.
"""

rewrite_prompt = ChatPromptTemplate.from_template(rewrite_query_prompt, verbose=True)

# Define a chain for rewriting queries with history
rewrite_chain = (
    {
        "question": RunnablePassthrough(),
        "history": RunnableLambda(lambda x: conversation_history[-2:] if conversation_history else [])
    }
    | rewrite_prompt
    | llm
)

retriever = Retriever()

def compute_similarity(query, history):
    """Compute cosine similarity between the query and conversation history."""
    if not history:
        return 0.0  # No history, no similarity
    
    # Extract the last message from history (or concatenate all if needed)
    history_text = " ".join([msg.content for msg in history])
    
    # Get embeddings for query and history
    query_embedding = similarity_model.encode(query, convert_to_tensor=True)
    history_embedding = similarity_model.encode(history_text, convert_to_tensor=True)
    
    # Compute cosine similarity
    similarity = util.cos_sim(query_embedding, history_embedding).item()
    return similarity

def count_tokens(context_data):
    """Counts total tokens in the retrieved context data."""
    return sum(len(text.split()) for document in context_data for text in document.values())

def rewrite_query(query):
    """Rewrites the user query using conversation history if similarity is high enough."""
    history = conversation_history[-2:] if conversation_history else []  # Last turn (user + AI)
    similarity_threshold = 0.5  # Adjust this threshold as needed (0 to 1 scale)
    similarity_score = compute_similarity(query, history)
    print(f"Similarity Score: {similarity_score}")
    
    # If similarity is low, return the original query
    if similarity_score < similarity_threshold:
        print("Similarity too low, using original query.")
        return query
    
    print("Rewriting query based on history.")
    return rewrite_chain.invoke(query).content

def generate_filtered_response(query, rerank_score_threshold=-5):
    """Generates a response using retrieved documents."""
    rewritten_query = rewrite_query(query)
    print("REWRITEEN", rewritten_query)
    top_n_document, citation_data, context_data = retriever.retrieve_and_rerank(rewritten_query)

    total_token_count = count_tokens(context_data)
    timestamp_holder = {"Token Count": total_token_count}

    generation_kwargs = {
        "max_tokens": 500,
        "echo": True,
        "top_k": 1
    }

    llmChoiceGPT = True

    start_time = time.time()
    if llmChoiceGPT:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    You are BucBuddy - conversational and context-aware QnA platform for East Tennessee State University.
                    Your job is to answer the user query in a conversational way strictly based on context.

                    Please just answer the question strictly based on the context.

                    User question: {rewritten_query}

                    Context: {top_n_document}.
                    """
                }
            ]
        )
        generated_text = completion.choices[0].message.content
        timestamp_holder.update({"TimeStamp": time.time() - start_time, "Model": "GPT 4o Mini"})
    else:
        response = ollama.chat(
            model="llama2",
            options=generation_kwargs,
            messages=[
                {
                    "role": "user",
                    "content": f"You are ETSU's conversational and context-aware QnA system. Answer the {query} strictly based on the following information only: {top_n_document}. If explicit/rough/sensitive language is detected in the query, respond saying 'Explicit language is prohibited.'"
                }
            ]
        )
        generated_text = response["message"]["content"]
        timestamp_holder.update({"TimeStamp": time.time() - start_time, "Model": "Ollama2- Local Server"})

    # Update conversation history (mimicking k=1 behavior)
    if len(conversation_history) >= 2:
        conversation_history.pop(0)  # Remove oldest turn
    conversation_history.append(HumanMessage(content=rewritten_query))
    conversation_history.append(AIMessage(content=generated_text))

    return generated_text, top_n_document, citation_data, context_data, timestamp_holder

