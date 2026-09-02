from pathlib import Path

import plotly.graph_objects as go
import pandas as pd
import streamlit as st


# CONFIGURAÇÃO DA PÁGINA

st.set_page_config(
    page_title='Análise de Ocupação Logística',
    page_icon='🚛',
    layout='wide'
)


# LOCALIZAÇÃO DA RAIZ DO PROJETO

PASTA_APP = Path(__file__).resolve().parent

if (PASTA_APP / 'data').exists():
    BASE_DIR = PASTA_APP

elif (PASTA_APP.parent / 'data').exists():
    BASE_DIR = PASTA_APP.parent

else:
    st.error(
        'Não foi possível localizar a pasta data do projeto.'
    )

    st.write(
        f'Local do app.py: {PASTA_APP}'
    )

    st.stop()


# CAMINHO DA BASE ANALÍTICA

ARQUIVO_ANALITICO = (
    BASE_DIR
    / 'data'
    / 'processed'
    / 'ocupacao_analitica.parquet'
)


# LEITURA DOS DADOS

@st.cache_data
def carregar_dados(caminho_arquivo):
    return pd.read_parquet(
        caminho_arquivo
    )


if not ARQUIVO_ANALITICO.exists():
    st.error(
        'O arquivo ocupacao_analitica.parquet não foi encontrado.'
    )

    st.write(
        f'Caminho procurado: {ARQUIVO_ANALITICO}'
    )

    st.info(
        'Execute primeiro: python src/extract.py '
        'e depois: python src/transform.py'
    )

    st.stop()


df = carregar_dados(
    ARQUIVO_ANALITICO
)


# TÍTULO

st.title('Análise de Ocupação Logística')

st.caption(
    'Este dashboard apresenta uma análise detalhada da '
    'ocupação logística. Utilize os filtros disponíveis '
    'para explorar os resultados por período, CD e operação.'
)


# FUNÇÕES AUXILIARES

def valores_disponiveis(dataframe, coluna):
    return sorted(
        dataframe[coluna]
        .dropna()
        .unique()
        .tolist()
    )


def formatar_numero(valor, casas=2):
    texto = f'{valor:,.{casas}f}'

    return (
        texto
        .replace(',', 'X')
        .replace('.', ',')
        .replace('X', '.')
    )


def formatar_inteiro(valor):
    return (
        f'{valor:,}'
        .replace(',', '.')
    )


# FILTROS PRINCIPAIS

st.sidebar.header('Filtros principais')


# FILTRO DE VISÃO

visoes_disponiveis = valores_disponiveis(
    df,
    'visao'
)

visoes_selecionadas = st.sidebar.multiselect(
    'Selecione a(s) visão(ões):',
    options=visoes_disponiveis,
    default=visoes_disponiveis
)


# FILTRO DE MÊS

meses_disponiveis = (
    df[
        [
            'mes_numero',
            'mes_nome'
        ]
    ]
    .drop_duplicates()
    .dropna()
    .sort_values('mes_numero')
    .reset_index(drop=True)
)

mapa_meses = {
    linha['mes_nome']: int(linha['mes_numero'])
    for _, linha in meses_disponiveis.iterrows()
}

nomes_meses_disponiveis = (
    meses_disponiveis['mes_nome']
    .tolist()
)

meses_selecionados = st.sidebar.multiselect(
    'Selecione o(s) mês(es):',
    options=nomes_meses_disponiveis,
    default=nomes_meses_disponiveis
)

numeros_meses_selecionados = [
    mapa_meses[mes]
    for mes in meses_selecionados
]


# FILTRO DE CD

cds_disponiveis = valores_disponiveis(
    df,
    'cd_origem'
)

cds_selecionados = st.sidebar.multiselect(
    'Selecione o(s) CD(s):',
    options=cds_disponiveis,
    default=cds_disponiveis
)


# TRATAMENTO DE FILTROS VAZIOS

if not visoes_selecionadas:
    st.warning(
        'Selecione pelo menos uma visão.'
    )

    st.stop()

if not meses_selecionados:
    st.warning(
        'Selecione pelo menos um mês.'
    )

    st.stop()

if not cds_selecionados:
    st.warning(
        'Selecione pelo menos um CD.'
    )

    st.stop()


# APLICAÇÃO DOS FILTROS PRINCIPAIS

df_filtrado = df.loc[
    df['visao'].isin(visoes_selecionadas)
    & df['mes_numero'].isin(
        numeros_meses_selecionados
    )
    & df['cd_origem'].isin(
        cds_selecionados
    )
].copy()


# FILTROS ADICIONAIS

# FUNÇÃO PARA APLICAR FILTRO OPCIONAL

def aplicar_filtro(dataframe, coluna, valores):
    if valores:
        return dataframe.loc[
            dataframe[coluna].isin(valores)
        ].copy()

    return dataframe


# FILTROS ADICIONAIS

st.sidebar.divider()

with st.sidebar.expander(
    'Filtros adicionais',
    expanded=False
):

    clientes_disponiveis = valores_disponiveis(
        df_filtrado,
        'cliente_unidade'
    )

    clientes_selecionados = st.multiselect(
        'Cliente / unidade:',
        options=clientes_disponiveis,
        placeholder='Todos os clientes'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'cliente_unidade',
        clientes_selecionados
    )

    codigos_clientes_disponiveis = valores_disponiveis(
        df_filtrado,
        'cod_cliente'
    )

    codigos_clientes_selecionados = st.multiselect(
        'Código do cliente:',
        options=codigos_clientes_disponiveis,
        placeholder='Todos os códigos'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'cod_cliente',
        codigos_clientes_selecionados
    )

    clientes_pai_disponiveis = valores_disponiveis(
        df_filtrado,
        'cliente_pai'
    )

    clientes_pai_selecionados = st.multiselect(
        'Cliente-pai:',
        options=clientes_pai_disponiveis,
        placeholder='Todos os clientes-pai'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'cliente_pai',
        clientes_pai_selecionados
    )

    territorios_disponiveis = valores_disponiveis(
        df_filtrado,
        'territorio'
    )

    territorios_selecionados = st.multiselect(
        'Território:',
        options=territorios_disponiveis,
        placeholder='Todos os territórios'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'territorio',
        territorios_selecionados
    )

    canais_disponiveis = valores_disponiveis(
        df_filtrado,
        'canal'
    )

    canais_selecionados = st.multiselect(
        'Canal:',
        options=canais_disponiveis,
        placeholder='Todos os canais'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'canal',
        canais_selecionados
    )

    carregamentos_disponiveis = valores_disponiveis(
        df_filtrado,
        'tipo_carregamento'
    )

    carregamentos_selecionados = st.multiselect(
        'Tipo de carregamento:',
        options=carregamentos_disponiveis,
        placeholder='Todos os carregamentos'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'tipo_carregamento',
        carregamentos_selecionados
    )

    produtos_disponiveis = valores_disponiveis(
        df_filtrado,
        'tipo_produto'
    )

    produtos_selecionados = st.multiselect(
        'Tipo de produto:',
        options=produtos_disponiveis,
        placeholder='Todos os produtos'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'tipo_produto',
        produtos_selecionados
    )

    perfis_disponiveis = valores_disponiveis(
        df_filtrado,
        'perfil_veiculo'
    )

    perfis_selecionados = st.multiselect(
        'Perfil do veículo:',
        options=perfis_disponiveis,
        placeholder='Todos os veículos'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'perfil_veiculo',
        perfis_selecionados
    )

    tipos_ordem_disponiveis = valores_disponiveis(
        df_filtrado,
        'tipo_ordem'
    )

    tipos_ordem_selecionados = st.multiselect(
        'Tipo de ordem:',
        options=tipos_ordem_disponiveis,
        placeholder='Todos os tipos de ordem'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'tipo_ordem',
        tipos_ordem_selecionados
    )

    ufs_disponiveis = valores_disponiveis(
        df_filtrado,
        'uf'
    )

    ufs_selecionadas = st.multiselect(
        'UF:',
        options=ufs_disponiveis,
        placeholder='Todos os estados'
    )

    df_filtrado = aplicar_filtro(
        df_filtrado,
        'uf',
        ufs_selecionadas
    )


# TRATAMENTO DE FILTROS SEM RESULTADOS

if df_filtrado.empty:
    st.warning(
        'Nenhum registro foi encontrado com os filtros aplicados. '
        'Ajuste os filtros para visualizar os dados.'
    )

    st.stop()


# CÁLCULO DOS INDICADORES

metro_carregado_total = (
    df_filtrado['metro_carregado']
    .sum()
)

metro_padrao_total = (
    df_filtrado['metro_padrao']
    .sum()
)

frete_total = (
    df_filtrado['frete_total']
    .sum()
)

if (
    pd.notna(metro_padrao_total)
    and metro_padrao_total > 0
):
    ocupacao_filtrada = (
        metro_carregado_total
        / metro_padrao_total
    )

else:
    ocupacao_filtrada = None


quantidade_unidades = (
    df_filtrado['cliente_unidade']
    .nunique()
)

quantidade_codigos = (
    df_filtrado['cod_cliente']
    .nunique()
)

quantidade_cds = (
    df_filtrado['cd_origem']
    .nunique()
)


# CARDS

st.subheader('Indicadores do período filtrado')

coluna_1, coluna_2, coluna_3 = st.columns(3)

coluna_4, coluna_5, coluna_6 = st.columns(3)


coluna_1.metric(
    label='Ocupação',
    value=(
        f'{ocupacao_filtrada:.2%}'
        if ocupacao_filtrada is not None
        else 'Não calculada'
    )
)

coluna_2.metric(
    label='m³ carregados',
    value=formatar_numero(
        metro_carregado_total
    )
)

coluna_3.metric(
    label='m³ padrão',
    value=formatar_numero(
        metro_padrao_total
    )
)

coluna_4.metric(
    label='Frete total',
    value=(
        f'R$ {formatar_numero(frete_total)}'
    )
)

coluna_5.metric(
    label='Unidades distintas',
    value=formatar_inteiro(
        quantidade_unidades
    )
)

coluna_6.metric(
    label='Códigos de cliente',
    value=formatar_inteiro(
        quantidade_codigos
    )
)


# INFORMAÇÕES SOBRE OS FILTROS

st.caption(
    f'{formatar_inteiro(len(df_filtrado))} registros analíticos '
    f'e {formatar_inteiro(quantidade_cds)} CD(s) no filtro atual.'
)


# INFORMAÇÃO SOBRE O CÁLCULO

with st.expander(
    'Como é calculada a ocupação?',
    expanded=False
):

    st.write(
        'A ocupação não utiliza a média simples das porcentagens '
        'das linhas. O indicador considera os volumes totais '
        'do conjunto filtrado.'
    )

    st.code(
        'Ocupação = soma do m³ carregado / soma do m³ padrão'
    )

    st.write(
        f'm³ carregados: '
        f'{formatar_numero(metro_carregado_total, 4)}'
    )

    st.write(
        f'm³ padrão: '
        f'{formatar_numero(metro_padrao_total, 4)}'
    )

    if ocupacao_filtrada is not None:
        st.write(
            f'Ocupação calculada: '
            f'{ocupacao_filtrada:.4%}'
        )

# FUNÇÃO PARA PREPARAR UMA VISÃO DE OCUPAÇÃO

def preparar_visao_ocupacao(
    dataframe,
    coluna_agrupamento,
    volume_minimo=0.0
):
    resultado = (
        dataframe
        .groupby(
            coluna_agrupamento,
            dropna=False
        )
        .agg(
            metro_carregado=(
                'metro_carregado',
                'sum'
            ),
            metro_padrao=(
                'metro_padrao',
                'sum'
            ),
            frete_total=(
                'frete_total',
                'sum'
            ),
            qtd_unidades=(
                'cliente_unidade',
                'nunique'
            ),
            qtd_codigos=(
                'cod_cliente',
                'nunique'
            )
        )
        .reset_index()
    )

    resultado = resultado.loc[
        resultado['metro_padrao'].notna()
        & resultado['metro_padrao'].gt(0)
        & resultado['metro_carregado'].ge(
            volume_minimo
        )
    ].copy()

    resultado['ocupacao'] = (
        resultado['metro_carregado']
        / resultado['metro_padrao']
    )

    return resultado


# FUNÇÃO PARA CRIAR O GRÁFICO COMBINADO

def criar_grafico_ocupacao(
    dataframe,
    coluna_categoria,
    titulo_categoria,
    meta_ocupacao,
    quantidade_itens
):
    dados_grafico = (
        dataframe
        .nlargest(
            quantidade_itens,
            'metro_carregado'
        )
        .sort_values(
            'metro_carregado',
            ascending=True
        )
        .reset_index(drop=True)
    )

    if dados_grafico.empty:
        return None

    dados_grafico['situacao_meta'] = (
        dados_grafico['ocupacao']
        .ge(meta_ocupacao)
        .map({
            True: 'Na meta',
            False: 'Abaixo da meta'
        })
    )

    cores_barras = [
        '#D9534F'
        if ocupacao < meta_ocupacao
        else '#2E86DE'
        for ocupacao in dados_grafico['ocupacao']
    ]

    figura = go.Figure()

    figura.add_trace(
        go.Bar(
            x=dados_grafico['metro_carregado'],
            y=dados_grafico[coluna_categoria],
            orientation='h',
            name='m³ carregado',
            marker_color=cores_barras,
            customdata=dados_grafico[
                [
                    'metro_padrao',
                    'ocupacao',
                    'frete_total',
                    'qtd_unidades',
                    'qtd_codigos',
                    'situacao_meta'
                ]
            ].to_numpy(),
            hovertemplate=(
                '<b>%{y}</b><br>'
                'm³ carregado: %{x:,.2f}<br>'
                'm³ padrão: %{customdata,.2f}<br>'
                'Ocupação: %{customdata.2%}<br>'
                'Frete: R$ %{customdata,.2f}<br>'
                'Unidades: %{customdata[3]}<br>'
                'Códigos: %{customdata[4]}<br>'
                'Situação: %{customdata[5]}'
                '<extra></extra>'
            )
        )
    )

    figura.add_trace(
        go.Scatter(
            x=dados_grafico['ocupacao'],
            y=dados_grafico[coluna_categoria],
            mode='markers',
            name='Ocupação',
            xaxis='x2',
            marker={
                'size': 10,
                'color': '#F39C12',
                'line': {
                    'color': '#FFFFFF',
                    'width': 1
                }
            },
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Ocupação: %{x:.2%}'
                '<extra></extra>'
            )
        )
    )

    # Linha da meta usando o eixo percentual x2

    figura.add_shape(
        type='line',
        xref='x2',
        yref='paper',
        x0=meta_ocupacao,
        x1=meta_ocupacao,
        y0=0,
        y1=1,
        line={
            'color': '#C0392B',
            'width': 2,
            'dash': 'dash'
        }
    )

    figura.add_annotation(
        xref='x2',
        yref='paper',
        x=meta_ocupacao,
        y=1.05,
        text=f'Meta: {meta_ocupacao:.2%}',
        showarrow=False,
        font={
            'color': '#C0392B'
        }
    )

    maior_ocupacao = dados_grafico['ocupacao'].max()

    limite_percentual = max(
        1.0,
        maior_ocupacao * 1.10,
        meta_ocupacao * 1.10
    )

    altura_grafico = max(
        500,
        len(dados_grafico) * 34
    )

    figura.update_layout(
        height=altura_grafico,
        margin={
            'l': 20,
            'r': 20,
            't': 80,
            'b': 20
        },
        hovermode='closest',
        legend={
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': 1.10,
            'xanchor': 'left',
            'x': 0
        },
        xaxis={
            'title': 'm³ carregado',
            'side': 'bottom',
            'showgrid': True,
            'rangemode': 'tozero'
        },
        xaxis2={
            'title': 'Ocupação',
            'overlaying': 'x',
            'side': 'top',
            'tickformat': '.0%',
            'range': [
                0,
                limite_percentual
            ]
        },
        yaxis={
            'title': titulo_categoria,
            'automargin': True
        }
    )

    return figura


# CONTROLES DA ANÁLISE

st.divider()

st.subheader(
    'Volume carregado e ocupação por cliente-pai'
)

st.caption(
    'A análise começa pelo cliente-pai para identificar '
    'as redes com maior volume e ocupação abaixo da meta. '
    'Depois é possível abrir as unidades e códigos-filhos.'
)

coluna_meta, coluna_top, coluna_volume = st.columns(3)

meta_ocupacao = coluna_meta.number_input(
    'Meta anual de ocupação (%)',
    min_value=0.0,
    max_value=150.0,
    value=67.31,
    step=0.01
) / 100

quantidade_clientes_grafico = coluna_top.slider(
    'Quantidade de clientes-pai',
    min_value=5,
    max_value=50,
    value=20,
    step=5
)

volume_minimo = coluna_volume.number_input(
    'Volume mínimo carregado (m³)',
    min_value=0.0,
    value=0.0,
    step=100.0
)


# VISÃO MACRO POR CLIENTE-PAI

df_clientes_pai = preparar_visao_ocupacao(
    dataframe=df_filtrado,
    coluna_agrupamento='cliente_pai',
    volume_minimo=volume_minimo
)

df_clientes_pai['situacao_meta'] = (
    df_clientes_pai['ocupacao']
    .ge(meta_ocupacao)
    .map({
        True: 'Na meta',
        False: 'Abaixo da meta'
    })
)

figura_clientes_pai = criar_grafico_ocupacao(
    dataframe=df_clientes_pai,
    coluna_categoria='cliente_pai',
    titulo_categoria='Cliente-pai',
    meta_ocupacao=meta_ocupacao,
    quantidade_itens=quantidade_clientes_grafico
)

if figura_clientes_pai is None:
    st.warning(
        'Nenhum cliente-pai foi encontrado para os filtros atuais.'
    )

else:
    st.plotly_chart(
        figura_clientes_pai,
        use_container_width=True
    )


# TABELA DOS CLIENTES-PAI ABAIXO DA META

clientes_pai_abaixo_meta = (
    df_clientes_pai.loc[
        df_clientes_pai['ocupacao'].lt(
            meta_ocupacao
        )
    ]
    .sort_values(
        'metro_carregado',
        ascending=False
    )
    .head(20)
    .copy()
)

st.subheader(
    'Clientes-pai com maior volume abaixo da meta'
)

if clientes_pai_abaixo_meta.empty:
    st.success(
        'Nenhum cliente-pai ficou abaixo da meta '
        'nos filtros selecionados.'
    )

else:
    clientes_pai_abaixo_meta['ocupacao_percentual'] = (
        clientes_pai_abaixo_meta['ocupacao']
        * 100
    )

    tabela_pais = (
        clientes_pai_abaixo_meta[
            [
                'cliente_pai',
                'metro_carregado',
                'metro_padrao',
                'ocupacao_percentual',
                'frete_total',
                'qtd_unidades',
                'qtd_codigos'
            ]
        ]
        .rename(
            columns={
                'cliente_pai': 'Cliente-pai',
                'metro_carregado': 'm³ carregado',
                'metro_padrao': 'm³ padrão',
                'ocupacao_percentual': 'Ocupação (%)',
                'frete_total': 'Frete total',
                'qtd_unidades': 'Unidades',
                'qtd_codigos': 'Códigos-filhos'
            }
        )
    )

    st.dataframe(
        tabela_pais,
        use_container_width=True,
        hide_index=True,
        column_config={
            'm³ carregado': (
                st.column_config.NumberColumn(
                    format='%.2f'
                )
            ),
            'm³ padrão': (
                st.column_config.NumberColumn(
                    format='%.2f'
                )
            ),
            'Ocupação (%)': (
                st.column_config.NumberColumn(
                    format='%.2f%%'
                )
            ),
            'Frete total': (
                st.column_config.NumberColumn(
                    format='R$ %.2f'
                )
            )
        }
    )


# DETALHAMENTO DO CLIENTE-PAI

st.divider()

st.subheader(
    'Detalhamento do cliente-pai'
)

opcoes_clientes_pai = (
    df_clientes_pai
    .sort_values(
        'metro_carregado',
        ascending=False
    )['cliente_pai']
    .dropna()
    .tolist()
)

if not opcoes_clientes_pai:
    st.info(
        'Nenhum cliente-pai disponível para detalhamento.'
    )

else:
    cliente_pai_detalhe = st.selectbox(
        'Selecione um cliente-pai para abrir as unidades:',
        options=opcoes_clientes_pai,
        index=None,
        placeholder='Selecione um cliente-pai'
    )

    if cliente_pai_detalhe is None:
        st.info(
            'Selecione um cliente-pai acima para visualizar '
            'as unidades e códigos-filhos.'
        )

    else:
        df_detalhe_pai = df_filtrado.loc[
            df_filtrado['cliente_pai'].eq(
                cliente_pai_detalhe
            )
        ].copy()

        metro_carregado_pai = (
            df_detalhe_pai['metro_carregado']
            .sum()
        )

        metro_padrao_pai = (
            df_detalhe_pai['metro_padrao']
            .sum()
        )

        ocupacao_pai = (
            metro_carregado_pai
            / metro_padrao_pai
            if metro_padrao_pai > 0
            else None
        )

        frete_pai = (
            df_detalhe_pai['frete_total']
            .sum()
        )

        qtd_unidades_pai = (
            df_detalhe_pai['cliente_unidade']
            .nunique()
        )

        qtd_codigos_pai = (
            df_detalhe_pai['cod_cliente']
            .nunique()
        )

        detalhe_coluna_1, detalhe_coluna_2 = st.columns(2)

        detalhe_coluna_3, detalhe_coluna_4 = st.columns(2)

        detalhe_coluna_1.metric(
            'Ocupação do cliente-pai',
            (
                f'{ocupacao_pai:.2%}'
                if ocupacao_pai is not None
                else 'Não calculada'
            ),
            delta=(
                f'{ocupacao_pai - meta_ocupacao:.2%} vs. meta'
                if ocupacao_pai is not None
                else None
            ),
            delta_color='normal'
        )

        detalhe_coluna_2.metric(
            'm³ carregados',
            formatar_numero(
                metro_carregado_pai
            )
        )

        detalhe_coluna_3.metric(
            'Unidades',
            formatar_inteiro(
                qtd_unidades_pai
            )
        )

        detalhe_coluna_4.metric(
            'Códigos-filhos',
            formatar_inteiro(
                qtd_codigos_pai
            )
        )

        st.caption(
            f'Frete total do cliente-pai: '
            f'R$ {formatar_numero(frete_pai)}'
        )


        # VISÃO POR UNIDADE DO CLIENTE-PAI

        df_unidades_pai = preparar_visao_ocupacao(
            dataframe=df_detalhe_pai,
            coluna_agrupamento='cliente_unidade'
        )

        quantidade_unidades_grafico = min(
            30,
            max(
                5,
                len(df_unidades_pai)
            )
        )

        figura_unidades = criar_grafico_ocupacao(
            dataframe=df_unidades_pai,
            coluna_categoria='cliente_unidade',
            titulo_categoria='Cliente / unidade',
            meta_ocupacao=meta_ocupacao,
            quantidade_itens=quantidade_unidades_grafico
        )

        st.markdown(
            f'### Unidades de {cliente_pai_detalhe}'
        )

        if figura_unidades is not None:
            st.plotly_chart(
                figura_unidades,
                use_container_width=True
            )


        # TABELA DOS CÓDIGOS-FILHOS

        df_codigos_filhos = (
            df_detalhe_pai
            .groupby(
                [
                    'cod_cliente',
                    'cliente_unidade'
                ],
                dropna=False
            )
            .agg(
                metro_carregado=(
                    'metro_carregado',
                    'sum'
                ),
                metro_padrao=(
                    'metro_padrao',
                    'sum'
                ),
                frete_total=(
                    'frete_total',
                    'sum'
                )
            )
            .reset_index()
        )

        df_codigos_filhos = df_codigos_filhos.loc[
            df_codigos_filhos['metro_padrao'].gt(0)
        ].copy()

        df_codigos_filhos['ocupacao_percentual'] = (
            df_codigos_filhos['metro_carregado']
            / df_codigos_filhos['metro_padrao']
            * 100
        )

        df_codigos_filhos['situacao'] = (
            (
                df_codigos_filhos[
                    'ocupacao_percentual'
                ] / 100
            )
            .ge(meta_ocupacao)
            .map({
                True: 'Na meta',
                False: 'Abaixo da meta'
            })
        )

        tabela_codigos = (
            df_codigos_filhos
            .sort_values(
                'metro_carregado',
                ascending=False
            )
            .rename(
                columns={
                    'cod_cliente': 'Código-filho',
                    'cliente_unidade': 'Cliente / unidade',
                    'metro_carregado': 'm³ carregado',
                    'metro_padrao': 'm³ padrão',
                    'ocupacao_percentual': 'Ocupação (%)',
                    'frete_total': 'Frete total',
                    'situacao': 'Situação'
                }
            )
        )

        st.markdown(
            '### Códigos-filhos'
        )

        st.dataframe(
            tabela_codigos,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Código-filho': (
                    st.column_config.NumberColumn(
                        format='%d'
                    )
                ),
                'm³ carregado': (
                    st.column_config.NumberColumn(
                        format='%.2f'
                    )
                ),
                'm³ padrão': (
                    st.column_config.NumberColumn(
                        format='%.2f'
                    )
                ),
                'Ocupação (%)': (
                    st.column_config.NumberColumn(
                        format='%.2f%%'
                    )
                ),
                'Frete total': (
                    st.column_config.NumberColumn(
                        format='R$ %.2f'
                    )
                )
            }
        )

# TABELA DOS DADOS FILTRADOS

st.divider()

st.subheader('Tabela de dados filtrados')

st.caption(
    f'{formatar_inteiro(len(df_filtrado))} registros '
    f'encontrados com os filtros aplicados.'
)

colunas_tabela = [
    'cliente_unidade',
    'cod_cliente',
    'cliente_pai',
    'visao',
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
    'frete_total'
]

df_exibicao = (
    df_filtrado[colunas_tabela]
    .sort_values(
        by='metro_padrao',
        ascending=False
    )
    .reset_index(drop=True)
)


# COLUNA AUXILIAR SOMENTE PARA EXIBIÇÃO

df_exibicao['ocupacao_percentual'] = (
    df_exibicao['ocupacao']
    * 100
)

df_exibicao = df_exibicao.drop(
    columns='ocupacao'
)


# RENOMEAR COLUNAS PARA EXIBIÇÃO

df_exibicao = df_exibicao.rename(
    columns={
        'cliente_unidade': 'Cliente / unidade',
        'cod_cliente': 'Código do cliente',
        'cliente_pai': 'Cliente-pai',
        'visao': 'Visão',
        'mes_nome': 'Mês',
        'cd_origem': 'CD de origem',
        'regiao': 'Região',
        'territorio': 'Território',
        'canal': 'Canal',
        'cidade': 'Cidade',
        'uf': 'UF',
        'perfil_veiculo': 'Perfil do veículo',
        'tipo_carregamento': 'Tipo de carregamento',
        'tipo_produto': 'Tipo de produto',
        'tipo_ordem': 'Tipo de ordem',
        'cod_transportadora': 'Código da transportadora',
        'metro_carregado': 'm³ carregados',
        'metro_padrao': 'm³ padrão',
        'ocupacao_percentual': 'Ocupação (%)',
        'frete_total': 'Frete total'
    }
)


st.dataframe(
    df_exibicao,
    use_container_width=True,
    hide_index=True,
    column_config={
        'Código do cliente': st.column_config.NumberColumn(
            format='%d'
        ),
        'CD de origem': st.column_config.NumberColumn(
            format='%d'
        ),
        'Código da transportadora': (
            st.column_config.NumberColumn(
                format='%d'
            )
        ),
        'm³ carregados': st.column_config.NumberColumn(
            format='%.2f'
        ),
        'm³ padrão': st.column_config.NumberColumn(
            format='%.2f'
        ),
        'Ocupação (%)': st.column_config.NumberColumn(
            format='%.2f%%'
        ),
        'Frete total': st.column_config.NumberColumn(
            format='R$ %.2f'
        )
    }
)


# DOWNLOAD DOS DADOS FILTRADOS

st.divider()

arquivo_csv = (
    df_filtrado
    .to_csv(
        index=False,
        sep=';',
        decimal=','
    )
    .encode('utf-8-sig')
)

st.download_button(
    label='📥 Baixar dados filtrados',
    data=arquivo_csv,
    file_name='ocupacao_filtrada.csv',
    mime='text/csv'
)