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
        if self._client is not None:
            try:
                self._client.connection.ping()
                return self._client
            except Exception:
                self._client = None

        # Resolve candidate hosts (prefer local, fallback to WSL bridge on Windows)
        candidate_hosts = [self.host]
        if self.host in ("127.0.0.1", "localhost"):
            try:
                import subprocess
                ps_cmd = '(Get-NetNeighbor -InterfaceAlias "*vEthernet*WSL*" | Where-Object { $_.IPAddress -match "^\\d+\\.\\d+\\.\\d+\\.\\d+$" -and $_.State -eq "Reachable" }).IPAddress'
                wsl_ip = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    timeout=1.5
                ).decode("utf-8").strip()
                if wsl_ip and wsl_ip not in candidate_hosts:
                    candidate_hosts.append(wsl_ip)
            except Exception:
                pass

        last_err = None
        for host in candidate_hosts:
            for attempt in range(2):
                try:
                    cl = FalkorDB(
                        host=host,
                        port=self.port,
                        password=self.password
                    )
                    cl.connection.ping()
                    self._client = cl
                    self.host = host
                    return self._client
                except Exception as e:
                    last_err = e
                    import time
                    time.sleep(0.05)

        if last_err:
            raise last_err
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
