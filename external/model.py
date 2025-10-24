"""
Main model connector for Play virtual consultant.
"""

import os
from typing import Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from .prompts import SYSTEM_PROMPT, TOOL_PROCESSING_PROMPT
from .tool_executor import ToolExecutor


class ModelConnector:
    """
    Connects to the AI model and manages conversation history.
    Supports MCP tool execution and streaming responses.
    """
    
    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        """
        Initialize the model connector.
        
        Args:
            system_prompt: System prompt for the AI model
        """
        self.llm = ChatOpenAI(
            base_url="https://api.scaleway.ai/2d6e7638-f7f5-41f4-b61c-79209c1785be/v1",
            api_key=os.environ.get("SCW_SECRET_KEY"),
            model="gpt-oss-120b",
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            presence_penalty=0,
            streaming=True
        )
        
        self.parser = StrOutputParser()
        self.conversation_history = [SystemMessage(content=system_prompt)]
        self.tool_executor = ToolExecutor()
    
    async def _process_response_with_tools(
        self, 
        text: str, 
        stream_callback: Optional[Callable[[str], None]] = None,
        internal_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Process AI response and execute any tool commands found.
        
        Args:
            text: AI response text that may contain tool commands
            stream_callback: Optional callback for streaming to CLIENT
            internal_callback: Optional callback for internal logging only
            
        Returns:
            Final processed response text
        """
        # Find tool commands
        tool_results = []
        commands = self.tool_executor.find_tool_commands(text)
        
        if not commands:
            return text
        
        # Execute tools and collect results (DON'T stream to client)
        for command in commands:
            # Log internally but don't send to client
            if internal_callback:
                await internal_callback(f"\n🔧 Wykonuję narzędzie: {command}\n")
            
            result = await self.tool_executor.execute_command(command)
            tool_results.append((command, result))
            
            # Log result internally
            if internal_callback:
                await internal_callback(f"✅ Otrzymano wynik ({len(result)} znaków)\n")
        
        # Format results and create follow-up prompt
        tool_results_text = self.tool_executor.format_tool_results(tool_results)
        follow_up_prompt = TOOL_PROCESSING_PROMPT.format(
            tool_results=tool_results_text
        )
        
        # Add to history and get final response
        self.conversation_history.append(HumanMessage(content=follow_up_prompt))
        
        # Stream ONLY the final AI response to client (not tool results)
        final_response = ''
        async for chunk in self.llm.astream(self.conversation_history):
            if chunk.content:
                final_response += chunk.content
                # This goes to the client
                if stream_callback:
                    await stream_callback(chunk.content)
        
        return final_response
    
    async def get_model_response(
        self, 
        input_text: str, 
        stream_callback: Optional[Callable[[str], None]] = None,
        internal_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Get response from the AI model with tool support.
        
        Args:
            input_text: User's message
            stream_callback: Optional callback for streaming to CLIENT
            internal_callback: Optional callback for internal logging only
        
        Returns:
            Complete response text
        """
        # Add user message to history
        self.conversation_history.append(HumanMessage(content=input_text))
        
        # Get initial response from model
        output_text = ''
        async for chunk in self.llm.astream(self.conversation_history):
            if chunk.content:
                output_text += chunk.content
                # Stream to client
                if stream_callback:
                    await stream_callback(chunk.content)
        
        # Check if response contains tool commands
        tools_found = self.tool_executor.find_tool_commands(output_text)
        
        if tools_found:
            # Add initial AI response to history
            self.conversation_history.append(AIMessage(content=output_text))
            
            # Log tool detection internally
            if internal_callback:
                await internal_callback(f"\n⚙️ Wykryto {len(tools_found)} narzędzi: {tools_found}\n")
            
            # Execute tools and get final response
            # Note: This will REPLACE what was already streamed to client
            final_text = await self._process_response_with_tools(
                output_text, 
                stream_callback,
                internal_callback
            )
            
            # Add final response to history
            self.conversation_history.append(AIMessage(content=final_text))
            
            return final_text
        else:
            # No tools needed, just add response to history
            self.conversation_history.append(AIMessage(content=output_text))
            return output_text
    
    # History management methods
    
    def get_history(self) -> list:
        """Get the current conversation history."""
        return self.conversation_history
    
    def clear_history(self, keep_system_prompt: bool = True):
        """
        Clear conversation history.
        
        Args:
            keep_system_prompt: If True, keeps the system prompt
        """
        if keep_system_prompt and len(self.conversation_history) > 0:
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []
    
    def set_system_prompt(self, prompt: str):
        """
        Update the system prompt.
        
        Args:
            prompt: New system prompt text
        """
        if (len(self.conversation_history) > 0 and 
            isinstance(self.conversation_history[0], SystemMessage)):
            self.conversation_history[0] = SystemMessage(content=prompt)
        else:
            self.conversation_history.insert(0, SystemMessage(content=prompt))
    
    def get_stats(self) -> dict:
        """
        Get conversation statistics.
        
        Returns:
            Dictionary with message counts by type
        """
        return {
            "total_messages": len(self.conversation_history),
            "user_messages": sum(
                1 for msg in self.conversation_history 
                if isinstance(msg, HumanMessage)
            ),
            "ai_messages": sum(
                1 for msg in self.conversation_history 
                if isinstance(msg, AIMessage)
            ),
            "system_messages": sum(
                1 for msg in self.conversation_history 
                if isinstance(msg, SystemMessage)
            )
        }