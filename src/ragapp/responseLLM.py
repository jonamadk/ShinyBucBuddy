import os
import re
import time
import logging
from openai import OpenAI
from .retriever import Retriever
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, SENTENCE_TRANSFORMER_MODEL_NAME
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class ResponseLLM:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.5)
        self.similarity_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)

        rewrite_query_prompt = """
                Given:
                - The user's current query: "{question}"
                - A history of previous user queries: "{history}"

                If the current query refers to the previous conversation by (his, her, this, that, it, etc.), then rewrite {question} to make it context aware and return the rewritten question.
                ELSE return the current query {question}.
                """
        self.rewrite_prompt = ChatPromptTemplate.from_template(rewrite_query_prompt, verbose=True)

        self.decorate_text_prompt = """
        You are a text formatter. Format the text below using `**bold**` to highlight important terms.
        Return only the formatted text, nothing else.

        Text: {raw_response}
        """

        self.retriever = Retriever()

    def count_tokens(self, context_data):
        return sum(len(text.split()) for document in context_data for text in document.values())

    def rewrite_query(self, query, history_userquery):
        history = str({index: item for index, item in enumerate(history_userquery)} if history_userquery else "")
        rewritten_query = self.llm.invoke(
            self.rewrite_prompt.format_messages(question=query, history=history)
        ).content
        return rewritten_query

    def decorate_text(self, raw_response):
        decorated_text = self.llm.invoke(
            self.decorate_text_prompt.format(raw_response=raw_response)
        ).content
        return decorated_text

    def extract_location_from_response(self, user_query, bot_response):
        """
        Uses the LLM to extract a specific campus building or location name
        from the bot's response.
        """
        extraction_prompt = f"""You are a location extractor for ETSU (East Tennessee State University) campus.

Given:
- User question: "{user_query}"
- Assistant response: "{bot_response}"

Task: If the assistant's response mentions a SPECIFIC campus building, office, or physical location at ETSU, extract its full official name.

Rules:
- Return ONLY the full official building/location name, nothing else
- If the response mentions multiple locations, return only the most relevant one
- If no specific building or location is mentioned, return exactly: NONE
- Do not add any explanation, punctuation, or extra words
- Correct any spelling errors in the location name to its official form

Examples of valid responses: "D.P. Culp University Center", "Sherrod Library", "Warf-Pickel Hall", "Sam Wilson Hall"

Your response:"""

        try:
            result = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": extraction_prompt}],
                max_tokens=30,
                temperature=0
            )
            extracted = result.choices[0].message.content.strip()

            if not extracted or extracted.upper() == "NONE" or len(extracted) < 4:
                return None

            logger.debug(f"Extracted location: {extracted}")
            return extracted

        except Exception as e:
            logger.error(f"Location extraction failed: {str(e)}")
            return None

    def build_google_maps_link(self, building_name):
        """Builds a Google Maps search URL for a given ETSU building name."""
        search_query = f"{building_name} ETSU Johnson City Tennessee"
        encoded_query = search_query.replace(" ", "+")
        return f"https://www.google.com/maps/search/{encoded_query}"

    def build_chat_messages(self, system_prompt, conversation_history, current_query, top_n_document):
        """
        Builds the full messages array for the OpenAI API call,
        including system prompt, previous conversation turns,
        and the current query with retrieved context.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            recent_history = conversation_history[-6:]
            for turn in recent_history:
                user_q = turn.get("userquery", "").strip()
                bot_a = turn.get("llmresponse", "").strip()
                if user_q:
                    messages.append({"role": "user", "content": user_q})
                if bot_a:
                    messages.append({"role": "assistant", "content": bot_a})

        messages.append({
            "role": "user",
            "content": f"Answer this question: {current_query}\n\nBased strictly on this context: {top_n_document}"
        })

        return messages


    def generate_streaming_response(self, query, history_userquery, conversation_history=None):
        """
        Generator that yields SSE chunks for streaming to the frontend.
        Yields text tokens as they are generated, then a final JSON metadata chunk.
        """
        import json as _json

        rewritten_query = self.rewrite_query(query, history_userquery)

        top_5_retrieved, top_n_document, citation_data, context_data = self.retriever.retrieve_and_rerank(
            rewritten_query
        )

        total_token_count = self.count_tokens(context_data)

        system_prompt = """You are BucBuddy, a conversational and context-aware Q&A assistant for East Tennessee State University (ETSU).
Your job is to help students explore campus resources, programs, and services.
- If the user sends a greeting like "Hi", "Hello", or "Hey", respond warmly, introduce yourself as BucBuddy, and invite them to ask about ETSU.
- Only answer questions related to ETSU. Do not answer jokes, news, trends, or unrelated topics.
- Do not fabricate information. Only use what is provided in the context.
- Be conversational and remember what was discussed earlier in the conversation.
- When you mention a building or campus location, always use its full official name."""

        messages = self.build_chat_messages(
            system_prompt=system_prompt,
            conversation_history=conversation_history or [],
            current_query=rewritten_query,
            top_n_document=top_n_document
        )

        start_time = time.time()
        generated_text = ""

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500,
            stream=True
        )

        for chunk in completion:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                generated_text += delta
                yield f"data: {_json.dumps({'type': 'token', 'content': delta})}\n\n"

        # Skip decorate_text in streaming — avoids a second LLM pause after streaming
        # The GPT response already uses markdown naturally
        decorated_text = generated_text

        # Still append Google Maps link if a campus location is mentioned
        building_name = self.extract_location_from_response(query, decorated_text)
        if building_name:
            maps_url = self.build_google_maps_link(building_name)
            maps_chunk = f"\n\n\U0001f4cd [View **{building_name}** on Google Maps]({maps_url})"
            decorated_text += maps_chunk
            yield f"data: {_json.dumps({'type': 'token', 'content': maps_chunk})}\n\n"

        process_time = time.time() - start_time
        token_count = self.count_tokens(context_data)

        # Final metadata chunk
        metadata = {
            "type": "done",
            "full_text": decorated_text,
            "citation_data": citation_data,
            "top_5_retrieved": top_5_retrieved,
            "top_n_document": top_n_document,
            "token_count": token_count,
            "process_time": process_time,
        }
        yield f"data: {_json.dumps(metadata)}\n\n"

    def generate_filtered_response(self, query, history_userquery, conversation_history=None, rerank_score_threshold=-5):
        """
        Generates a response using retrieved documents and decorates the final text.
        Returns top_5_retrieved (before reranking) and top_n_document (after reranking)
        so both can be saved to the database for metrics evaluation.
        """
        # Rewrite query to be context-aware
        rewritten_query = self.rewrite_query(query, history_userquery)

        # Retrieve and rerank — now returns top_5_retrieved separately
        top_5_retrieved, top_n_document, citation_data, context_data = self.retriever.retrieve_and_rerank(
            rewritten_query
        )

        total_token_count = self.count_tokens(context_data)
        token_processing_details_holder = {"Token Count": total_token_count}

        llmChoiceGPT = True
        start_time = time.time()

        if llmChoiceGPT:
            system_prompt = """You are BucBuddy, a conversational and context-aware Q&A assistant for East Tennessee State University (ETSU).
Your job is to help students explore campus resources, programs, and services.
- If the user sends a greeting like "Hi", "Hello", or "Hey", respond warmly, introduce yourself as BucBuddy, and invite them to ask about ETSU.
- Only answer questions related to ETSU. Do not answer jokes, news, trends, or unrelated topics.
- Do not fabricate information. Only use what is provided in the context.
- Be conversational and remember what was discussed earlier in the conversation.
- When you mention a building or campus location, always use its full official name."""

            messages = self.build_chat_messages(
                system_prompt=system_prompt,
                conversation_history=conversation_history or [],
                current_query=rewritten_query,
                top_n_document=top_n_document
            )

            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                stream=True
            )

            generated_text = ""
            for chunk in completion:
                delta = chunk.choices[0].delta.content or ""
                generated_text += delta

            token_processing_details_holder.update(
                {"Process-Time": time.time() - start_time, "Model": "GPT 4o Mini"})
        else:
            import ollama
            response = ollama.chat(
                model="llama2",
                messages=[{
                    "role": "user",
                    "content": f"You are ETSU's conversational and context-aware QnA system. Answer the {query} strictly based on the following information only: {top_n_document}."
                }]
            )
            generated_text = response["message"]["content"]
            token_processing_details_holder.update(
                {"Process-Time": time.time() - start_time, "Model": "Ollama2- Local Server"})

        # Decorate with markdown
        decorated_text = self.decorate_text(generated_text)

        # Append Google Maps link if a campus location is mentioned
        building_name = self.extract_location_from_response(query, decorated_text)
        if building_name:
            maps_url = self.build_google_maps_link(building_name)
            decorated_text += f"\n\n📍 [View **{building_name}** on Google Maps]({maps_url})"

        # Return top_5_retrieved as extra value so views.py can save it
        return decorated_text, top_5_retrieved, top_n_document, citation_data, context_data, token_processing_details_holder