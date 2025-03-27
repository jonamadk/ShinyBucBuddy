# BucBuddy

The deployment-ready BucBuddy application!

## Table of Contents

- [BucBuddy](#bucbuddy)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Features](#features)
  - [Project Structure](#project-structure)
- [BucBuddy Directory Tree](#bucbuddy-directory-tree)

## Introduction

BucBuddy is a conversational and context-aware QnA platform designed for East Tennessee State University. It leverages advanced natural language processing models to provide accurate and relevant responses to user queries based on the context.

## Features

- Conversational AI for answering queries related to East Tennessee State University.
- Context-aware responses using advanced embedding and reranking techniques.
- Integration with OpenAI for generating embeddings and responses.
- Logging of queries and responses for analysis and improvement.

## Project Structure

# BucBuddy Directory Tree

- **BucBuddy/**
  - **BUCDB/** - Database directory
  - **logs/** - Log files directory
    - `response_data.json` - Response data log
    - `response_timestamp.json` - Response timestamp log
  - **src/** - Source code directory
    - `app.py` - Main application file
    - `config.py` - Configuration file
    - `responseLLM.py` - LLM response handling
    - `responselog.py` - Response logging
    - `retriever.py` - Data retrieval script
  - **templates/** - HTML templates directory
    - `chat.html` - Chat interface template


1. **Clone the repository:**

   ```sh
   git clone https://github.com/jonamadk/ShinyBucBuddy
   cd BucBuddy
   ```


2. **Build and Run service**
    To build the docker images
    ```bash
    docker-compose up --build   
    ```
   To run the container
   ```bash
   docker-compose up
   ```
    This should create the docker container that runs on two containers
    > 1. Chroma Vector Database Container -> *chroma-1*
    Check if database instance is active or not through below endpoint:
     ```bash
       http://localhost:8000/health
      ```
      
    > 2. Server Application Container -> *my-flask-cont*
    Check if server is active or not through below endpoint:
      ```bash
       http://localhost:8000/chat
      ```
    
3. **Add the Embedded Document**
    In case server responds no collection found, there is possibility that there is no vector embeddings/documents in database. 

    **To embed and push data in Chroma DB:**
    Send the post request to /embed to perform embedding through endpoint:
    ```bash
    http://localhost:8000/embed
    ```
    This should add the documents in the vector database. Once you run the client application, you should be able to get response !