import socket

def check_mcp_port():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('', 0))  # Bind to any available port
        port = sock.getsockname()[1]
        sock.close()
        print(f"MCP Server would use port: {port}")
        return port
    except Exception as e:
        print(f"Error checking port: {e}")
        return None

if __name__ == "__main__":
    check_mcp_port() 