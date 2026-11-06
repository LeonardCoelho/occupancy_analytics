"""Atualiza todas as bases do painel em um unico comando.

    python src/atualizar_bases.py

Executa extract.py e transform.py em sequencia. O painel detecta os Parquets
novos sozinho (o cache usa a data do arquivo), sem precisar limpar cache.
"""

import runpy
import sys
import time
from pathlib import Path

PASTA_SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_SRC))

for etapa in ('extract.py', 'transform.py'):
    inicio = time.perf_counter()
    print(f'\n=== {etapa} ===')
    runpy.run_path(str(PASTA_SRC / etapa), run_name='__main__')
    print(f'=== {etapa} concluido em {time.perf_counter() - inicio:.1f}s ===')

print('\nBases atualizadas. Recarregue o painel no navegador.')
