from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

RAW_DIR = BASE_DIR / 'data' / 'raw'
PROCESSED_DIR = BASE_DIR / 'data' / 'processed'
OUTPUT_DIR = BASE_DIR / 'data' / 'output'