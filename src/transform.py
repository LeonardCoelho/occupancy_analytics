import numpy as np
import pandas as pd

from config import PROCESSED_DIR


# LEITURA DOS DADOS

df_ocupacao = pd.read_parquet(
    PROCESSED_DIR / 'df_ocupacao.parquet'
)


# VALIDAÇÕES INICIAIS

registros_iniciais = len(df_ocupacao)

metro_padrao_nulo = (
    df_ocupacao['m³ padrão']
    .isna()
    .sum()
)

metro_padrao_zero = (
    df_ocupacao['m³ padrão']
    .eq(0)
    .sum()
)

metro_padrao_negativo = (
    df_ocupacao['m³ padrão']
    .lt(0)
    .sum()
)

print(f'Registros iniciais: {registros_iniciais:,}')

print('\nDistribuição de linhas por visão:')
print(df_ocupacao['Visão'].value_counts(dropna=False))

print(f'\nm³ padrão nulo: {metro_padrao_nulo:,}')
print(f'm³ padrão igual a zero: {metro_padrao_zero:,}')
print(f'm³ padrão negativo: {metro_padrao_negativo:,}')


# IDENTIFICAÇÃO DOS REGISTROS VÁLIDOS

condicao_valida = (
    df_ocupacao['m³ padrão'].notna()
    & df_ocupacao['m³ padrão'].gt(0)
)

linhas_validas = condicao_valida.sum()
linhas_invalidas = (~condicao_valida).sum()

print(f'\nLinhas válidas: {linhas_validas:,}')
print(f'Linhas inválidas: {linhas_invalidas:,}')


# CÁLCULO DA OCUPAÇÃO POR LINHA

df_ocupacao['ocupacao_linha'] = np.where(
    condicao_valida,
    df_ocupacao['m³ carregado'] / df_ocupacao['m³ padrão'],
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

print('\nAmostra do cálculo por linha:')

print(
    df_ocupacao[
        [
            'm³ carregado',
            'm³ padrão',
            'ocupacao_linha'
        ]
    ].head()
)


# AGREGAÇÃO POR CLIENTE E VISÃO

df_cliente_visao = (
    df_ocupacao
    .groupby(
        ['Cod cliente', 'Cliente', 'Visão'],
        dropna=False
    )
    .agg(
        metro_carregado=('m³ carregado', 'sum'),
        metro_padrao=(
            'm³ padrão',
            lambda coluna: coluna.sum(min_count=1)
        ),
        qtd_ocs=('OC', 'nunique'),
        frete_total=('R$ frete', 'sum'),
        qtd_metro_padrao_nulo=(
            'm³ padrão',
            lambda coluna: coluna.isna().sum()
        )
    )
    .reset_index()
)

print(
    f'\nRegistros agregados por cliente e visão: '
    f'{len(df_cliente_visao):,}'
)


# CÁLCULO DA OCUPAÇÃO AGREGADA

condicao_agregada_valida = (
    df_cliente_visao['metro_padrao'].notna()
    & df_cliente_visao['metro_padrao'].gt(0)
)

df_cliente_visao['ocupacao_cliente_visao'] = np.where(
    condicao_agregada_valida,
    df_cliente_visao['metro_carregado']
    / df_cliente_visao['metro_padrao'],
    np.nan
)

ocupacoes_agregadas_nao_calculadas = (
    df_cliente_visao['ocupacao_cliente_visao']
    .isna()
    .sum()
)

print(
    f'Ocupações agregadas não calculadas: '
    f'{ocupacoes_agregadas_nao_calculadas:,}'
)


# IDENTIFICAÇÃO DOS CLIENTES COM M³ PADRÃO NULO

codigos_com_metro_nulo = (
    df_ocupacao
    .loc[df_ocupacao['m³ padrão'].isna()]
    [['Cod cliente', 'Visão']]
    .drop_duplicates()
)

print(
    f'\nClientes e visões com m³ padrão nulo: '
    f'{len(codigos_com_metro_nulo):,}'
)

print(codigos_com_metro_nulo)


# DIAGNÓSTICO APÓS O AGRUPAMENTO

diagnostico_nulos = codigos_com_metro_nulo.merge(
    df_cliente_visao,
    on=['Cod cliente', 'Visão'],
    how='left',
    validate='one_to_one'
)

print('\nSituação desses clientes após o agrupamento:')

colunas_diagnostico = [
    'Cod cliente',
    'Cliente',
    'Visão',
    'metro_carregado',
    'metro_padrao',
    'qtd_ocs',
    'qtd_metro_padrao_nulo',
    'ocupacao_cliente_visao'
]

print(diagnostico_nulos[colunas_diagnostico])

colunas_resultado = [
    'Cod cliente',
    'Cliente',
    'Visão',
    'metro_carregado',
    'metro_padrao',
    'ocupacao_cliente_visao',
    'qtd_ocs',
    'frete_total'
]

print('\nAmostra da ocupação agregada:')
print(df_cliente_visao[colunas_resultado].head())

cliente_teste = df_ocupacao[
    df_ocupacao['Cod cliente'].eq(53053006)
]

validacao_manual = (
    cliente_teste
    .groupby('Visão')
    .agg(
        metro_carregado=('m³ carregado', 'sum'),
        metro_padrao=('m³ padrão', 'sum'),
        qtd_ocs=('OC', 'nunique')
    )
)

validacao_manual['ocupacao'] = (
    validacao_manual['metro_carregado']
    / validacao_manual['metro_padrao']
)

print('\nValidação manual do cliente 53053006:')
print(validacao_manual)

df_comparativo = df_cliente_visao.pivot_table(
    index=[
        'Cod cliente',
        'Cliente'
    ],
    columns='Visão',
    values=[
        'metro_carregado',
        'metro_padrao',
        'qtd_ocs',
        'frete_total',
        'ocupacao_cliente_visao'
    ],
    aggfunc='first'
).reset_index()

print('\nColunas após o pivot com todas as métricas:')
print(df_comparativo.columns.tolist())
# ACHATAMENTO DAS COLUNAS DO PIVOT

df_comparativo.columns = [
    coluna[0]
    if coluna[1] == ''
    else f'{coluna[0]}_{coluna[1]}'
    for coluna in df_comparativo.columns
]

df_comparativo = df_comparativo.rename(
    columns={
        'ocupacao_cliente_visao_AA': 'ocupacao_AA',
        'ocupacao_cliente_visao_Real': 'ocupacao_Real'
    }
)

df_comparativo['variacao_pp'] = (
    df_comparativo['ocupacao_Real']
    - df_comparativo['ocupacao_AA']
)

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

print('\nColunas após o achatamento:')
print(df_comparativo.columns.tolist())

print('\nDistribuição do status de comparação:')

print(
    df_comparativo['status_comparacao']
    .value_counts(dropna=False)
)

colunas_comparativo = [
    'Cod cliente',
    'Cliente',
    'ocupacao_AA',
    'ocupacao_Real',
    'variacao_pp',
    'metro_padrao_AA',
    'metro_padrao_Real',
    'qtd_ocs_AA',
    'qtd_ocs_Real',
    'frete_total_AA',
    'frete_total_Real',
    'status_comparacao'
]

print('\nAmostra do comparativo final:')
print(df_comparativo[colunas_comparativo].head(10))

# EXPORTAÇÃO DO RESULTADO TRANSFORMADO

print(
    f'\nClientes no comparativo final: '
    f'{len(df_comparativo):,}'
)

print(
    f'Códigos duplicados no comparativo: '
    f'{df_comparativo["Cod cliente"].duplicated().sum():,}'
)

arquivo_saida = (
    PROCESSED_DIR
    / 'ocupacao_por_cliente.parquet'
)

df_comparativo.to_parquet(
    arquivo_saida,
    index=False
)

print(
    f'\nComparativo por cliente exportado para: '
    f'{arquivo_saida}'
)