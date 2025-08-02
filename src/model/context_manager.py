from abc import ABC, abstractmethod

class BaseContextManager(ABC):
    @abstractmethod
    def save_context(self, session_id: str, message: str, metadata: dict = None):
        """Save a single message with optional metadata."""
        pass

    @abstractmethod
    def load_context(self, session_id: str, limit: int = None) -> list[dict]:
        """Retrieve context for a session."""
        pass

    @abstractmethod
    def prune_context(self, session_id: str, strategy: str = "default"):
        """Prune the session context according to a strategy."""
        pass

    @abstractmethod
    def delete_context(self, session_id: str):
        """Delete all context for a session."""
        pass


class OracleContextManager(BaseContextManager):
    def __init__(self, db_connection):
        self.conn = db_connection

    def save_context(self, session_id, message, metadata=None):
        # Oracle insert logic
        pass

    def load_context(self, session_id, limit=None):
        # Oracle select logic
        pass

    def prune_context(self, session_id, strategy="default"):
        # Oracle pruning logic
        pass

    def delete_context(self, session_id):
        # Oracle delete logic
        pass

