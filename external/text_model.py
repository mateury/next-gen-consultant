from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
import os
import json

class ModelConnector:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url="https://api.scaleway.ai/2d6e7638-f7f5-41f4-b61c-79209c1785be/v1",
            api_key=os.environ.get("SCW_SECRET_KEY"),
            model="gpt-oss-120b",
            max_tokens=512,
            temperature=1,
            top_p=1,
            presence_penalty=0,
            streaming=True
        )
        self.parser = StrOutputParser()
        self.system_prompt = json.load(open('external/model_prompts.json', 'r', encoding='utf-8'))['text_model']
        self.conversation_history = [SystemMessage(content=self.system_prompt)]

    async def get_model_response_streaming(self, input_text):
        """
        Get response from the model with async streaming.
        Yields chunks as they arrive and maintains conversation history.

        Args:
            input_text: User's message

        Yields:
            Text chunks as they arrive from the model
        """
        # Add user message to history
        self.conversation_history.append(HumanMessage(content=input_text))

        output_text = ''

        # Stream the response using async stream
        async for chunk in self.llm.astream(self.conversation_history):
            if chunk.content:
                output_text += chunk.content
                yield chunk.content

        # Add assistant's response to history after streaming is complete
        self.conversation_history.append(AIMessage(content=output_text))

    def clear_history(self, keep_system_prompt=True):
        """Clear conversation history, optionally keeping the system prompt."""
        if keep_system_prompt and len(self.conversation_history) > 0:
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []
