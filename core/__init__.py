"""
Core functionality for the Play virtual consultant API.
"""

from .logging import log_colored, log_history, log_streaming_progress
from .session import SessionManager
from .websocket import WebSocketHandler

__all__ = [
    'log_colored',
    'log_history',
    'log_streaming_progress',
    'SessionManager',
    'WebSocketHandler',
]