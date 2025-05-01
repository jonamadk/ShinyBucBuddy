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
                You are a context-aware assistant that helps clarify user questions using their conversation history.

                Given:
                - The user's current query: "{question}"
                - A history of previous user queries: "{history}, where 0 index is the latest question"

                If the current query depends on or refers to the previous conversation, rewrite it to be a fully self-contained and contextually complete question.
                Otherwise return current query.

                Only return the rewritten query or the original query — do not include explanations or additional content.
                """

        
        self.rewrite_prompt = ChatPromptTemplate.from_template(rewrite_query_prompt, verbose=True)

        self.decorate_text_prompt = """
        You are a helpful assistant for East Tennessee State University students.

        **Decorate and format the following response text with Markdown syntax**:
        - **Use `**bold**`** to highlight the **main results**, key findings, important terms, or conclusions.
        - **Use `\\n` (newlines)** to clearly separate different ideas, steps, sections, or topics.
        - **DO NOT** add any new information not in the original text.

        Here is the text you need to decorate:

        "{raw_response}"

        Respond only with the decorated Markdown-formatted text.
        """

        # Initialize retriever
        self.retriever = Retriever()

    def count_tokens(self, context_data):
        """Counts total tokens in the retrieved context data."""
        return sum(len(text.split()) for document in context_data for text in document.values())

    def rewrite_query(self, query, history_userquery):
        """Rewrites the user query using the provided conversation history."""
        

    
        history = str({index:item for index, item in enumerate(history_userquery)} if history_userquery else "")
        rewritten_query = self.llm.predict(
            self.rewrite_prompt.format(question=query, history=history)
        )

        return rewritten_query

    def decorate_text(self, raw_response):
        """Decorates the raw LLM response with Markdown formatting."""
        decorated_text = self.llm.predict(
            self.decorate_text_prompt.format(raw_response=raw_response)
        )
        return decorated_text

    def generate_filtered_response(self, query, history_userquery, rerank_score_threshold=-5):
        """Generates a response using retrieved documents and decorates the final text."""
        # Rewrite query
        rewritten_query = self.rewrite_query(query, history_userquery)

        # Retrieve and rerank
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
                
                        Your identity is: "BucBuddy - conversational and context-aware QnA platform for East Tennessee State University who help to student to explore campus resources".
                        
                        Your task is to:
                        - Not to answer any other context questions - example joke, sexual content, news, internet topics, trends, songs etc.
                        - Answer the User question: {rewritten_query} **strictly based on the provided Context: {top_n_document}.**.
                        - Respond in a **friendly, conversational tone** suitable for students.
                        - **Do not fabricate** information not present in the context.
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

        # 🌟 NEW: Decorate generated text with Markdown
        decorated_text = self.decorate_text(generated_text)

        return decorated_text, top_n_document, citation_data, context_data, token_processing_details_holder
