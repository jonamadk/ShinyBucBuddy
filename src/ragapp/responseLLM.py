import os
import time
import ollama
import logging
from openai import OpenAI
from ragapp.retriever import Retriever
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from config import OPENAI_API_KEY, SENTENCE_TRANSFORMER_MODEL_NAME
from sentence_transformers import SentenceTransformer, util


class ResponseLLM:
    def __init__(self):
        # Initialize API clients
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        # Define LLM
        self.llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.5)

        # Load sentence transformer model for similarity computation
        self.similarity_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)

        # Define query rewrite prompt
        rewrite_query_prompt = """
        Based on the provided user query: "{question}" and the history of previous user questions: "{history}",
        if the query is related to the history, rewrite the query based on the context of the history.
        Otherwise, return the original query: "{question}".
        """

        self.rewrite_prompt = ChatPromptTemplate.from_template(rewrite_query_prompt, verbose=True)

        # Initialize retriever
        self.retriever = Retriever()

    def count_tokens(self, context_data):
        """Counts total tokens in the retrieved context data."""
        return sum(len(text.split()) for document in context_data for text in document.values())

    def rewrite_query(self, query, history_userquery):
        """Rewrites the user query using the provided conversation history."""
        # Combine the last 4 user queries into a single history string
        history = ",".join(history_userquery) if history_userquery else ""

        # Use the rewrite prompt to rewrite the query
        rewritten_query = self.llm.predict(
            self.rewrite_prompt.format(question=query, history=history)
        )

        return rewritten_query

    def generate_filtered_response(self, query, history_userquery, rerank_score_threshold=-5):
        """Generates a response using retrieved documents."""
        # Rewrite the query using the provided history
        rewritten_query = self.rewrite_query(query, history_userquery)

        # Retrieve and rerank documents based on the rewritten query
        top_n_document, citation_data, context_data = self.retriever.retrieve_and_rerank(
            rewritten_query
        )

        total_token_count = self.count_tokens(context_data)
        token_processing_details_holder = {"Token Count": total_token_count}

        generation_kwargs = {
            "max_tokens": 500,
            "echo": True,
            "top_k": 1
        }

        llmChoiceGPT = True

        start_time = time.time()
        if llmChoiceGPT:
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                        Your identity is: "BucBuddy - conversational and context-aware QnA platform for East Tennessee State University."
                        Your job is to answer the user query in a conversational way strictly based on context.

                        Please just answer the question strictly based on the context.

                        User question: {rewritten_query}

                        Context: {top_n_document}.
                        """
                    }
                ]
            )
            generated_text = completion.choices[0].message.content
            token_processing_details_holder.update(
                {"Process-Time": time.time() - start_time, "Model": "GPT 4o Mini"})
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
            token_processing_details_holder.update(
                {"Process-Time": time.time() - start_time, "Model": "Ollama2- Local Server"})

        return generated_text, top_n_document, citation_data, context_data, token_processing_details_holder
