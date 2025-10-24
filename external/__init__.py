"""
External integrations package for Play virtual consultant.
"""

from .model import ModelConnector
from .prompts import SYSTEM_PROMPT, TOOL_PROCESSING_PROMPT
from .tool_executor import ToolExecutor
from .mcp_server import check_customer, get_product_catalog, create_order

__all__ = [
    'ModelConnector',
    'SYSTEM_PROMPT',
    'TOOL_PROCESSING_PROMPT',
    'ToolExecutor',
    'check_customer',
    'get_product_catalog',
    'create_order',
]