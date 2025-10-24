"""
Tool execution logic for MCP commands.
"""

import re
import json
from typing import List, Tuple, Optional, Callable
from .mcp_server import check_customer, get_product_catalog


class ToolExecutor:
    """Handles execution of MCP tool commands."""
    
    # Regex pattern for finding tool commands
    TOOL_PATTERN = r'\[(?:CHECK_CUSTOMER:[^\]]+|GET_CATALOG)\]'
    
    @staticmethod
    def find_tool_commands(text: str) -> List[str]:
        """
        Find all tool commands in the text.
        
        Args:
            text: Text to search for tool commands
            
        Returns:
            List of tool command strings (e.g., "[CHECK_CUSTOMER: 12345]")
        """
        return re.findall(ToolExecutor.TOOL_PATTERN, text, re.IGNORECASE)
    
    @staticmethod
    async def execute_command(command: str) -> str:
        """
        Execute a single tool command.
        
        Args:
            command: Tool command string (e.g., "[CHECK_CUSTOMER: 12345]")
            
        Returns:
            Result from the tool as a string
        """
        try:
            # [CHECK_CUSTOMER: pesel]
            if command.upper().startswith("[CHECK_CUSTOMER:"):
                pesel = command[16:-1].strip()
                return await check_customer(pesel)
            
            # [GET_CATALOG]
            elif command.upper().startswith("[GET_CATALOG"):
                return await get_product_catalog(None)
            
            else:
                return f"❌ Nieznana komenda: {command}"
                
        except json.JSONDecodeError as e:
            return f"❌ Błąd parsowania JSON: {str(e)}"
        except Exception as e:
            return f"❌ Błąd wykonania narzędzia: {str(e)}"
    
    @staticmethod
    async def execute_all_commands(
        text: str, 
        callback: Optional[Callable[[str], None]] = None
    ) -> List[Tuple[str, str]]:
        """
        Execute all tool commands found in text.
        
        Args:
            text: Text containing tool commands
            callback: Optional async callback for streaming progress
            
        Returns:
            List of (command, result) tuples
        """
        commands = ToolExecutor.find_tool_commands(text)
        
        if not commands:
            return []
        
        results = []
        for command in commands:
            if callback:
                await callback(f"\n\n🔧 Wykonuję: {command}\n\n")
            
            result = await ToolExecutor.execute_command(command)
            results.append((command, result))
            
            if callback:
                await callback(result)
                await callback("\n\n")
        
        return results
    
    @staticmethod
    def format_tool_results(results: List[Tuple[str, str]]) -> str:
        """
        Format tool results for inclusion in prompt.
        
        Args:
            results: List of (command, result) tuples
            
        Returns:
            Formatted string with all results
        """
        return "\n\n".join([
            f"WYNIK NARZĘDZIA {cmd}:\n{res}" 
            for cmd, res in results
        ])