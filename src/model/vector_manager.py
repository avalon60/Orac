from abc import ABC, abstractmethod

class BaseVectorManager(ABC):
    @abstractmethod
    def store_vector(self, key: str, vector: list[float], metadata: dict = None):
        pass

    @abstractmethod
    def search_vectors(self, query_vector: list[float], top_k: int, filters: dict = None) -> list:
        pass

    @abstractmethod
    def delete_vector(self, key: str):
        pass

# 🟢 Oracle implementation
class OracleVectorManager(BaseVectorManager):
    def __init__(self, db_connection):
        self.conn = db_connection

    def store_vector(self, key, vector, metadata):
        # Insert into Oracle with VECTOR(n) datatype
        pass

    def search_vectors(self, query_vector, top_k, filters=None):
        # Use SQL with VECTOR_DISTANCE
        pass

# 🟡 Qdrant implementation
class QdrantVectorManager(BaseVectorManager):
    def __init__(self, qdrant_client):
        self.client = qdrant_client

    def store_vector(self, key, vector, metadata):
        # Call Qdrant REST API / Python SDK
        pass

    def search_vectors(self, query_vector, top_k, filters=None):
        # Qdrant similarity search
        pass
