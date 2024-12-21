# LLaMA RAG System

A Retrieval-Augmented Generation system using LLaMA model and ChromaDB.

## Project Structure

```
llama-rag-engine/
├── api/                    # API layer
│   ├── endpoints/         # API endpoint implementations
│   ├── middleware/        # API middleware
│   └── routers/          # API route definitions
├── core/                  # Core RAG functionality
│   ├── document_processor/ # Document processing logic
│   ├── embeddings/        # Embedding generation
│   ├── llm/              # LLM integration
│   └── vector_store/     # Vector store operations
├── data/                  # Data storage
│   ├── documents/        # Raw documents
│   ├── processed/        # Processed documents
│   └── vectors/          # Vector store data
├── models/                # Model files
│   └── llama/           # LLaMA model files
├── docker/                # Docker configurations
├── tests/                 # Test suites
├── scripts/               # Utility scripts
├── config/                # Configuration files
└── notebooks/            # Jupyter notebooks
```

## Setup

1. Clone the repository: `git clone https://github.com/sudo-scorpion/llama-rag-engine.git`
2. Create a virtual environment: `python -m venv rag-env && source rag-env/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure
5. Run `docker-compose up` to start services

## Usage

[Add usage instructions here]

## Development

[Add development instructions here]
