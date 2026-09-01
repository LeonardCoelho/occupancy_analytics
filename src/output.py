import pandas as pd

from config import PROCESSED_DIR, OUTPUT_DIR


# CAMINHOS

arquivo_entrada = (
    PROCESSED_DIR
    / 'ocupacao_por_unidade.parquet'
)

arquivo_saida = (
    OUTPUT_DIR
    / 'ocupacao_por_unidade.xlsx'
)


# LEITURA

df_comparativo = pd.read_parquet(
    arquivo_entrada
)


# VALIDAÇÕES

print(f'Unidades recebidas: {len(df_comparativo):,}')

print('\nColunas recebidas:')
print(df_comparativo.columns.to_list())

if 'Cliente curto' not in df_comparativo.columns:
    raise ValueError(
        'A coluna "Cliente curto" não existe. '
        'Execute primeiro o transform.py atualizado.'
    )

unidades_duplicadas = (
    df_comparativo['Cliente curto']
    .duplicated()
    .sum()
)

print(
    f'\nClientes curtos duplicados: '
    f'{unidades_duplicadas:,}'
)


# EXPORTAÇÃO PARA EXCEL

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

df_comparativo.to_excel(
    arquivo_saida,
    index=False
)

print(
    f'\nArquivo Excel exportado para: '
    f'{arquivo_saida}'
)