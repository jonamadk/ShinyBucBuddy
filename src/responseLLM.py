import os
import time
import ollama
from openai import OpenAI
from retriever import Retriever
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from config import OPENAI_API_KEY

# Initialize API clients and memory
client = OpenAI(api_key=OPENAI_API_KEY)
memory = ConversationBufferMemory(k=1, return_messages=True)

# Define LLM
llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.7)

# Define query rewrite prompt
rewrite_query_prompt = """
Based on the provided user query and the conversational history, rewrite the query as the summary of previous conversations in preicse and concise.

Conversational history: {history}

User query: {question}

"""

rewrite_prompt = ChatPromptTemplate.from_template(rewrite_query_prompt, verbose=True)
chain = rewrite_prompt | llm

retriever = Retriever()

def count_tokens(context_data):
    """Counts total tokens in the retrieved context data."""
    return sum(len(text.split()) for document in context_data for text in document.values())

def rewrite_query(query):
    """Rewrites the user query using conversation history."""
    print(memory.load_memory_variables({}))
    history = memory.load_memory_variables({}).get("history", [])[-1:]  # Keep only the last 5 conversations

    return chain.invoke({"question": query, "history": history}).content

def generate_filtered_response(query, rerank_score_threshold=-5):
    """Generates a response using retrieved documents."""
    rewritten_query = rewrite_query(query)
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

                    Context: {top_n_document}

                    if there is greetings in the {rewritten_query} then greet.

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
                    "content": f" You are ETSU's conversational and context-aware QnA system. Answer the {query} strictly based on the following information only: {top_n_document}. If explicit/rough/sensitive language is detected in the query, respond saying 'Explicit language is prohibited.'"
                }
            ]
        )
        generated_text = response["message"]["content"]
        timestamp_holder.update({"TimeStamp": time.time() - start_time, "Model": "Ollama2- Local Server"})

    memory.chat_memory.add_user_message(rewritten_query)
    memory.chat_memory.add_ai_message(generated_text)

    return generated_text, top_n_document, citation_data, context_data, timestamp_holder