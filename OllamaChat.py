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
    # "You are to respond ONLY in valid JSON format. "
    # "Your output MUST be a JSON object with EXACTLY one key: 'result'. "
    # "The value associated with 'result' should be a single string containing at least 1 sentence separated by spaces. "
    # "Make sure to adhere to this valid JSON format, so that the response is serializable on Python. "
    # "Do not include any extra keys, explanations, markdown formatting, HTML, or extraneous escape characters. "
    # "Ensure that all strings are formatted in valid JSON, i.e., no unnecessary escape characters are inserted. "
    "Do not include markdown formatting. "
    "Make sure to just give a response to the given input. "
    "The input will always be in the following format: [date in format %Y-%m-%d %H.%M:%S] <user who was talking>: transcribed speech "
    "An example of the input: [2025-05-12 13.59:53] <John>:  What is Python? "
    "In some cases the input will include multiple lines of the previously mentioned format. "
    "Do no include the date or speaker information as in the input in your response. "
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

    async def ollama_chat(self, message) -> dict:
        ollama_message = {
            'role': 'user',
            'content': message
        }
        self.messages.append(ollama_message)

        try:
            response: ChatResponse = await self.client.chat(model='llama3.2:3b', messages=self.messages)
            self.messages.append({'role': 'assistant', 'content': response.message.content})

            return {"success": True, "response": response.message.content}
        except Exception as e:
            return {"success": False, "error": e}
