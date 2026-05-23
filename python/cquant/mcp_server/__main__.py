"""Entry point: python -m cquant.mcp_server"""
from cquant.mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run()
