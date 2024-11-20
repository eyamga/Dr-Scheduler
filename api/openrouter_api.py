import aiohttp
import asyncio
import logging
import os
from dotenv import load_dotenv
from app.utils.error_handler import ProcessingError, APIError

# Load environment variables
load_dotenv()

# Get API configuration from environment
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = os.getenv('OPENROUTER_API_URL', 'https://openrouter.ai/api/v1/chat/completions')

class OpenRouterAPI:
    def __init__(self, api_key: str = OPENROUTER_API_KEY, model: str = None):
        self.api_key = api_key
        self.model = model
        self.logger = logging.getLogger(__name__)

    async def make_request(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }

        self.logger.info(f"Sending request to OpenRouter API with model: {self.model}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(OPENROUTER_API_URL, headers=headers, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    self.logger.info("API request successful")
                    return content
            except Exception as e:
                self.logger.error(f"API request failed: {str(e)}")
                raise APIError(f"API request failed: {str(e)}")