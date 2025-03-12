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
   git clone https://github.com/yourusername/BucBuddy.git
   cd BucBuddy
   ```

2. **Create and activate a virtual environment:**
    ```bash
    python3 -m venv env
    source env/bin/activate 
    ```