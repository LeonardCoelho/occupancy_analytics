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


def criar_heatmap_geografia_perfil(
    dataframe,
    coluna_geografica,
    localidades,
    meta
):
    base = dataframe.loc[
        dataframe[coluna_geografica].isin(localidades)
        & dataframe['perfil_veiculo'].notna()
    ].copy()

    if base.empty:
        return None

    agrupado = (
        base
        .groupby(
            [coluna_geografica, 'perfil_veiculo'],
            dropna=False
        )
        .agg(
            metro_carregado=('metro_carregado', 'sum'),
            metro_padrao=('metro_padrao', 'sum'),
            frete_total=('frete_total', 'sum')
        )
        .reset_index()
    )

    agrupado = agrupado.loc[
        agrupado['metro_padrao'].gt(0)
    ].copy()

    if agrupado.empty:
        return None

    agrupado['ocupacao'] = (
        agrupado['metro_carregado']
        / agrupado['metro_padrao']
    )

    ordem_localidades = [
        localidade
        for localidade in localidades
        if localidade in agrupado[coluna_geografica].values
    ]

    ordem_perfis = (
        agrupado
        .groupby('perfil_veiculo')['metro_carregado']
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    matriz_ocupacao = (
        agrupado
        .pivot(
            index=coluna_geografica,
            columns='perfil_veiculo',
            values='ocupacao'
        )
        .reindex(
            index=ordem_localidades,
            columns=ordem_perfis
        )
    )

    matriz_carregado = (
        agrupado
        .pivot(
            index=coluna_geografica,
            columns='perfil_veiculo',
            values='metro_carregado'
        )
        .reindex(
            index=ordem_localidades,
            columns=ordem_perfis
        )
    )

    matriz_padrao = (
        agrupado
        .pivot(
            index=coluna_geografica,
            columns='perfil_veiculo',
            values='metro_padrao'
        )
        .reindex(
            index=ordem_localidades,
            columns=ordem_perfis
        )
    )

    matriz_frete = (
        agrupado
        .pivot(
            index=coluna_geografica,
            columns='perfil_veiculo',
            values='frete_total'
        )
        .reindex(
            index=ordem_localidades,
            columns=ordem_perfis
        )
    )

    textos = []
    dados_hover = []

    for localidade in ordem_localidades:
        linha_textos = []
        linha_hover = []

        for perfil in ordem_perfis:
            valor = matriz_ocupacao.loc[localidade, perfil]

            if pd.isna(valor):
                linha_textos.append('')
                linha_hover.append([None, None, None])
            else:
                linha_textos.append(f'{valor:.0%}')
                linha_hover.append([
                    matriz_carregado.loc[localidade, perfil],
                    matriz_padrao.loc[localidade, perfil],
                    matriz_frete.loc[localidade, perfil]
                ])

        textos.append(linha_textos)
        dados_hover.append(linha_hover)

    escala = [
        [0.0, '#C0392B'],
        [meta, '#C0392B'],
        [meta, '#2E86DE'],
        [1.0, '#2E86DE']
    ]

    figura = go.Figure(
        data=go.Heatmap(
            z=matriz_ocupacao.values,
            x=ordem_perfis,
            y=ordem_localidades,
            zmin=0,
            zmax=1,
            colorscale=escala,
            text=textos,
            texttemplate='%{text}',
            textfont={'size': 11, 'color': '#FFFFFF'},
            customdata=dados_hover,
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Perfil: %{x}<br>'
                'Ocupacao: %{z:.2%}<br>'
                'm3 carregado: %{customdata[0]:,.2f}<br>'
                'm3 padrao: %{customdata[1]:,.2f}<br>'
                'Frete total: R$ %{customdata[2]:,.2f}'
                '<extra></extra>'
            ),
            colorbar={
                'title': 'Ocupacao',
                'tickformat': '.0%'
            },
            xgap=2,
            ygap=2
        )
    )

    figura.update_layout(
        height=max(520, len(ordem_localidades) * 42),
        margin={'l': 20, 'r': 30, 't': 30, 'b': 130},
        xaxis={
            'title': 'Perfil de veiculo',
            'tickangle': -45,
            'automargin': True
        },
        yaxis={
            'title': 'Localidade',
            'automargin': True,
            'autorange': 'reversed'
        }
    )

    return figura


def calcular_resumo_visao(dataframe, visao):
    base = dataframe.loc[dataframe['visao'].eq(visao)].copy()
    metro_carregado = base['metro_carregado'].sum()
    metro_padrao = base['metro_padrao'].sum()
    ocupacao = (
        metro_carregado / metro_padrao
        if metro_padrao > 0
        else None
    )

    return {
        'metro_carregado': metro_carregado,
        'metro_padrao': metro_padrao,
        'ocupacao': ocupacao,
        'frete_total': base['frete_total'].sum(),
        'registros': len(base)
    }


def preparar_comparativo_grupo(dataframe, coluna_grupo):
    agrupado = (
        dataframe
        .groupby([coluna_grupo, 'visao'], dropna=False)
        .agg(
            metro_carregado=('metro_carregado', 'sum'),
            metro_padrao=('metro_padrao', 'sum'),
            frete_total=('frete_total', 'sum')
        )
        .reset_index()
    )

    agrupado = agrupado.loc[agrupado['metro_padrao'].gt(0)].copy()
    agrupado['ocupacao'] = (
        agrupado['metro_carregado'] / agrupado['metro_padrao']
    )

    comparativo = agrupado.pivot(
        index=coluna_grupo,
        columns='visao',
        values=['metro_carregado', 'metro_padrao', 'frete_total', 'ocupacao']
    )

    comparativo.columns = [
        f'{metrica}_{str(visao).lower()}'
        for metrica, visao in comparativo.columns
    ]
    comparativo = comparativo.reset_index()

    colunas_esperadas = [
        'metro_carregado_real', 'metro_carregado_aa',
        'metro_padrao_real', 'metro_padrao_aa',
        'frete_total_real', 'frete_total_aa',
        'ocupacao_real', 'ocupacao_aa'
    ]
    for coluna in colunas_esperadas:
        if coluna not in comparativo.columns:
            comparativo[coluna] = pd.NA

    comparativo['variacao_ocupacao_pp'] = (
        comparativo['ocupacao_real'] - comparativo['ocupacao_aa']
    )
    comparativo['variacao_volume_pct'] = (
        comparativo['metro_carregado_real']
        / comparativo['metro_carregado_aa']
        - 1
    )

    return comparativo


def criar_grafico_clientes_gerencial(dataframe, meta, quantidade):
    dados = preparar_comparativo_grupo(dataframe, 'cliente_pai')
    dados = dados.loc[
        dados['metro_carregado_real'].notna()
        & dados['ocupacao_real'].notna()
    ].copy()

    if dados.empty:
        return None

    dados['abaixo_meta'] = dados['ocupacao_real'].lt(meta)
    dados = (
        dados
        .sort_values(
            ['abaixo_meta', 'metro_carregado_real'],
            ascending=[False, False]
        )
        .head(quantidade)
        .sort_values('metro_carregado_real', ascending=True)
        .reset_index(drop=True)
    )

    maior_volume = dados['metro_carregado_real'].max()
    dados['volume_relativo'] = (
        dados['metro_carregado_real'] / maior_volume
        if maior_volume > 0
        else 0
    )
    dados['cor_ocupacao'] = dados['ocupacao_real'].ge(meta).map({
        True: '#27AE60',
        False: '#D9534F'
    })
    dados['texto_volume'] = dados['metro_carregado_real'].map(
        lambda valor: f'{formatar_numero(valor, 0)} m3'
    )
    dados['texto_ocupacao'] = dados['ocupacao_real'].map(
        lambda valor: f'{valor:.1%}'
    )

    # Metade esquerda: volume parte da borda e avanca para o centro.
    inicio_volume = -1.0
    comprimento_volume = dados['volume_relativo']

    # Metade direita: ocupacao parte da borda direita e volta para o centro.
    inicio_ocupacao = 1.0 - dados['ocupacao_real']
    comprimento_ocupacao = dados['ocupacao_real']

    figura = go.Figure()

    figura.add_trace(go.Bar(
        x=comprimento_volume,
        base=[inicio_volume] * len(dados),
        y=dados['cliente_pai'],
        orientation='h',
        name='Volume relativo',
        marker_color='#7F8C8D',
        text=dados['texto_volume'],
        textposition='inside',
        insidetextanchor='start',
        textfont={'color': '#FFFFFF', 'size': 11},
        customdata=dados[
            ['metro_carregado_real', 'metro_carregado_aa']
        ].to_numpy(),
        hovertemplate=(
            '<b>%{y}</b><br>'
            'm3 carregado Real: %{customdata[0]:,.2f}<br>'
            'm3 carregado AA: %{customdata[1]:,.2f}<br>'
            'Volume relativo: %{x:.1%} do maior cliente'
            '<extra></extra>'
        )
    ))

    figura.add_trace(go.Bar(
        x=comprimento_ocupacao,
        base=inicio_ocupacao,
        y=dados['cliente_pai'],
        orientation='h',
        name='Ocupacao Real',
        marker_color=dados['cor_ocupacao'],
        text=dados['texto_ocupacao'],
        textposition='inside',
        insidetextanchor='start',
        textfont={'color': '#FFFFFF', 'size': 11},
        customdata=dados[
            ['ocupacao_aa', 'variacao_ocupacao_pp', 'metro_carregado_real']
        ].to_numpy(),
        hovertemplate=(
            '<b>%{y}</b><br>'
            'Ocupacao Real: %{x:.2%}<br>'
            'Ocupacao AA: %{customdata[0]:.2%}<br>'
            'Real x AA: %{customdata[1]:+.2%}<br>'
            'm3 carregado Real: %{customdata[2]:,.2f}'
            '<extra></extra>'
        )
    ))

    # A meta na metade direita e convertida para a posicao da ponta interna.
    posicao_meta = 1.0 - meta
    figura.add_vline(
        x=posicao_meta,
        line_dash='dash',
        line_color='#F1C40F',
        line_width=3,
        annotation_text=f'Meta: {meta:.2%}',
        annotation_position='top right'
    )

    figura.add_vline(
        x=0,
        line_color='rgba(255,255,255,0.35)',
        line_width=1
    )

    figura.update_layout(
        barmode='overlay',
        height=max(560, len(dados) * 46),
        margin={'l': 20, 'r': 30, 't': 85, 'b': 55},
        bargap=0.30,
        legend={
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': 1.06,
            'xanchor': 'left',
            'x': 0
        },
        xaxis={
            'title': 'Volume relativo  →                 ←  Ocupacao Real',
            'range': [-1.02, 1.02],
            'tickvals': [-1, -0.5, 0, 0.5, 1],
            'ticktext': ['Inicio volume', '50%', 'Centro', '50%', 'Inicio ocupacao'],
            'showgrid': True,
            'zeroline': False
        },
        yaxis={'title': 'Cliente-pai', 'automargin': True},
        hovermode='closest'
    )

    return figura


def criar_grafico_gap_meta(dataframe, meta, quantidade=10):
    dados = preparar_comparativo_grupo(dataframe, 'cliente_pai')
    dados = dados.loc[
        dados['metro_carregado_real'].notna()
        & dados['metro_padrao_real'].notna()
        & dados['ocupacao_real'].notna()
    ].copy()

    dados['gap_meta_m3'] = (
        meta * dados['metro_padrao_real']
        - dados['metro_carregado_real']
    ).clip(lower=0)
    dados = (
        dados.loc[dados['gap_meta_m3'].gt(0)]
        .nlargest(quantidade, 'gap_meta_m3')
        .sort_values('gap_meta_m3', ascending=True)
        .reset_index(drop=True)
    )

    if dados.empty:
        return None

    dados['texto_gap'] = dados['gap_meta_m3'].map(
        lambda valor: f'{formatar_numero(valor, 0)} m3'
    )

    figura = go.Figure(go.Bar(
        x=dados['gap_meta_m3'],
        y=dados['cliente_pai'],
        orientation='h',
        marker_color='#E67E22',
        text=dados['texto_gap'],
        textposition='outside',
        cliponaxis=False,
        customdata=dados[
            [
                'ocupacao_real', 'ocupacao_aa',
                'metro_carregado_real', 'metro_padrao_real'
            ]
        ].to_numpy(),
        hovertemplate=(
            '<b>%{y}</b><br>'
            'Gap para a meta: %{x:,.2f} m3<br>'
            'Ocupacao Real: %{customdata[0]:.2%}<br>'
            'Ocupacao AA: %{customdata[1]:.2%}<br>'
            'm3 carregado Real: %{customdata[2]:,.2f}<br>'
            'm3 padrao Real: %{customdata[3]:,.2f}'
            '<extra></extra>'
        )
    ))

    figura.update_layout(
        height=max(480, len(dados) * 44),
        margin={'l': 20, 'r': 120, 't': 30, 'b': 50},
        xaxis={
            'title': 'm3 adicionais estimados para atingir a meta',
            'rangemode': 'tozero',
            'showgrid': True
        },
        yaxis={'title': 'Cliente-pai', 'automargin': True},
        showlegend=False
    )

    return figura


def criar_heatmap_uf_perfil_gerencial(dataframe, meta):
    base = dataframe.loc[
        dataframe['uf'].notna()
        & dataframe['perfil_veiculo'].notna()
    ].copy()

    if base.empty:
        return None

    agrupado = (
        base
        .groupby(['uf', 'perfil_veiculo', 'visao'], dropna=False)
        .agg(
            metro_carregado=('metro_carregado', 'sum'),
            metro_padrao=('metro_padrao', 'sum')
        )
        .reset_index()
    )
    agrupado = agrupado.loc[agrupado['metro_padrao'].gt(0)].copy()
    agrupado['ocupacao'] = (
        agrupado['metro_carregado'] / agrupado['metro_padrao']
    )

    real = agrupado.loc[agrupado['visao'].eq('Real')].copy()
    aa = agrupado.loc[agrupado['visao'].eq('AA')].copy()
    aa = aa.rename(columns={
        'ocupacao': 'ocupacao_aa',
        'metro_carregado': 'metro_carregado_aa'
    })[['uf', 'perfil_veiculo', 'ocupacao_aa', 'metro_carregado_aa']]

    combinado = real.merge(
        aa,
        on=['uf', 'perfil_veiculo'],
        how='left'
    )

    ordem_ufs = (
        combinado.groupby('uf')['metro_carregado']
        .sum().sort_values(ascending=False).index.tolist()
    )
    ordem_perfis = (
        combinado.groupby('perfil_veiculo')['metro_carregado']
        .sum().sort_values(ascending=False).index.tolist()
    )

    matriz_real = combinado.pivot(
        index='uf', columns='perfil_veiculo', values='ocupacao'
    ).reindex(index=ordem_ufs, columns=ordem_perfis)
    matriz_aa = combinado.pivot(
        index='uf', columns='perfil_veiculo', values='ocupacao_aa'
    ).reindex(index=ordem_ufs, columns=ordem_perfis)
    matriz_volume = combinado.pivot(
        index='uf', columns='perfil_veiculo', values='metro_carregado'
    ).reindex(index=ordem_ufs, columns=ordem_perfis)

    textos = []
    dados_hover = []
    for uf in ordem_ufs:
        linha_textos = []
        linha_hover = []
        for perfil in ordem_perfis:
            real_valor = matriz_real.loc[uf, perfil]
            aa_valor = matriz_aa.loc[uf, perfil]
            volume = matriz_volume.loc[uf, perfil]
            if pd.isna(real_valor):
                linha_textos.append('')
                linha_hover.append([None, None])
            else:
                seta = ''
                if pd.notna(aa_valor):
                    seta = '▲' if real_valor >= aa_valor else '▼'
                linha_textos.append(f'{real_valor:.0%} {seta}')
                linha_hover.append([aa_valor, volume])
        textos.append(linha_textos)
        dados_hover.append(linha_hover)

    escala = [
        [0.0, '#D9534F'],
        [meta, '#D9534F'],
        [meta, '#27AE60'],
        [1.0, '#27AE60']
    ]

    figura = go.Figure(go.Heatmap(
        z=matriz_real.values,
        x=ordem_perfis,
        y=ordem_ufs,
        zmin=0,
        zmax=1,
        colorscale=escala,
        text=textos,
        texttemplate='%{text}',
        textfont={'size': 10, 'color': '#FFFFFF'},
        customdata=dados_hover,
        hovertemplate=(
            '<b>UF: %{y}</b><br>'
            'Perfil: %{x}<br>'
            'Ocupacao Real: %{z:.2%}<br>'
            'Ocupacao AA: %{customdata[0]:.2%}<br>'
            'm3 carregado Real: %{customdata[1]:,.2f}'
            '<extra></extra>'
        ),
        colorbar={'title': 'Ocupacao', 'tickformat': '.0%'},
        xgap=2,
        ygap=2
    ))

    figura.update_layout(
        height=max(520, len(ordem_ufs) * 38),
        margin={'l': 20, 'r': 30, 't': 30, 'b': 140},
        xaxis={'title': 'Perfil de veiculo', 'tickangle': -45},
        yaxis={'title': 'UF', 'autorange': 'reversed'}
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

st.sidebar.caption('Comparacao automatica: Real x AA')

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

if not meses_selecionados or not cds_selecionados:
    st.warning('Selecione ao menos um mes e um CD.')
    st.stop()


df_filtrado = df.loc[
    df['mes_numero'].isin(numeros_meses)
    & df['cd_origem'].isin(cds_selecionados)
    & df['visao'].isin(['Real', 'AA'])
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

df_mapa = preparar_visao_ocupacao(
    df_antes_uf.loc[df_antes_uf['visao'].eq('Real')].copy(),
    'uf'
)
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

df_real = df_filtrado.loc[df_filtrado['visao'].eq('Real')].copy()
df_aa = df_filtrado.loc[df_filtrado['visao'].eq('AA')].copy()

if df_real.empty:
    st.warning('Nao existem registros da visao Real para os filtros atuais.')
    st.stop()

resumo_real = calcular_resumo_visao(df_filtrado, 'Real')
resumo_aa = calcular_resumo_visao(df_filtrado, 'AA')

ocupacao_real = resumo_real['ocupacao']
ocupacao_aa = resumo_aa['ocupacao']
variacao_ocupacao_pp = (
    ocupacao_real - ocupacao_aa
    if ocupacao_real is not None and ocupacao_aa is not None
    else None
)
variacao_volume_total = (
    resumo_real['metro_carregado'] / resumo_aa['metro_carregado'] - 1
    if resumo_aa['metro_carregado'] > 0
    else None
)

st.subheader('Resumo executivo')
st.caption(
    'Comparacao do Real com a meta configurada e com o mesmo periodo da visao AA.'
)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    'Ocupacao Real',
    f'{ocupacao_real:.2%}' if ocupacao_real is not None else 'N/A',
    delta=(
        f'{ocupacao_real - meta_ocupacao:+.2%} vs. meta'
        if ocupacao_real is not None else None
    )
)
c2.metric('Meta configurada', f'{meta_ocupacao:.2%}')
c3.metric(
    'Ocupacao AA',
    f'{ocupacao_aa:.2%}' if ocupacao_aa is not None else 'N/A',
    delta=(
        f'{variacao_ocupacao_pp:+.2%} Real x AA'
        if variacao_ocupacao_pp is not None else None
    )
)
c4.metric(
    'm3 carregado Real',
    formatar_numero(resumo_real['metro_carregado']),
    delta=(
        f'{variacao_volume_total:+.1%} vs. AA'
        if variacao_volume_total is not None else None
    )
)

st.caption(
    f"{formatar_inteiro(resumo_real['registros'])} registros Real e "
    f"{formatar_inteiro(resumo_aa['registros'])} registros AA no filtro atual."
)

st.divider()
st.subheader('Volume e ocupacao por tipo de carregamento')
st.caption(
    'Mostra se Paletizado e Estivado cresceram ou cairam no Real em relacao ao AA.'
)

comparativo_tipo = preparar_comparativo_grupo(
    df_filtrado,
    'tipo_carregamento'
)

for tipo in ['Paletizado', 'Estivado']:
    linha = comparativo_tipo.loc[
        comparativo_tipo['tipo_carregamento'].eq(tipo)
    ]

    if linha.empty:
        st.info(f'Sem dados para {tipo} nos filtros atuais.')
        continue

    registro = linha.iloc[0]
    volume_real = registro['metro_carregado_real']
    volume_aa = registro['metro_carregado_aa']
    ocup_tipo_real = registro['ocupacao_real']
    var_volume = registro['variacao_volume_pct']
    var_ocup = registro['variacao_ocupacao_pp']

    st.markdown(f'### {tipo}')
    t1, t2, t3, t4 = st.columns(4)
    t1.metric('Volume Real', formatar_numero(volume_real))
    t2.metric(
        'Volume AA',
        formatar_numero(volume_aa) if pd.notna(volume_aa) else 'N/A'
    )
    t3.metric(
        'Variacao do volume',
        f'{var_volume:+.1%}' if pd.notna(var_volume) else 'N/A',
        delta=(
            f'{formatar_numero(volume_real - volume_aa)} m3'
            if pd.notna(volume_aa) else None
        )
    )
    t4.metric(
        'Ocupacao Real',
        f'{ocup_tipo_real:.2%}' if pd.notna(ocup_tipo_real) else 'N/A',
        delta=(
            f'{var_ocup:+.2%} vs. AA'
            if pd.notna(var_ocup) else None
        )
    )

st.divider()
st.subheader('Clientes prioritarios para atuacao')
st.caption(
    'As barras partem das extremidades e avancam em direcao ao centro. A barra '
    'cinza mostra o volume relativo ao maior cliente do ranking; a barra colorida '
    'mostra a ocupacao Real. Alto volume e baixa ocupacao deixam maior distancia '
    'entre as barras e indicam prioridade. A comparacao com AA fica no hover.'
)

quantidade_clientes = st.slider(
    'Quantidade de clientes:',
    min_value=5,
    max_value=30,
    value=15,
    step=5
)

figura_clientes = criar_grafico_clientes_gerencial(
    df_filtrado,
    meta_ocupacao,
    quantidade_clientes
)

if figura_clientes is None:
    st.warning('Nenhum cliente encontrado para os filtros atuais.')
else:
    st.plotly_chart(
        figura_clientes,
        width='stretch',
        key='clientes_gerencial'
    )

st.divider()
st.subheader('Ocupacao por estado e perfil de veiculo')
st.caption(
    'Cada celula mostra a ocupacao Real. Verde indica na meta ou acima; vermelho '
    'indica abaixo da meta. A seta mostra se o Real melhorou ou piorou contra AA.'
)

figura_uf_perfil = criar_heatmap_uf_perfil_gerencial(
    df_filtrado,
    meta_ocupacao
)

if figura_uf_perfil is None:
    st.warning('Sem dados de UF e perfil para os filtros atuais.')
else:
    st.plotly_chart(
        figura_uf_perfil,
        width='stretch',
        key='uf_perfil_gerencial'
    )

st.divider()
st.subheader('Maiores oportunidades para atingir a meta')
st.caption(
    'Ranking estimado de quantos m3 adicionais seriam necessarios para cada '
    'cliente atingir a meta configurada, considerando o m3 padrao do Real.'
)

figura_gap = criar_grafico_gap_meta(
    df_filtrado,
    meta_ocupacao,
    quantidade=10
)

if figura_gap is None:
    st.success('Nenhum cliente com gap positivo para a meta nos filtros atuais.')
else:
    st.plotly_chart(
        figura_gap,
        width='stretch',
        key='gap_meta_clientes'
    )

st.divider()
st.subheader('Base detalhada')
st.caption(
    'A base nao e exibida no painel. Use o download para investigacoes detalhadas.'
)

arquivo_csv = df_filtrado.to_csv(
    index=False,
    sep=';',
    decimal=','
).encode('utf-8-sig')

st.download_button(
    '📥 Baixar base detalhada filtrada',
    arquivo_csv,
    file_name='ocupacao_detalhada_filtrada.csv',
    mime='text/csv'
)
