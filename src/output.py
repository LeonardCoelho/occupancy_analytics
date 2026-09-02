import pandas as pd

from config import PROCESSED_DIR, OUTPUT_DIR


# CAMINHOS

arquivo_comparativo = (
    PROCESSED_DIR
    / 'ocupacao_por_unidade.parquet'
)

arquivo_analitico = (
    PROCESSED_DIR
    / 'ocupacao_analitica.parquet'
)

arquivo_saida = (
    OUTPUT_DIR
    / 'relatorio_ocupacao.xlsx'
)


# LEITURA

df_comparativo = pd.read_parquet(
    arquivo_comparativo
)

df_analitico = pd.read_parquet(
    arquivo_analitico
)


# VALIDAÇÕES

print(
    f'Unidades recebidas no comparativo: '
    f'{len(df_comparativo):,}'
)

print(
    f'Registros recebidos na base analítica: '
    f'{len(df_analitico):,}'
)

if 'cliente_unidade' not in df_comparativo.columns:
    raise ValueError(
        'A coluna "cliente_unidade" não existe no comparativo. '
        'Execute primeiro o transform.py atualizado.'
    )

unidades_duplicadas = (
    df_comparativo['cliente_unidade']
    .duplicated()
    .sum()
)

print(
    f'Unidades duplicadas no comparativo: '
    f'{unidades_duplicadas:,}'
)

if unidades_duplicadas > 0:
    raise ValueError(
        'O comparativo possui unidades duplicadas.'
    )


# EXPORTAÇÃO PARA EXCEL

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with pd.ExcelWriter(
    arquivo_saida,
    engine='openpyxl'
) as writer:

    df_comparativo.to_excel(
        writer,
        sheet_name='Comparativo',
        index=False
    )

    df_analitico.to_excel(
        writer,
        sheet_name='Base Analítica',
        index=False
    )

print(
    f'\nRelatório Excel exportado para: '
    f'{arquivo_saida}'
)