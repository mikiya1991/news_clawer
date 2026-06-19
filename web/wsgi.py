"""
WSGI entry point for deployment
"""
import sys
from pathlib import Path

# Add parent directory to path to import config and database
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
