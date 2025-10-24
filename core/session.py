"""
Session management for WebSocket connections.
"""

from typing import Dict
from external.model import ModelConnector


class SessionManager:
    """Manages user sessions for WebSocket connections."""
    
    def __init__(self):
        self.sessions: Dict[str, ModelConnector] = {}
    
    def create_session(self, session_id: str) -> ModelConnector:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ModelConnector instance for this session
        """
        mc = ModelConnector()
        self.sessions[session_id] = mc
        return mc
    
    def get_session(self, session_id: str) -> ModelConnector:
        """
        Get existing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ModelConnector instance or None if not found
        """
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> tuple:
        """
        Delete a session and return its final state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Tuple of (history, stats) if session existed, (None, None) otherwise
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            history = session.get_history()
            stats = session.get_stats()
            del self.sessions[session_id]
            return history, stats
        return None, None
    
    def get_active_count(self) -> int:
        """Get number of active sessions."""
        return len(self.sessions)
    
    def get_all_stats(self) -> dict:
        """Get statistics for all active sessions."""
        return {
            sid: session.get_stats() 
            for sid, session in self.sessions.items()
        }