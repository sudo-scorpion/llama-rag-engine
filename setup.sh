#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to stop a service if it is running
stop_service() {
    local service_name=$1
    local service_command=$2
    if pgrep -f "$service_command" > /dev/null; then
        echo "Stopping $service_name..."
        pkill -f "$service_command"
    fi
}

# Function to start services
start_services() {
    # Create logs directory if it doesn't exist
    mkdir -p ./logs

    # Pull the Ollama model
    echo "Pulling the Ollama model..."
    ollama pull llama3.2:3b

    # Start the Ollama server
    echo "Starting the Ollama server..."
    nohup ollama serve > ./logs/ollama_server.log 2>&1 &

    # Check if Redis is installed
    if ! command_exists redis-server; then
        echo "Redis is not installed. Please install Redis and try again."
        exit 1
    fi

    # Start the Redis server
    echo "Starting the Redis server..."
    nohup redis-server > ./logs/redis_server.log 2>&1 &

    # Check if ChromaDB is installed
    if ! command_exists chroma; then
        echo "ChromaDB is not installed. Please install ChromaDB and try again."
        exit 1
    fi

    # Start the ChromaDB server
    echo "Starting the ChromaDB server..."
    nohup chroma run --path ./db/chromadb > ./logs/chroma_server.log 2>&1 &

    # Start the FastAPI application
    echo "Starting the FastAPI application..."
    # nohup python3 app.py > ./logs/fastapi_server.log 2>&1 &

    echo "Setup complete. All services are running."
}

# Function to stop all services
stop_services() {
    stop_service "Ollama server" "ollama serve"
    stop_service "Redis server" "redis-server"
    stop_service "ChromaDB server" "chroma run"
    stop_service "FastAPI application" "app.py"
    echo "All services stopped."
}

# Function to restart all services
restart_services() {
    stop_services
    start_services
}

# Main script logic
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac