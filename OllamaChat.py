import asyncio

from ollama import chat, ChatResponse, AsyncClient
import dotenv
import json

dotenv.load_dotenv()

# system_message = (
#     "You are to respond ONLY in valid JSON format. "
#     "Your output MUST be a JSON object with EXACTLY one key: 'result'. "
#     "The value associated with 'result' should be a list containing at least 1 sentence. "
#     "Do not include any additional keys, commentary, or markdown formatting."
# )

system_message = (
    "You are to respond ONLY in valid JSON format. "
    "Your output MUST be a JSON object with EXACTLY one key: 'result'. "
    "The value associated with 'result' should be a single string containing at least 1 sentence separated by spaces. "
    "Do not include any extra keys, explanations, or markdown formatting."
)


class OllamaClient:
    def __init__(self):
        self.client = AsyncClient(
            host='http://localhost:11434',
        )
        self.messages = [
            {
                "role": "system",
                "content": system_message
            }
        ]

    async def ollama_chat(self, message):
        ollama_message = {
            'role': 'user',
            'content': message
        }
        self.messages.append(ollama_message)

        response: ChatResponse = await self.client.chat(model='llama3.2:3b', messages=self.messages)
        self.messages.append({'role': 'assistant', 'content': response.message.content})

        return response.message.content