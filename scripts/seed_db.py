"""
Database seeding script.

Usage:
    python scripts/seed_db.py
"""

import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.seed_data import seed_all

if __name__ == "__main__":
    seed_all()
