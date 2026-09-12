import ai
import asyncio
import logging
from pydantic import BaseModel

async def hello_world():
    class HelloWorldResponse(BaseModel):
        message: str
    response = await ai.responses(
        "openai/gpt-5-nano",
        [{"role": "system", "content": "You are a helpful assistant that outputs everything in reverse."},
         {"role": "user", "content": "Say 'hello world'"}],
        text_format=HelloWorldResponse)
    logging.info(response.message)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(hello_world())
