#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project name
PROJECT_NAME="llama-rag"

echo -e "${BLUE}Creating project structure for ${PROJECT_NAME}...${NC}"

# Create main project directory
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Create directory structure
directories=(
    "api/endpoints"
    "api/middleware"
    "api/routers"
    "core/document_processor"
    "core/embeddings"
    "core/llm"
    "core/vector_store"
    "data/documents"
    "data/processed"
    "data/vectors"
    "models/llama"
    "docker/development"
    "docker/production"
    "tests/unit"
    "tests/integration"
    "tests/e2e"
    "scripts/setup"
    "scripts/utils"
    "config/development"
    "config/production"
    "notebooks"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    echo -e "${GREEN}Created directory: $dir${NC}"
done

# Create essential files
touch README.md
touch requirements.txt
touch .gitignore
touch .env.example
touch docker-compose.yml
touch Dockerfile

# Create config files
cat > config/development/config.yml << EOL
# Development Configuration
app:
  name: llama-rag
  version: 0.1.0
  environment: development

vector_store:
  backend: chromadb
  settings:
    chroma_db_impl: duckdb+parquet
    persist_directory: data/vectors

llm:
  model: llama-2-3b
  model_path: models/llama
  max_tokens: 2048
  temperature: 0.7

document_processor:
  chunk_size: 500
  chunk_overlap: 50
  max_documents: 1000

cache:
  backend: redis
  ttl: 3600
EOL

# Create main Python package files
touch __init__.py
mkdir -p llama_rag
touch llama_rag/__init__.py

# Create example configuration files
cat > .env.example << EOL
# Environment Configuration
APP_ENV=development
DEBUG=true

# Vector Store
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM Settings
MODEL_PATH=/app/models/llama-2-3b
MAX_TOKENS=2048
EOL

# Create initial README
cat > README.md << EOL
# LLaMA RAG System

A Retrieval-Augmented Generation system using LLaMA model and ChromaDB.

## Project Structure

\`\`\`
llama-rag/
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
\`\`\`

## Setup

1. Clone the repository
2. Create a virtual environment
3. Install dependencies: \`pip install -r requirements.txt\`
4. Copy \`.env.example\` to \`.env\` and configure
5. Run \`docker-compose up\` to start services

## Usage

[Add usage instructions here]

## Development

[Add development instructions here]
EOL

# Create gitignore
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
.env
data/documents/*
data/processed/*
data/vectors/*
models/llama/*
*.db
*.sqlite3

# Logs
*.log
logs/

# System
.DS_Store
Thumbs.db
EOL

# Create initial requirements.txt
cat > requirements.txt << EOL
fastapi>=0.68.0
uvicorn>=0.15.0
pydantic>=1.8.2
python-dotenv>=0.19.0
chromadb>=0.4.0
redis>=4.0.0
torch>=2.0.0
transformers>=4.30.0
sentence-transformers>=2.2.0
python-multipart>=0.0.5
sqlalchemy>=1.4.0
pyyaml>=6.0
pytest>=7.0.0
pytest-asyncio>=0.20.0
httpx>=0.24.0
pdfreader>=0.1.12
tiktoken>=0.4.0
EOL

# Create docker-compose.yml
cat > docker-compose.yml << EOL
version: '3.8'

services:
  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
    volumes:
      - ./data/vectors:/chroma/data
    environment:
      - CHROMA_DB_IMPL=duckdb+parquet
    ports:
      - "8000:8000"

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  rag_app:
    build: .
    volumes:
      - .:/app
      - ./data:/app/data
      - ./rag_metadata.db:/app/rag_metadata.db
    environment:
      - CHROMA_HOST=chromadb
      - REDIS_HOST=redis
    depends_on:
      - chromadb
      - redis
    ports:
      - "8080:8080"

volumes:
  redis_data:
EOL

# Create Dockerfile
cat > Dockerfile << EOL
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements