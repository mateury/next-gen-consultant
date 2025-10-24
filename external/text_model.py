from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
import os


class ModelConnector:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url="https://api.scaleway.ai/2d6e7638-f7f5-41f4-b61c-79209c1785be/v1",
            api_key=os.environ.get("OPENAI_API_KEY"),
            model="gpt-oss-120b",
            max_tokens=512,
            temperature=1,
            top_p=1,
            presence_penalty=0,
            streaming=True
        )
        self.parser = StrOutputParser()

    def get_model_response(self, input_text):
        output_text = ''
        messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content=input_text)
        ]

        # Stream the response
        for chunk in self.llm.stream(messages):
            if chunk.content:
                output_text += chunk.content

        print(output_text)
        return output_text