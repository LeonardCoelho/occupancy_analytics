import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title='Analise de Ocupacao Logistica',
    page_icon='🚛',
    layout='wide'
)

PASTA_APP = Path(__file__).resolve().parent
if (PASTA_APP / 'data').exists():
    BASE_DIR = PASTA_APP
elif (PASTA_APP.parent / 'data').exists():
    BASE_DIR = PASTA_APP.parent
else:
    st.error('Nao foi possivel localizar a pasta data do projeto.')
    st.stop()

ARQUIVO_ANALITICO = BASE_DIR / 'data' / 'processed' / 'ocupacao_analitica.parquet'
ARQUIVO_GEOJSON = BASE_DIR / 'data' / 'geo' / 'br_states.json'
URL_GEOJSON = (
    'https://raw.githubusercontent.com/giuliano-macedo/'
    'geodata-br-states/main/geojson/br_states.json'
)


@st.cache_data
def carregar_dados(caminho):
    return pd.read_parquet(caminho)


@st.cache_data(show_spinner=False, ttl=86400)
def carregar_geojson_brasil(caminho):
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        requisicao = Request(URL_GEOJSON, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(requisicao, timeout=60) as resposta:
            caminho.write_bytes(resposta.read())

    with caminho.open('r', encoding='utf-8') as arquivo:
        geojson = json.load(arquivo)

    features = geojson.get('features', [])
    if not features:
        raise ValueError('O GeoJSON nao possui geometrias.')

    codigo_para_uf = {
        '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA',
        '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE',
        '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE',
        '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
        '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT',
        '52': 'GO', '53': 'DF'
    }

    nomes_para_uf = {
        'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAPA': 'AP', 'AMAZONAS': 'AM',
        'BAHIA': 'BA', 'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF',
        'ESPIRITO SANTO': 'ES', 'GOIAS': 'GO', 'MARANHAO': 'MA',
        'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS',
        'MINAS GERAIS': 'MG', 'PARA': 'PA', 'PARAIBA': 'PB',
        'PARANA': 'PR', 'PERNAMBUCO': 'PE', 'PIAUI': 'PI',
        'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN',
        'RIO GRANDE DO SUL': 'RS', 'RONDONIA': 'RO', 'RORAIMA': 'RR',
        'SANTA CATARINA': 'SC', 'SAO PAULO': 'SP', 'SERGIPE': 'SE',
        'TOCANTINS': 'TO'
    }

    candidatos = [
        'sigla', 'SIGLA', 'uf', 'UF', 'code', 'CODE', 'abbrev_state',
        'SIGLA_UF', 'CD_UF', 'codigo_ibge', 'id', 'name', 'nome', 'NM_UF'
    ]

    for feature in features:
        propriedades = feature.get('properties', {})
        valor = next((propriedades.get(c) for c in candidatos if propriedades.get(c) is not None), None)

        if valor is None:
            valor = feature.get('id')

        texto = str(valor).upper().strip() if valor is not None else ''
        texto_sem_acento = (
            texto.replace('Á', 'A').replace('À', 'A').replace('Ã', 'A')
            .replace('Â', 'A').replace('É', 'E').replace('Ê', 'E')
            .replace('Í', 'I').replace('Ó', 'O').replace('Ô', 'O')
            .replace('Õ', 'O').replace('Ú', 'U').replace('Ç', 'C')
        )

        if len(texto) == 2 and texto.isalpha():
            uf = texto
        elif texto in codigo_para_uf:
            uf = codigo_para_uf[texto]
        else:
            uf = nomes_para_uf.get(texto_sem_acento)

        if not uf:
            raise ValueError(
                'Nao foi possivel identificar a UF no GeoJSON. '
                f'Propriedades: {list(propriedades.keys())}'
            )

        feature['id'] = uf
        propriedades['uf'] = uf

    return geojson


def valores_disponiveis(dataframe, coluna):
    return sorted(dataframe[coluna].dropna().unique().tolist())


def aplicar_filtro(dataframe, coluna, valores):
    if valores:
        return dataframe.loc[dataframe[coluna].isin(valores)].copy()
    return dataframe


def formatar_numero(valor, casas=2):
    texto = f'{valor:,.{casas}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def formatar_inteiro(valor):
    return f'{valor:,}'.replace(',', '.')


def preparar_visao_ocupacao(dataframe, coluna_agrupamento, volume_minimo=0.0):
    resultado = (
        dataframe.groupby(coluna_agrupamento, dropna=False)
        .agg(
            metro_carregado=('metro_carregado', 'sum'),
            metro_padrao=('metro_padrao', 'sum'),
            frete_total=('frete_total', 'sum'),
            qtd_unidades=('cliente_unidade', 'nunique'),
            qtd_codigos=('cod_cliente', 'nunique')
        )
        .reset_index()
    )
    resultado = resultado.loc[
        resultado['metro_padrao'].notna()
        & resultado['metro_padrao'].gt(0)
        & resultado['metro_carregado'].ge(volume_minimo)
    ].copy()
    resultado['ocupacao'] = resultado['metro_carregado'] / resultado['metro_padrao']
    return resultado


def criar_grafico_ocupacao(dataframe, categoria, titulo, meta, quantidade):
    dados = (
        dataframe
        .nlargest(quantidade, 'metro_carregado')
        .sort_values('metro_carregado', ascending=True)
        .reset_index(drop=True)
    )

    if dados.empty:
        return None

    dados['situacao'] = (
        dados['ocupacao']
        .ge(meta)
        .map({True: 'Na meta', False: 'Abaixo da meta'})
    )

    dados['cor'] = (
        dados['ocupacao']
        .ge(meta)
        .map({True: '#2E86DE', False: '#D9534F'})
    )

    dados['texto_ocupacao'] = dados['ocupacao'].map(
        lambda valor: f'{valor:.1%}'
    )

    dados['texto_volume'] = dados['metro_carregado'].map(
        lambda valor: f'{formatar_numero(valor, 0)} m3'
    )

    figura = go.Figure()

    figura.add_trace(
        go.Bar(
            x=dados['ocupacao'],
            y=dados[categoria],
            orientation='h',
            marker={
                'color': dados['cor'],
                'line': {'color': '#FFFFFF', 'width': 0.8}
            },
            text=dados['texto_ocupacao'],
            textposition='inside',
            insidetextanchor='end',
            textfont={
                'size': 12,
                'color': '#FFFFFF',
                'family': 'Arial Black'
            },
            customdata=dados[
                [
                    'metro_carregado',
                    'metro_padrao',
                    'frete_total',
                    'qtd_unidades',
                    'qtd_codigos',
                    'situacao'
                ]
            ].to_numpy(),
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Ocupacao: %{x:.2%}<br>'
                'm3 carregado: %{customdata[0]:,.2f}<br>'
                'm3 padrao: %{customdata[1]:,.2f}<br>'
                'Frete total: R$ %{customdata[2]:,.2f}<br>'
                'Unidades: %{customdata[3]}<br>'
                'Codigos-filhos: %{customdata[4]}<br>'
                'Situacao: %{customdata[5]}'
                '<extra></extra>'
            ),
            showlegend=False
        )
    )

    figura.add_trace(
        go.Scatter(
            x=[1.025] * len(dados),
            y=dados[categoria],
            mode='text',
            text=dados['texto_volume'],
            textposition='middle right',
            textfont={'size': 11, 'color': '#FFFFFF'},
            hoverinfo='skip',
            showlegend=False,
            cliponaxis=False
        )
    )

    figura.add_vline(
        x=meta,
        line_dash='dash',
        line_color='#F1C40F',
        line_width=3,
        annotation_text=f'Meta: {meta:.2%}',
        annotation_position='top'
    )

    altura = max(520, len(dados) * 42)

    figura.update_layout(
        height=altura,
        margin={'l': 20, 'r': 150, 't': 70, 'b': 40},
        hovermode='closest',
        bargap=0.22,
        xaxis={
            'title': 'Ocupacao',
            'tickformat': '.0%',
            'range': [0, 1.18],
            'showgrid': True,
            'zeroline': False
        },
        yaxis={
            'title': titulo,
            'automargin': True
        }
    )

    return figura


if not ARQUIVO_ANALITICO.exists():
    st.error(f'Arquivo nao encontrado: {ARQUIVO_ANALITICO}')
    st.info('Execute python src/extract.py e python src/transform.py.')
    st.stop()


df = carregar_dados(ARQUIVO_ANALITICO)

if 'uf_mapa_ativa' not in st.session_state:
    st.session_state['uf_mapa_ativa'] = None
if 'mapa_uf_versao' not in st.session_state:
    st.session_state['mapa_uf_versao'] = 0

st.title('Analise de Ocupacao Logistica')
st.caption('Painel interativo por cliente-pai, unidade e codigo-filho.')

st.sidebar.header('Filtros principais')

visoes = valores_disponiveis(df, 'visao')
visoes_selecionadas = st.sidebar.multiselect(
    'Visao:', visoes, default=['Real'] if 'Real' in visoes else visoes
)

meses = (
    df[['mes_numero', 'mes_nome']].drop_duplicates().dropna()
    .sort_values('mes_numero').reset_index(drop=True)
)
mapa_meses = dict(zip(meses['mes_nome'], meses['mes_numero']))
nomes_meses = meses['mes_nome'].tolist()
meses_selecionados = st.sidebar.multiselect('Mes:', nomes_meses, default=nomes_meses)
numeros_meses = [mapa_meses[mes] for mes in meses_selecionados]

cds = valores_disponiveis(df, 'cd_origem')
cds_selecionados = st.sidebar.multiselect('CD de origem:', cds, default=cds)

meta_ocupacao = st.sidebar.number_input(
    'Meta anual de ocupacao (%)', min_value=0.0, max_value=100.0,
    value=67.31, step=0.01
) / 100

if not visoes_selecionadas or not meses_selecionados or not cds_selecionados:
    st.warning('Selecione ao menos uma visao, um mes e um CD.')
    st.stop()


df_filtrado = df.loc[
    df['visao'].isin(visoes_selecionadas)
    & df['mes_numero'].isin(numeros_meses)
    & df['cd_origem'].isin(cds_selecionados)
].copy()

st.sidebar.divider()
with st.sidebar.expander('Filtros adicionais', expanded=False):
    configuracoes = [
        ('cliente_pai', 'Cliente-pai:'),
        ('cliente_unidade', 'Cliente / unidade:'),
        ('cod_cliente', 'Codigo do cliente:'),
        ('territorio', 'Territorio:'),
        ('canal', 'Canal:'),
        ('tipo_carregamento', 'Tipo de carregamento:'),
        ('tipo_produto', 'Tipo de produto:'),
        ('perfil_veiculo', 'Perfil do veiculo:'),
        ('tipo_ordem', 'Tipo de ordem:')
    ]
    for coluna, rotulo in configuracoes:
        opcoes = valores_disponiveis(df_filtrado, coluna)
        selecao = st.multiselect(rotulo, opcoes, placeholder='Todos')
        df_filtrado = aplicar_filtro(df_filtrado, coluna, selecao)

    ufs_disponiveis = valores_disponiveis(df_filtrado, 'uf')
    ufs_selecionadas = st.multiselect('UF:', ufs_disponiveis, placeholder='Todas as UFs')


df_antes_uf = df_filtrado.copy()

st.divider()
st.subheader('Ocupacao por estado')
st.caption('Clique em um estado para filtrar o restante do painel.')

df_mapa = preparar_visao_ocupacao(df_antes_uf, 'uf')
df_mapa['ocupacao_percentual'] = df_mapa['ocupacao'] * 100
df_mapa['situacao_meta'] = df_mapa['ocupacao'].ge(meta_ocupacao).map({True: 'Na meta', False: 'Abaixo da meta'})

coordenadas_ufs = {
    'AC': (-9.02, -70.81), 'AL': (-9.70, -34.80),
    'AP': (1.41, -51.77), 'AM': (-3.47, -65.10),
    'BA': (-12.96, -41.70), 'CE': (-5.20, -39.53),
    'DF': (-15.75, -46.80), 'ES': (-19.20, -38.80),
    'GO': (-15.98, -49.86), 'MA': (-5.42, -45.44),
    'MT': (-12.64, -55.42), 'MS': (-20.51, -54.54),
    'MG': (-18.10, -44.38), 'PA': (-3.79, -52.48),
    'PB': (-7.10, -34.50), 'PR': (-24.89, -51.55),
    'PE': (-8.15, -34.90), 'PI': (-6.60, -42.28),
    'RJ': (-22.40, -40.50), 'RN': (-5.70, -34.60),
    'RS': (-30.17, -53.50), 'RO': (-10.83, -63.34),
    'RR': (2.73, -61.33), 'SC': (-27.45, -50.95),
    'SP': (-22.19, -48.79), 'SE': (-10.80, -35.30),
    'TO': (-10.25, -48.25)
}

ufs_pequenas = {'DF', 'SE', 'AL', 'ES', 'RJ', 'RN', 'PB'}

df_mapa['latitude'] = df_mapa['uf'].map(
    lambda uf: coordenadas_ufs.get(uf, (None, None))[0]
)
df_mapa['longitude'] = df_mapa['uf'].map(
    lambda uf: coordenadas_ufs.get(uf, (None, None))[1]
)
df_mapa['texto_mapa'] = df_mapa.apply(
    lambda linha: f"{linha['uf']} {linha['ocupacao_percentual']:.0f}%",
    axis=1
)

evento_mapa = None
try:
    geojson = carregar_geojson_brasil(ARQUIVO_GEOJSON)
    escala = [
        [0.0, '#C0392B'], [meta_ocupacao, '#C0392B'],
        [meta_ocupacao, '#2E86DE'], [1.0, '#2E86DE']
    ]
    figura_mapa = px.choropleth(
        df_mapa, geojson=geojson, locations='uf', featureidkey='id',
        color='ocupacao_percentual', hover_name='uf', custom_data=['uf'],
        hover_data={
            'ocupacao_percentual': ':.2f', 'metro_carregado': ':,.2f',
            'metro_padrao': ':,.2f', 'frete_total': ':,.2f',
            'qtd_unidades': True, 'qtd_codigos': True, 'situacao_meta': True
        },
        color_continuous_scale=escala, range_color=[0, 100],
        labels={'ocupacao_percentual': 'Ocupacao (%)'}
    )
    figura_mapa.add_trace(
        go.Scattergeo(
            lat=df_mapa['latitude'],
            lon=df_mapa['longitude'],
            text=df_mapa['texto_mapa'],
            mode='text',
            textfont={
                'size': 9,
                'color': '#FFFFFF',
                'family': 'Arial Black'
            },
            hoverinfo='skip',
            showlegend=False
        )
    )

    figura_mapa.update_geos(
        fitbounds='locations', visible=False, showland=False,
        showocean=False, showlakes=False, bgcolor='rgba(0,0,0,0)',
        projection_type='mercator'
    )
    figura_mapa.update_traces(
        marker_line_color='#FFFFFF',
        marker_line_width=1.0,
        selected={'marker': {'opacity': 1.0}},
        unselected={'marker': {'opacity': 0.45}},
        selector={'type': 'choropleth'}
    )
    figura_mapa.update_layout(
        height=650, margin={'l': 0, 'r': 0, 't': 10, 'b': 0},
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        geo={'bgcolor': 'rgba(0,0,0,0)'}, clickmode='event+select',
        coloraxis_colorbar={'title': 'Ocupacao', 'ticksuffix': '%'}
    )
    chave = f'mapa_uf_{st.session_state["mapa_uf_versao"]}'
    evento_mapa = st.plotly_chart(
        figura_mapa, on_select='rerun', selection_mode='points',
        key=chave, width='stretch'
    )
except Exception as erro:
    st.warning('Nao foi possivel carregar o mapa.')
    st.caption(f'Detalhe tecnico: {erro}')

if evento_mapa is not None:
    pontos = evento_mapa.get('selection', {}).get('points', [])
    if pontos:
        ponto = pontos[0]
        customdata = ponto.get('customdata', [])
        uf_clicada = customdata[0] if customdata else ponto.get('location')
        if uf_clicada:
            uf_clicada = str(uf_clicada).upper().strip()
        if uf_clicada and uf_clicada != st.session_state['uf_mapa_ativa']:
            st.session_state['uf_mapa_ativa'] = uf_clicada
            st.rerun()

coluna_status, coluna_limpar = st.columns([4, 1])
uf_mapa_ativa = st.session_state['uf_mapa_ativa']
if uf_mapa_ativa:
    coluna_status.success(f'UF selecionada no mapa: {uf_mapa_ativa}')
    if coluna_limpar.button('Limpar selecao', use_container_width=True):
        st.session_state['uf_mapa_ativa'] = None
        st.session_state['mapa_uf_versao'] += 1
        st.rerun()
else:
    coluna_status.info('Nenhuma UF selecionada no mapa.')


df_filtrado = aplicar_filtro(df_antes_uf, 'uf', ufs_selecionadas)
if uf_mapa_ativa:
    df_filtrado = aplicar_filtro(df_filtrado, 'uf', [uf_mapa_ativa])

if df_filtrado.empty:
    st.warning('Nenhum registro encontrado com os filtros aplicados.')
    st.stop()

metro_carregado = df_filtrado['metro_carregado'].sum()
metro_padrao = df_filtrado['metro_padrao'].sum()
frete_total = df_filtrado['frete_total'].sum()
ocupacao = metro_carregado / metro_padrao if metro_padrao > 0 else None

st.subheader('Indicadores do periodo filtrado')
c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)
c1.metric('Ocupacao', f'{ocupacao:.2%}' if ocupacao is not None else 'N/A')
c2.metric('m3 carregados', formatar_numero(metro_carregado))
c3.metric('m3 padrao', formatar_numero(metro_padrao))
c4.metric('Frete total', f'R$ {formatar_numero(frete_total)}')
c5.metric('Unidades distintas', formatar_inteiro(df_filtrado['cliente_unidade'].nunique()))
c6.metric('Codigos de cliente', formatar_inteiro(df_filtrado['cod_cliente'].nunique()))

st.caption(f'{formatar_inteiro(len(df_filtrado))} registros analiticos no filtro atual.')

with st.expander('Como e calculada a ocupacao?'):
    st.code('Ocupacao = soma do m3 carregado / soma do m3 padrao')

st.divider()
st.subheader('Ocupacao dos clientes com maior volume carregado')
st.caption(
    'Clientes ordenados pelo maior volume carregado. O percentual aparece dentro '
    'da barra e o volume e exibido a direita. Vermelho indica resultado abaixo '
    'da meta; azul indica resultado na meta ou acima.'
)
col_top, col_volume = st.columns(2)
quantidade = col_top.slider('Quantidade de clientes-pai', 5, 50, 20, 5)
volume_minimo = col_volume.number_input('Volume minimo carregado (m3)', min_value=0.0, value=0.0, step=100.0)

df_clientes_pai = preparar_visao_ocupacao(df_filtrado, 'cliente_pai', volume_minimo)
figura = criar_grafico_ocupacao(df_clientes_pai, 'cliente_pai', 'Cliente-pai', meta_ocupacao, quantidade)
if figura is not None:
    st.plotly_chart(figura, width='stretch')

abaixo = (
    df_clientes_pai.loc[df_clientes_pai['ocupacao'].lt(meta_ocupacao)]
    .sort_values('metro_carregado', ascending=False).head(20).copy()
)
st.subheader('Clientes-pai com maior volume abaixo da meta')
if abaixo.empty:
    st.success('Nenhum cliente-pai ficou abaixo da meta.')
else:
    abaixo['ocupacao_percentual'] = abaixo['ocupacao'] * 100
    tabela_pais = abaixo[[
        'cliente_pai', 'metro_carregado', 'metro_padrao',
        'ocupacao_percentual', 'frete_total', 'qtd_unidades', 'qtd_codigos'
    ]].rename(columns={
        'cliente_pai': 'Cliente-pai', 'metro_carregado': 'm3 carregado',
        'metro_padrao': 'm3 padrao', 'ocupacao_percentual': 'Ocupacao (%)',
        'frete_total': 'Frete total', 'qtd_unidades': 'Unidades',
        'qtd_codigos': 'Codigos-filhos'
    })
    st.dataframe(tabela_pais, width='stretch', hide_index=True)

st.divider()
st.subheader('Detalhamento do cliente-pai')
opcoes_pai = df_clientes_pai.sort_values('metro_carregado', ascending=False)['cliente_pai'].dropna().tolist()
cliente_pai = st.selectbox(
    'Selecione um cliente-pai para abrir as unidades:',
    opcoes_pai, index=None, placeholder='Selecione um cliente-pai'
)

if cliente_pai:
    detalhe = df_filtrado.loc[df_filtrado['cliente_pai'].eq(cliente_pai)].copy()
    mc_pai = detalhe['metro_carregado'].sum()
    mp_pai = detalhe['metro_padrao'].sum()
    ocupacao_pai = mc_pai / mp_pai if mp_pai > 0 else None
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(
        'Ocupacao do cliente-pai',
        f'{ocupacao_pai:.2%}' if ocupacao_pai is not None else 'N/A',
        delta=f'{ocupacao_pai - meta_ocupacao:.2%} vs. meta' if ocupacao_pai is not None else None
    )
    d2.metric('m3 carregados', formatar_numero(mc_pai))
    d3.metric('Unidades', formatar_inteiro(detalhe['cliente_unidade'].nunique()))
    d4.metric('Codigos-filhos', formatar_inteiro(detalhe['cod_cliente'].nunique()))

    unidades = preparar_visao_ocupacao(detalhe, 'cliente_unidade')
    figura_unidades = criar_grafico_ocupacao(
        unidades, 'cliente_unidade', 'Cliente / unidade', meta_ocupacao,
        min(30, max(5, len(unidades)))
    )
    if figura_unidades is not None:
        st.plotly_chart(figura_unidades, width='stretch')

    codigos = (
        detalhe.groupby(['cod_cliente', 'cliente_unidade'], dropna=False)
        .agg(
            metro_carregado=('metro_carregado', 'sum'),
            metro_padrao=('metro_padrao', 'sum'),
            frete_total=('frete_total', 'sum')
        ).reset_index()
    )
    codigos = codigos.loc[codigos['metro_padrao'].gt(0)].copy()
    codigos['ocupacao'] = codigos['metro_carregado'] / codigos['metro_padrao']
    codigos['situacao'] = codigos['ocupacao'].ge(meta_ocupacao).map({True: 'Na meta', False: 'Abaixo da meta'})
    st.markdown('### Codigos-filhos')
    st.dataframe(codigos.sort_values('metro_carregado', ascending=False), width='stretch', hide_index=True)

st.divider()
st.subheader('Tabela de dados filtrados')
colunas = [
    'cliente_unidade', 'cod_cliente', 'cliente_pai', 'visao', 'mes_nome',
    'cd_origem', 'regiao', 'territorio', 'canal', 'cidade', 'uf',
    'perfil_veiculo', 'tipo_carregamento', 'tipo_produto', 'tipo_ordem',
    'cod_transportadora', 'metro_carregado', 'metro_padrao', 'ocupacao',
    'frete_total'
]
st.dataframe(
    df_filtrado[colunas].sort_values('metro_padrao', ascending=False),
    width='stretch', hide_index=True
)

st.divider()
arquivo_csv = df_filtrado.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
st.download_button(
    '📥 Baixar dados filtrados', arquivo_csv,
    file_name='ocupacao_filtrada.csv', mime='text/csv'
)
