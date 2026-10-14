from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

RAW_DIR = BASE_DIR / 'data' / 'raw'
PROCESSED_DIR = BASE_DIR / 'data' / 'processed'
OUTPUT_DIR = BASE_DIR / 'data' / 'output'
ARQUIVO_PARTICULARIDADES = RAW_DIR / 'particularidade_clientes.xlsx'
ARQUIVO_OCUPACAO_DETALHADA = PROCESSED_DIR / 'ocupacao_cargas.parquet'
ARQUIVO_PARTICULARIDADES_PROCESSADAS = (
    PROCESSED_DIR / 'particularidades_clientes.parquet'
)
