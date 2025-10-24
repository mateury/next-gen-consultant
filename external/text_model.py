from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
import os
import requests


JAVA_BACKEND_URL = "http://localhost:8080/"


def get_customer_by_pesel(pesel: int) -> dict:
    """Get customer information by PESEL number.
    
    Args:
        pesel: Customer's PESEL identification number
        
    Returns:
        Dictionary containing customer information
    """
    url = f"{JAVA_BACKEND_URL}/customer"
    try:
        res = requests.get(url, params={"pesel": pesel})
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}


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
            streaming=False  # Disable streaming for tool calls
        )
        
        # Define available tools
        self.tools = [get_customer_by_pesel]
        
        # Bind tools to the model
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        self.parser = StrOutputParser()

    def get_model_response(self, input_text):
        messages = [
            SystemMessage(content="Jesteś sprzedawcą w salonie operatora telekomunikacyjnego PLAY, jesteś pomocny i użyteczny. Gdy klient poda swój PESEL, użyj funkcji get_customer_by_pesel aby pobrać jego dane."),
            HumanMessage(content=input_text)
        ]

        # Get initial response from model
        response = self.llm_with_tools.invoke(messages)
        
        # Check if model wants to call tools
        while response.tool_calls:
            print(f"Model requested tool calls: {response.tool_calls}")
            
            # Add AI message to conversation
            messages.append(response)
            
            # Execute each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                print(f"Executing tool: {tool_name} with args: {tool_args}")
                
                # Execute the tool
                if tool_name == "get_customer_by_pesel":
                    result = get_customer_by_pesel(**tool_args)
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                
                print(f"Tool result: {result}")
                
                # Add tool result to messages
                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id
                ))
            
            # Get next response from model
            response = self.llm_with_tools.invoke(messages)
        
        # Return final text response
        output_text = response.content if hasattr(response, 'content') else str(response)
        print(f"Final response: {output_text}")
        return output_text