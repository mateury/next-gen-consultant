"""
Tool execution logic for MCP commands.
"""

import re
import json
from typing import List, Tuple, Optional, Callable
from .mcp_server import check_customer, get_product_catalog, create_order, check_invoices


class ToolExecutor:
    """Handles execution of MCP tool commands."""
    
    # Regex pattern for finding tool commands
    TOOL_PATTERN = r'\[(?:CHECK_CUSTOMER:[^\]]+|GET_CATALOG|CREATE_ORDER:[^\]]+|CHECK_INVOICES:[^\]]+)\]'
    
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
            
            # [CREATE_ORDER: customer_id, product_id1, product_id2, ...]
            elif command.upper().startswith("[CREATE_ORDER:"):
                # Parse: customer_id, component_id1, component_id2, ...
                params_str = command[14:-1].strip()
                params = [p.strip() for p in params_str.split(',')]
                
                if len(params) < 2:
                    return "❌ CREATE_ORDER wymaga co najmniej 2 parametrów: customer_id oraz przynajmniej jeden component_catalog_id"
                
                try:
                    customer_id = int(params[0])
                    component_ids = [int(p) for p in params[1:]]
                    return await create_order(customer_id, component_ids)
                except ValueError:
                    return f"❌ Nieprawidłowe parametry CREATE_ORDER. Wymagane: liczby całkowite. Otrzymano: {params}"
            
            # [CHECK_INVOICES: customer_id]
            elif command.upper().startswith("[CHECK_INVOICES:"):
                customer_id_str = command[16:-1].strip()
                try:
                    customer_id = int(customer_id_str)
                    return await check_invoices(customer_id)
                except ValueError:
                    return f"❌ Nieprawidłowy customer_id dla CHECK_INVOICES. Wymagane: liczba całkowita. Otrzymano: {customer_id_str}"
            
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
                await callback(f"\n🔧 Wykonuję narzędzie: {command}\n")
            
            result = await ToolExecutor.execute_command(command)
            results.append((command, result))
            
            if callback:
                await callback(f"✅ Otrzymano wynik ({len(result)} znaków)\n")
        
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