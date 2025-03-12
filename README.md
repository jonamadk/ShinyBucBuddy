# ShinyBucBuddy

The deployment-ready BucBuddy application!

## Table of Contents

- [ShinyBucBuddy](#shinybucbuddy)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Installation](#installation)

## Introduction

ShinyBucBuddy is a conversational and context-aware QnA platform designed for East Tennessee State University. It leverages advanced natural language processing models to provide accurate and relevant responses to user queries based on the context.

## Features

- Conversational AI for answering queries related to East Tennessee State University.
- Context-aware responses using advanced embedding and reranking techniques.
- Integration with OpenAI for generating embeddings and responses.
- Logging of queries and responses for analysis and improvement.

## Project Structure

└── ShinyBucBuddy
    ├── BUCDB
    ├── logs
    │   ├── response_data.json
    │   └── response_timestamp.json
    ├── src
    │   ├── app.py
    │   ├── config.py
    │   ├── responseLLM.py
    │   ├── responselog.py
    │   └── retriever.py
    └── templates
          └── chat.html

## Installation

1. **Clone the repository:**

   ```sh
   git clone https://github.com/yourusername/ShinyBucBuddy.git
   cd ShinyBucBuddy
   ```

2. **Create and activate a virtual environment:**