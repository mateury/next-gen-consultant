from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
import os

class ModelConnector:
    def __init__(self, system_prompt="You are a helpful assistant"):
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
        self.conversation_history = [SystemMessage(content=system_prompt)]

    def get_model_response(self, input_text, stream_output=True):
        """
        Get response from the model and maintain conversation history.

        Args:
            input_text: User's message
            stream_output: Whether to print streaming output (default: True)

        Returns:
            Complete response text
        """
        # Add user message to history
        self.conversation_history.append(HumanMessage(content=input_text))

        output_text = ''

        # Stream the response
        for chunk in self.llm.stream(self.conversation_history):
            if chunk.content:
                output_text += chunk.content
                if stream_output:
                    print(chunk.content, end='', flush=True)

        if stream_output:
            print()  # New line after streaming

        # Add assistant's response to history
        self.conversation_history.append(AIMessage(content=output_text))

        return output_text

    def clear_history(self, keep_system_prompt=True):
        """Clear conversation history, optionally keeping the system prompt."""
        if keep_system_prompt and len(self.conversation_history) > 0:
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []

    def get_history(self):
        """Get the current conversation history."""
        return self.conversation_history

    def set_system_prompt(self, prompt):
        """Update the system prompt."""
        if len(self.conversation_history) > 0 and isinstance(self.conversation_history[0], SystemMessage):
            self.conversation_history[0] = SystemMessage(content=prompt)
        else:
            self.conversation_history.insert(0, SystemMessage(content=prompt))
