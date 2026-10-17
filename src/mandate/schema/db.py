import os
from typing import Optional
from falkordb import FalkorDB, Graph

class FalkorClientManager:
    """
    Manages connections to FalkorDB.
    Supports local Docker instance and FalkorDB Cloud via environment variables.
    Enforces strict tenant isolation via select_graph(tenant_id).
    """
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None
    ):
        self.host = host or os.getenv("FALKORDB_HOST", "127.0.0.1")
        self.port = int(port or os.getenv("FALKORDB_PORT", 6379))
        self.password = password or os.getenv("FALKORDB_PASSWORD", None)
        
        self._client = None

    @property
    def client(self) -> FalkorDB:
        if self._client is None:
            self._client = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password
            )
        return self._client

    def get_tenant_graph(self, tenant_id: str) -> Graph:
        """
        Retrieves or initializes a graph namespace strictly isolated for a given tenant.
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a valid non-empty string.")
        clean_name = f"mandate_{tenant_id.lower().replace('-', '_')}"
        return self.client.select_graph(clean_name)

    def get_public_graph(self) -> Graph:
        """
        Retrieves the public legal regulatory graph.
        """
        return self.client.select_graph("mandate_dpdp_public")
