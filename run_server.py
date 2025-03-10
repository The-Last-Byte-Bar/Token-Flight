#!/usr/bin/env python3
"""
Wrapper script to run the MCP server in the correct conda environment.
"""

import os
import sys
import subprocess
from pathlib import Path

def find_conda_python():
    """Find the Python executable in the pool conda environment"""
    conda_prefix = os.path.expanduser("~/miniconda3")
    env_python = os.path.join(conda_prefix, "envs", "pool", "bin", "python")
    if os.path.exists(env_python):
        return env_python
    return None

def main():
    """Run the MCP server in the pool conda environment"""
    # Find the conda Python executable
    python_path = find_conda_python()
    if not python_path:
        print("Error: Could not find Python in the pool conda environment")
        return 1
    
    # Set up environment
    env = os.environ.copy()
    current_dir = Path(__file__).parent
    env["PYTHONPATH"] = f"{current_dir}:{current_dir}/src"
    
    # Run the server
    try:
        subprocess.run([python_path, "mcp/run.py"], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running server: {e}")
        return e.returncode
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        return 0
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 