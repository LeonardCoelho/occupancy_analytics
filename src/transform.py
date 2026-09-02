import numpy as np
import pandas as pd

from config import PROCESSED_DIR


# CAMINHOS

arquivo_entrada = (
    PROCESSED_DIR
    / 'df_ocupacao.parquet'
)

arquivo_saida_unidade = (
    PROCESSED_DIR
    / 'ocupacao_por_unidade.parquet'
)

arquivo_saida_analitico = (
    PROCESSED_DIR
    / 'ocupacao_analitica.parquet'
)


# LEITURA DOS DADOS

df_ocupacao = pd.read_parquet(
    arquivo_entrada
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

print(f'Registros recebidos: {registros_iniciais:,}')

print('\nDistribuição por visão:')

print(
    df_ocupacao['Visão']
    .value_counts(dropna=False)
)

print(f'\nm³ padrão nulo: {metro_padrao_nulo:,}')
print(f'm³ padrão igual a zero: {metro_padrao_zero:,}')
print(f'm³ padrão negativo: {metro_padrao_negativo:,}')


# IDENTIFICAÇÃO DAS LINHAS VÁLIDAS

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

print(
    f'Ocupações não calculadas: '
    f'{ocupacoes_nao_calculadas:,}'
)

print(
    f'Registros preservados: '
    f'{len(df_ocupacao):,}'
)


# CRIAÇÃO DAS COLUNAS DE PERÍODO

meses = {
    1: 'Janeiro',
    2: 'Fevereiro',
    3: 'Março',
    4: 'Abril',
    5: 'Maio',
    6: 'Junho',
    7: 'Julho',
    8: 'Agosto',
    9: 'Setembro',
    10: 'Outubro',
    11: 'Novembro',
    12: 'Dezembro'
}

df_ocupacao['mes_numero'] = (
    df_ocupacao['Data OC']
    .dt.month
)

df_ocupacao['mes_nome'] = (
    df_ocupacao['mes_numero']
    .map(meses)
)


# BASE ANALÍTICA PARA FILTROS

df_analitico = (
    df_ocupacao
    .groupby(
        [
        'Cliente curto',
        'Cod cliente',
        'Pai curto - cod',
        'Visão',
        'mes_numero',
        'mes_nome',
        'Filial/Fábrica',
        'Região',
        'Território',
        'Canal',
        'Cidade',
        'UF',
        'Perfil veículo',
        'Tipo carregto',
        'Tipo produto',
        'Tp. Or.',
        'Cod Transportadora'
        ],
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


# CÁLCULO DA OCUPAÇÃO NA BASE ANALÍTICA

condicao_analitica_valida = (
    df_analitico['metro_padrao'].notna()
    & df_analitico['metro_padrao'].gt(0)
)

df_analitico['ocupacao'] = np.where(
    condicao_analitica_valida,
    df_analitico['metro_carregado']
    / df_analitico['metro_padrao'],
    np.nan
)


# RENOMEAR COLUNAS DA BASE ANALÍTICA

df_analitico = df_analitico.rename(
    columns={
        'Cliente curto': 'cliente_unidade',
        'Cod cliente': 'cod_cliente',
        'Pai curto - cod': 'cliente_pai',
        'Visão': 'visao',
        'Filial/Fábrica': 'cd_origem',
        'Região': 'regiao',
        'Território': 'territorio',
        'Canal': 'canal',
        'Cidade': 'cidade',
        'UF': 'uf',
        'Perfil veículo': 'perfil_veiculo',
        'Tipo carregto': 'tipo_carregamento',
        'Tipo produto': 'tipo_produto',
        'Tp. Or.': 'tipo_ordem',
        'Cod Transportadora': 'cod_transportadora'
    }
)


# ORGANIZAÇÃO DA BASE ANALÍTICA

colunas_analiticas = [
    'cliente_unidade',
    'cod_cliente',
    'cliente_pai',
    'visao',
    'mes_numero',
    'mes_nome',
    'cd_origem',
    'regiao',
    'territorio',
    'canal',
    'cidade',
    'uf',
    'perfil_veiculo',
    'tipo_carregamento',
    'tipo_produto',
    'tipo_ordem',
    'cod_transportadora',
    'metro_carregado',
    'metro_padrao',
    'ocupacao',
    'qtd_ocs',
    'qtd_codigos_cliente',
    'frete_total',
    'qtd_metro_padrao_nulo'
]

df_analitico = (
    df_analitico[colunas_analiticas]
    .sort_values(
        by=[
            'mes_numero',
            'cliente_unidade',
            'visao'
        ]
    )
    .reset_index(drop=True)
)

print(
    f'\nRegistros na base analítica: '
    f'{len(df_analitico):,}'
)


# VALIDAÇÃO DOS TOTAIS DA BASE ANALÍTICA

metro_carregado_original = (
    df_ocupacao['m³ carregado']
    .sum()
)

metro_carregado_analitico = (
    df_analitico['metro_carregado']
    .sum()
)

metro_padrao_original = (
    df_ocupacao['m³ padrão']
    .sum()
)

metro_padrao_analitico = (
    df_analitico['metro_padrao']
    .sum()
)

frete_original = (
    df_ocupacao['R$ frete']
    .sum()
)

frete_analitico = (
    df_analitico['frete_total']
    .sum()
)

print('\nValidação dos totais:')

print(
    f'm³ carregado original: '
    f'{metro_carregado_original:,.4f}'
)

print(
    f'm³ carregado analítico: '
    f'{metro_carregado_analitico:,.4f}'
)

print(
    f'm³ padrão original: '
    f'{metro_padrao_original:,.4f}'
)

print(
    f'm³ padrão analítico: '
    f'{metro_padrao_analitico:,.4f}'
)

print(
    f'Frete original: '
    f'{frete_original:,.2f}'
)

print(
    f'Frete analítico: '
    f'{frete_analitico:,.2f}'
)


# VALIDAÇÃO DA QUANTIDADE DE OCS

qtd_ocs_original = (
    df_ocupacao['OC']
    .nunique()
)

qtd_ocs_somada_analitico = (
    df_analitico['qtd_ocs']
    .sum()
)

print('\nValidação da quantidade de OCs:')

print(
    f'OCs únicas na base detalhada: '
    f'{qtd_ocs_original:,}'
)

print(
    f'Soma de qtd_ocs na base analítica: '
    f'{qtd_ocs_somada_analitico:,.0f}'
)

if qtd_ocs_somada_analitico != qtd_ocs_original:
    print(
        'Aviso: qtd_ocs não é uma métrica aditiva. '
        'A mesma OC pode aparecer em mais de uma combinação '
        'de filtros.'
    )


# AGREGAÇÃO GERAL POR UNIDADE E VISÃO

df_unidade_visao = (
    df_ocupacao
    .groupby(
        [
            'Cliente curto',
            'Visão'
        ],
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


# CÁLCULO DA OCUPAÇÃO AGREGADA POR UNIDADE

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


# COMPARATIVO AA X REAL

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


# ACHATAMENTO DAS COLUNAS DO PIVOT

df_comparativo.columns = [
    coluna[0]
    if coluna[1] == ''
    else f'{coluna[0]}_{coluna[1]}'
    for coluna in df_comparativo.columns
]


# RENOMEAR COLUNAS DE OCUPAÇÃO

df_comparativo = df_comparativo.rename(
    columns={
        'Cliente curto': 'cliente_unidade',
        'ocupacao_unidade_visao_AA': 'ocupacao_AA',
        'ocupacao_unidade_visao_Real': 'ocupacao_Real'
    }
)


# VARIAÇÃO ENTRE REAL E AA

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


# ORDEM DAS COLUNAS DO COMPARATIVO

colunas_comparativo = [
    'cliente_unidade',
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

df_comparativo = (
    df_comparativo[colunas_comparativo]
    .sort_values(
        by='metro_padrao_Real',
        ascending=False,
        na_position='last'
    )
    .reset_index(drop=True)
)


# VALIDAÇÕES FINAIS

unidades_duplicadas = (
    df_comparativo['cliente_unidade']
    .duplicated()
    .sum()
)

print(
    f'\nUnidades no comparativo final: '
    f'{len(df_comparativo):,}'
)

print(
    f'Unidades duplicadas: '
    f'{unidades_duplicadas:,}'
)

print('\nDistribuição dos status:')

print(
    df_comparativo['status_comparacao']
    .value_counts(dropna=False)
)


# VALIDAÇÕES AUTOMÁTICAS

if len(df_ocupacao) != registros_iniciais:
    raise ValueError(
        'A quantidade de registros foi alterada '
        'durante a transformação.'
    )

if unidades_duplicadas > 0:
    raise ValueError(
        'Existem unidades duplicadas no comparativo final.'
    )

if (
    len(df_comparativo)
    != df_comparativo['cliente_unidade'].nunique()
):
    raise ValueError(
        'A base final não possui uma linha por unidade.'
    )

if not np.isclose(
    metro_carregado_original,
    metro_carregado_analitico
):
    raise ValueError(
        'O total de m³ carregado mudou '
        'na criação da base analítica.'
    )

if not np.isclose(
    metro_padrao_original,
    metro_padrao_analitico
):
    raise ValueError(
        'O total de m³ padrão mudou '
        'na criação da base analítica.'
    )

if not np.isclose(
    frete_original,
    frete_analitico
):
    raise ValueError(
        'O total de frete mudou '
        'na criação da base analítica.'
    )

print('\nValidações automáticas concluídas com sucesso.')


# EXPORTAÇÃO DAS DUAS BASES

df_comparativo.to_parquet(
    arquivo_saida_unidade,
    index=False
)

df_analitico.to_parquet(
    arquivo_saida_analitico,
    index=False
)

print(
    f'\nComparativo por unidade exportado para: '
    f'{arquivo_saida_unidade}'
)

print(
    f'Base analítica exportada para: '
    f'{arquivo_saida_analitico}'
)