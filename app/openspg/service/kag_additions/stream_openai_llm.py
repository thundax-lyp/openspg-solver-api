import logging

from kag.common.llm import OpenAIClient
from kag.interface import LLMClient

logger = logging.getLogger()


@LLMClient.register("stream_openai_llm")
class StreamOpenAIClient(OpenAIClient):
    """
    A client class for delegate LLM
    """

    def __init__(
            self,
            api_key: str,
            base_url: str,
            model: str,
            temperature: float = 0.7
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            stream=True,
            temperature=temperature
        )

    def __call__(self, prompt: str = "", image_url: str = None, **kwargs):
        message = [
            {"role": "system", "content": "you are a helpful assistant"},
            {"role": "user", "content": prompt},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=message,
            stream=self.stream,
            temperature=self.temperature
        )
        for chunk in response:
            yield chunk.choices[0].delta.content
        pass
