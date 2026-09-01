import numpy as np
import pandas as pd

from config import PROCESSED_DIR


# CAMINHOS

arquivo_entrada = PROCESSED_DIR / 'df_ocupacao.parquet'
arquivo_saida = PROCESSED_DIR / 'ocupacao_por_unidade.parquet'


# LEITURA DOS DADOS

df_ocupacao = pd.read_parquet(arquivo_entrada)


# VALIDAÇÕES INICIAIS

registros_iniciais = len(df_ocupacao)

metro_padrao_nulo = df_ocupacao['m³ padrão'].isna().sum()
metro_padrao_zero = df_ocupacao['m³ padrão'].eq(0).sum()
metro_padrao_negativo = df_ocupacao['m³ padrão'].lt(0).sum()

print(f'Registros recebidos: {registros_iniciais:,}')

print('\nDistribuição por visão:')
print(df_ocupacao['Visão'].value_counts(dropna=False))

print(f'\nm³ padrão nulo: {metro_padrao_nulo:,}')
print(f'm³ padrão igual a zero: {metro_padrao_zero:,}')
print(f'm³ padrão negativo: {metro_padrao_negativo:,}')


# OCUPAÇÃO POR LINHA

condicao_valida = (
    df_ocupacao['m³ padrão'].notna()
    & df_ocupacao['m³ padrão'].gt(0)
)

df_ocupacao['ocupacao_linha'] = np.where(
    condicao_valida,
    df_ocupacao['m³ carregado']
    / df_ocupacao['m³ padrão'],
    np.nan
)

ocupacoes_calculadas = (
    df_ocupacao['ocupacao_linha']
    .notna()
    .sum()
)

ocupacoes_nao_calculadas = (
    df_ocupacao['ocupacao_linha']
    .isna()
    .sum()
)

print(f'\nOcupações calculadas: {ocupacoes_calculadas:,}')
print(f'Ocupações não calculadas: {ocupacoes_nao_calculadas:,}')
print(f'Registros preservados: {len(df_ocupacao):,}')


# AGREGAÇÃO POR UNIDADE E VISÃO

df_unidade_visao = (
    df_ocupacao
    .groupby(
        ['Cliente curto', 'Visão'],
        dropna=False
    )
    .agg(
        metro_carregado=(
            'm³ carregado',
            'sum'
        ),
        metro_padrao=(
            'm³ padrão',
            lambda coluna: coluna.sum(min_count=1)
        ),
        qtd_ocs=(
            'OC',
            'nunique'
        ),
        qtd_codigos_cliente=(
            'Cod cliente',
            'nunique'
        ),
        frete_total=(
            'R$ frete',
            'sum'
        ),
        qtd_metro_padrao_nulo=(
            'm³ padrão',
            lambda coluna: coluna.isna().sum()
        )
    )
    .reset_index()
)

print(
    f'\nRegistros agregados por unidade e visão: '
    f'{len(df_unidade_visao):,}'
)


# OCUPAÇÃO AGREGADA POR UNIDADE E VISÃO

condicao_unidade_valida = (
    df_unidade_visao['metro_padrao'].notna()
    & df_unidade_visao['metro_padrao'].gt(0)
)

df_unidade_visao['ocupacao_unidade_visao'] = np.where(
    condicao_unidade_valida,
    df_unidade_visao['metro_carregado']
    / df_unidade_visao['metro_padrao'],
    np.nan
)


# PIVOT AA X REAL

df_comparativo = (
    df_unidade_visao
    .pivot_table(
        index='Cliente curto',
        columns='Visão',
        values=[
            'frete_total',
            'metro_carregado',
            'metro_padrao',
            'ocupacao_unidade_visao',
            'qtd_codigos_cliente',
            'qtd_metro_padrao_nulo',
            'qtd_ocs'
        ],
        aggfunc='first'
    )
    .reset_index()
)


# ACHATAMENTO DAS COLUNAS

df_comparativo.columns = [
    coluna[0]
    if coluna[1] == ''
    else f'{coluna[0]}_{coluna[1]}'
    for coluna in df_comparativo.columns
]


# RENOMEAR OCUPAÇÕES

df_comparativo = df_comparativo.rename(
    columns={
        'ocupacao_unidade_visao_AA': 'ocupacao_AA',
        'ocupacao_unidade_visao_Real': 'ocupacao_Real'
    }
)


# VARIAÇÃO EM PONTOS PERCENTUAIS

df_comparativo['variacao_pp'] = (
    df_comparativo['ocupacao_Real']
    - df_comparativo['ocupacao_AA']
)


# STATUS DA COMPARAÇÃO

tem_aa_e_real = (
    df_comparativo['ocupacao_AA'].notna()
    & df_comparativo['ocupacao_Real'].notna()
)

tem_somente_real = (
    df_comparativo['ocupacao_AA'].isna()
    & df_comparativo['ocupacao_Real'].notna()
)

tem_somente_aa = (
    df_comparativo['ocupacao_AA'].notna()
    & df_comparativo['ocupacao_Real'].isna()
)

df_comparativo['status_comparacao'] = np.select(
    [
        tem_aa_e_real,
        tem_somente_real,
        tem_somente_aa
    ],
    [
        'Comparável',
        'Novo no Real',
        'Sem movimento no Real'
    ],
    default='Sem dados'
)


# ORDEM DAS COLUNAS

colunas_finais = [
    'Cliente curto',
    'ocupacao_AA',
    'ocupacao_Real',
    'variacao_pp',
    'metro_carregado_AA',
    'metro_carregado_Real',
    'metro_padrao_AA',
    'metro_padrao_Real',
    'qtd_ocs_AA',
    'qtd_ocs_Real',
    'qtd_codigos_cliente_AA',
    'qtd_codigos_cliente_Real',
    'frete_total_AA',
    'frete_total_Real',
    'qtd_metro_padrao_nulo_AA',
    'qtd_metro_padrao_nulo_Real',
    'status_comparacao'
]

df_comparativo = df_comparativo[colunas_finais]


# ORDENAÇÃO PELO VOLUME REAL

df_comparativo = (
    df_comparativo
    .sort_values(
        by='metro_padrao_Real',
        ascending=False,
        na_position='last'
    )
    .reset_index(drop=True)
)


# VALIDAÇÕES FINAIS

unidades_duplicadas = (
    df_comparativo['Cliente curto']
    .duplicated()
    .sum()
)

print(
    f'\nUnidades no comparativo final: '
    f'{len(df_comparativo):,}'
)

print(
    f'Clientes curtos duplicados: '
    f'{unidades_duplicadas:,}'
)

print('\nDistribuição dos status:')

print(
    df_comparativo['status_comparacao']
    .value_counts(dropna=False)
)


# VALIDAÇÃO DO ARROJITO

teste_arrojito = df_comparativo.loc[
    df_comparativo['Cliente curto']
    .eq('ARROJITO - PINHAIS')
]

print('\nValidação ARROJITO - PINHAIS:')
print(teste_arrojito.to_string(index=False))


# EXPORTAÇÃO

df_comparativo.to_parquet(
    arquivo_saida,
    index=False
)

print(
    f'\nComparativo por unidade exportado para: '
    f'{arquivo_saida}'
)