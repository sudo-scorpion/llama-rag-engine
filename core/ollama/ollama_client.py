from typing import Dict, Optional, Any
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, Field
import os
import json
from enum import Enum
from core.logger.app_logger import logger

class OllamaModelConfig(BaseModel):
    """Configuration for Ollama model settings"""
    name: str = Field(default="llama3.2:3b")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    context_size: int = Field(default=2048)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=0)
    repeat_penalty: float = Field(default=1.1, ge=0.0)

class OllamaEndpoint(str, Enum):
    """Ollama API endpoints"""
    GENERATE = "generate"
    CHAT = "chat"
    EMBEDDINGS = "embeddings"

class OllamaConnectionConfig(BaseModel):
    """Configuration for Ollama connection settings"""
    base_url: str = Field(default="http://localhost")
    port: str = Field(default="11434")
    timeout: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    keepalive_connections: int = Field(default=5, ge=0)
    max_connections: int = Field(default=10, ge=0)

    @property
    def api_base(self) -> str:
        """Get the base API URL"""
        return f"{self.base_url.rstrip('/')}:{self.port}/api"

class OllamaClient:
    """
    Enhanced client for interacting with Ollama API.
    Handles all network communication with Ollama endpoints with improved configuration.
    """
    
    def __init__(
        self,
        model_config: Optional[OllamaModelConfig] = None,
        connection_config: Optional[OllamaConnectionConfig] = None
    ):
        # Load configurations
        self.model_config = model_config or OllamaModelConfig(
            name=os.getenv("OLLAMA_MODEL_NAME", "llama3.2:3b"),
            temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
        )
        
        self.connection_config = connection_config or OllamaConnectionConfig(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost"),
            port=os.getenv("OLLAMA_PORT", "11434")
        )
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=self.connection_config.timeout,
            limits=httpx.Limits(
                max_keepalive_connections=self.connection_config.keepalive_connections,
                max_connections=self.connection_config.max_connections
            )
        )
        
        logger.info(f"Initialized Ollama client for {self.model_config.name} at {self.connection_config.api_base}")

    def _get_endpoint_url(self, endpoint: OllamaEndpoint) -> str:
        """Get full URL for specified endpoint"""
        return f"{self.connection_config.api_base}/{endpoint.value}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Generate a response from Ollama model with enhanced configuration.
        
        Args:
            prompt: The input prompt
            temperature: Optional override for default temperature
            stream: Whether to stream the response
            options: Additional model options
            
        Returns:
            Dictionary containing the response and metadata
        """
        try:
            # Prepare payload with model configuration
            payload = {
                "model": self.model_config.name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature or self.model_config.temperature,
                    "top_p": self.model_config.top_p,
                    "top_k": self.model_config.top_k,
                    "repeat_penalty": self.model_config.repeat_penalty,
                }
            }
            
            # Add any additional options
            if options:
                payload["options"].update(options)
                
            logger.debug(f"Sending request to Ollama: {json.dumps(payload, indent=2)}")
            
            async with httpx.AsyncClient(
                timeout=self.connection_config.timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=self.connection_config.keepalive_connections,
                    max_connections=self.connection_config.max_connections
                )
            ) as client:
                response = await client.post(
                    self._get_endpoint_url(OllamaEndpoint.GENERATE),
                    json=payload
                )
                
                response.raise_for_status()
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'response': result.get('response', ''),
                        'metadata': {
                            'model': self.model_config.name,
                            'total_duration': result.get('total_duration'),
                            'load_duration': result.get('load_duration'),
                            'prompt_eval_count': result.get('prompt_eval_count'),
                            'eval_count': result.get('eval_count'),
                            'options_used': payload['options']
                        }
                    }
                else:
                    raise Exception(f"Unexpected status code: {response.status_code}")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Ollama request: {str(e)}")
            logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response'}")
            raise
        except Exception as e:
            logger.error(f"Error during Ollama request: {str(e)}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Enhanced health check with detailed status"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.connection_config.base_url}:{self.connection_config.port}")
                return {
                    'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                    'code': response.status_code,
                    'model': self.model_config.name,
                    'connection': {
                        'base_url': self.connection_config.base_url,
                        'port': self.connection_config.port
                    }
                }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'model': self.model_config.name
            }

    async def cleanup(self):
        """Cleanup client resources"""
        try:
            await self.http_client.aclose()
            logger.info(f"Ollama client cleaned up for model {self.model_config.name}")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return {
            'model': self.model_config.dict(),
            'connection': self.connection_config.dict()
        }

    def __repr__(self) -> str:
        return f"OllamaClient(model={self.model_config.name}, url={self.connection_config.api_base})"

async def main():
    # Custom configuration
    model_config = OllamaModelConfig(
        name="llama3.2:3b",
        temperature=0.8,
        context_size=2048
    )

    connection_config = OllamaConnectionConfig(
        base_url="http://localhost",
        port="11434",
        timeout=30.0
    )

    # Initialize client with custom config
    client = OllamaClient(
        model_config=model_config,
        connection_config=connection_config
    )

    # Generate response
    response =  await client.generate("What is the meaning of life?")
    print(response)

    # Check health
    health_status =  await client.health_check()
    print(health_status)

    # Get current configuration
    config = client.get_config()
    print(config)

    # Cleanup
    await client.cleanup()


if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
