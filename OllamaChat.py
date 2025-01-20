from ollama import chat, ChatResponse, AsyncClient
import dotenv

dotenv.load_dotenv()

class OllamaClient:
    def __init__(self):
        self.client = AsyncClient(
            host='http://localhost:11434',
        )
        self.messages = []
        self.messages.append({'role': 'user', 'content': 'Why is the sky blue?'})
        self.messages.append({'role': 'assistant', 'content': "The sky appears blue because of a phenomenon called scattering, which occurs when sunlight interacts with the tiny molecules of gases in the Earth's atmosphere.\n\nHere's what happens:\n\n1. Sunlight consists of a spectrum of colors, including all the colors of the visible light spectrum (red, orange, yellow, green, blue, indigo, and violet).\n2. When sunlight enters the Earth's atmosphere, it encounters tiny molecules of gases such as nitrogen (N2) and oxygen (O2).\n3. These gas molecules scatter the light in all directions, but they scatter shorter (blue) wavelengths more than longer (red) wavelengths.\n4. This is known as Rayleigh scattering, named after the British physicist Lord Rayleigh, who first described it in the late 19th century.\n5. As a result of this scattering, the blue light is dispersed throughout the atmosphere, giving the sky its blue appearance.\n\nIt's worth noting that the color of the sky can vary depending on several factors, such as:\n\n* Time of day: During sunrise and sunset, the sky can take on hues of red, orange, and pink due to the scattering of light by atmospheric particles.\n* Atmospheric conditions: Pollution, dust, and water vapor in the atmosphere can scatter light and change its color.\n* Altitude: The air is thinner at higher altitudes, which means there are fewer molecules to scatter the light. This can result in a more vibrant blue sky.\n\nSo, to summarize, the sky appears blue because of the scattering of sunlight by tiny gas molecules in the Earth's atmosphere, with shorter wavelengths (blue) being scattered more than longer wavelengths (red)."})

    async def ollama_chat_test(self):
        self.messages.append({'role': 'user', 'content': 'When was the phenomenon discovered?'})
        response = await self.client.chat(model='llama3.2', messages=self.messages)

        return response.message

    async def ollama_chat(self, message):
        ollama_message = {'role': 'user', 'content': message}
        self.messages.append(ollama_message)

        response = await self.client.chat(model='llama3.2', messages=self.messages)
        self.messages.append({'role': 'assistant', 'content': response.message.content})

        return response.message