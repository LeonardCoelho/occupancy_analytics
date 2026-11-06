"""Gráficos Plotly e formatadores do painel (padrão brasileiro)."""

import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta única do painel
COR_POSITIVO = '#2E9E5B'   # na meta / ajudou
COR_NEGATIVO = '#D64545'   # abaixo da meta / prejudicou
COR_ALERTA = '#E8893A'     # atenção (abaixo da meta, acima do mínimo)
COR_NEUTRO = '#8A95A5'     # volume, contexto
COR_PRINCIPAL = '#2F6DB5'  # Real
COR_AA = '#A9B6C8'         # ano anterior
COR_META = '#D4A017'       # meta

FONTE = {'family': 'Segoe UI, Arial, sans-serif', 'size': 13}


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def _br(texto):
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def fmt_num(valor, casas=0):
    if valor is None or pd.isna(valor):
        return '–'
    return _br(f'{valor:,.{casas}f}')


def fmt_pct(valor, casas=2):
    if valor is None or pd.isna(valor):
        return '–'
    return _br(f'{valor * 100:,.{casas}f}') + '%'


def fmt_pp(valor, casas=2, sinal=True):
    if valor is None or pd.isna(valor):
        return '–'
    prefixo = '+' if sinal and valor >= 0 else ''
    return prefixo + _br(f'{valor * 100:.{casas}f}') + ' p.p.'


def fmt_var(valor, casas=1):
    if valor is None or pd.isna(valor) or np.isinf(valor):
        return '–'
    return ('+' if valor >= 0 else '') + _br(f'{valor * 100:.{casas}f}') + '%'


def _fmt(series, formatador, **kwargs):
    return series.map(lambda v: formatador(v, **kwargs))


def _layout(figura, altura, **kwargs):
    base = dict(
        height=altura, font=FONTE, margin={'l': 10, 'r': 30, 't': 40, 'b': 30},
        separators=',.',  # decimal com virgula, milhar com ponto
        legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.02, 'x': 0, 'title': None},
        hoverlabel={'font_size': 13},
        uniformtext={'minsize': 10, 'mode': 'hide'},
    )
    base.update(kwargs)
    figura.update_layout(**base)
    return figura


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

def grafico_bridge(bridge):
    etapas = bridge['etapas']
    # Nomes em ate duas linhas, sem inclinar o eixo.
    quebras = {
        'Tipo de carregamento': 'Tipo de<br>carregamento', 'Fechamento do mês': 'Fechamento<br>do mês',
        'Cargas abaixo do mínimo': 'Cargas abaixo<br>do mínimo', 'Demais efeitos': 'Demais<br>efeitos',
        'Ocupação Real': 'Ocupação<br>Real',
    }
    nomes = [quebras.get(e[0], e[0]) for e in etapas]
    valores = [e[1] for e in etapas]
    medidas = [e[2] for e in etapas]
    textos = [fmt_pct(v) if m != 'relative' else fmt_pp(v) for _, v, m in etapas]

    acumulado, pontos = 0.0, []
    for valor, medida in zip(valores, medidas):
        acumulado = valor if medida in ('absolute', 'total') else acumulado + valor
        pontos.append(acumulado)

    figura = go.Figure(go.Waterfall(
        orientation='v', measure=medidas, x=nomes, y=valores, text=textos,
        textposition='outside', textfont={'size': 14},
        connector={'line': {'color': '#B8C0CC', 'width': 1}},
        increasing={'marker': {'color': COR_POSITIVO}},
        decreasing={'marker': {'color': COR_NEGATIVO}},
        totals={'marker': {'color': COR_PRINCIPAL}},
        hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>',
    ))
    amplitude = max(pontos) - min(pontos)
    minimo, maximo = min(pontos) - max(0.004, amplitude * 0.6), max(pontos) + max(0.003, amplitude * 0.25)
    return _layout(
        figura, 440, showlegend=False, waterfallgap=0.3,
        margin={'l': 10, 'r': 20, 't': 20, 'b': 10},
        xaxis={'tickangle': 0, 'tickfont': {'size': 13}},
        yaxis={'tickformat': '.1%', 'range': [max(0, minimo), min(1, maximo)], 'title': None},
    )


# ---------------------------------------------------------------------------
# Evolução mensal
# ---------------------------------------------------------------------------

def grafico_evolucao(evolucao):
    figura = go.Figure()
    figura.add_trace(go.Scatter(
        x=evolucao['mes_nome'], y=evolucao['ocupacao_aa'], name='Ano anterior',
        mode='lines+markers', line={'color': COR_AA, 'width': 2},
        hovertemplate='%{x}<br>AA: %{y:.2%}<extra></extra>',
    ))
    figura.add_trace(go.Scatter(
        x=evolucao['mes_nome'], y=evolucao['meta'], name='Meta',
        mode='lines', line={'color': COR_META, 'dash': 'dash', 'width': 2},
        hovertemplate='%{x}<br>Meta: %{y:.2%}<extra></extra>',
    ))
    figura.add_trace(go.Scatter(
        x=evolucao['mes_nome'], y=evolucao['ocupacao_real'], name='Real',
        mode='lines+markers+text', line={'color': COR_PRINCIPAL, 'width': 3}, marker={'size': 8},
        text=_fmt(evolucao['ocupacao_real'], fmt_pct, casas=1), textposition='top center', textfont={'size': 11},
        hovertemplate='%{x}<br>Real: %{y:.2%}<extra></extra>',
    ))
    return _layout(figura, 340, yaxis={'tickformat': '.0%', 'title': None}, hovermode='x unified')


# ---------------------------------------------------------------------------
# Clientes prioritários: volume à esquerda, ocupação à direita
# ---------------------------------------------------------------------------

def grafico_prioridades(dados, coluna, meta):
    dados = dados.iloc[::-1].reset_index(drop=True)
    maior = dados['metro_carregado_real'].max()
    volume_relativo = dados['metro_carregado_real'] / maior if maior > 0 else 0

    hover_volume = pd.DataFrame({
        'real': _fmt(dados['metro_carregado_real'], fmt_num),
        'aa': _fmt(dados['metro_carregado_aa'], fmt_num),
        'var': _fmt(dados['variacao_volume_pct'], fmt_var),
        'part': _fmt(dados['participacao_volume_real'], fmt_pct),
    })
    hover_ocup = pd.DataFrame({
        'real': _fmt(dados['ocupacao_real'], fmt_pct),
        'aa': _fmt(dados['ocupacao_aa'], fmt_pct),
        'var': _fmt(dados['variacao_ocupacao_pp'], fmt_pp),
        'impacto': _fmt(dados['impacto_meta_pp'], fmt_pp),
        'causa': dados['causa'] if 'causa' in dados else '',
    })

    figura = go.Figure()
    figura.add_trace(go.Bar(
        x=volume_relativo, base=[-1.0] * len(dados), y=dados[coluna], orientation='h',
        name='Volume Real', marker_color=COR_NEUTRO,
        text=dados['metro_carregado_real'].map(lambda v: f'{fmt_num(v)} m³'),
        textposition='inside', insidetextanchor='start', textfont={'color': '#FFFFFF', 'size': 12},
        customdata=hover_volume.to_numpy(),
        hovertemplate=(
            '<b>%{y}</b><br>Volume Real: %{customdata[0]} m³<br>Volume AA: %{customdata[1]} m³<br>'
            'Variação: <b>%{customdata[2]}</b><br>% do volume total: %{customdata[3]}<extra></extra>'
        ),
    ))
    cores = np.where(dados['ocupacao_real'] >= meta, COR_POSITIVO, COR_NEGATIVO)
    figura.add_trace(go.Bar(
        x=dados['ocupacao_real'], base=1.0 - dados['ocupacao_real'], y=dados[coluna], orientation='h',
        name='Ocupação Real', marker_color=cores,
        text=_fmt(dados['ocupacao_real'], fmt_pct, casas=1),
        textposition='inside', insidetextanchor='start', textfont={'color': '#FFFFFF', 'size': 12},
        customdata=hover_ocup.to_numpy(),
        hovertemplate=(
            '<b>%{y}</b><br>Ocupação Real: %{customdata[0]}<br>Ocupação AA: %{customdata[1]}<br>'
            'Variação: <b>%{customdata[2]}</b><br>Impacto na meta: <b>%{customdata[3]}</b><br>'
            'Causa principal: %{customdata[4]}<extra></extra>'
        ),
    ))
    figura.add_vline(
        x=1.0 - meta, line_dash='dash', line_color=COR_META, line_width=2,
        annotation_text=f'Meta {fmt_pct(meta, 1)}', annotation_position='top right',
        annotation_font_color=COR_META,
    )
    figura.add_vline(x=0, line_color='rgba(128,128,128,0.35)', line_width=1)
    return _layout(
        figura, max(460, len(dados) * 34), barmode='overlay', bargap=0.25, showlegend=False,
        xaxis={'range': [-1.02, 1.02], 'showticklabels': False, 'showgrid': False, 'zeroline': False,
               'title': {'text': '◀ Volume Real          Ocupação Real ▶', 'font': {'size': 12}}},
        yaxis={'title': None, 'automargin': True},
    )


# ---------------------------------------------------------------------------
# Barras horizontais de pontos perdidos (ranking)
# ---------------------------------------------------------------------------

def grafico_pontos(dados, coluna, valor, titulo_valor, extra_hover=None):
    dados = dados.iloc[::-1].reset_index(drop=True)
    cores = np.where(dados[valor] >= 0, COR_POSITIVO, COR_NEGATIVO)
    hover = '<b>%{y}</b><br>' + titulo_valor + ': %{text}'
    customdata = None
    if extra_hover:
        customdata = pd.DataFrame({rotulo: serie for rotulo, serie in extra_hover.items()}).to_numpy()
        hover += ''.join(f'<br>{rotulo}: %{{customdata[{i}]}}' for i, rotulo in enumerate(extra_hover))
    figura = go.Figure(go.Bar(
        x=dados[valor], y=dados[coluna], orientation='h', marker_color=cores,
        text=_fmt(dados[valor], fmt_pp), textposition='outside', cliponaxis=False,
        customdata=customdata, hovertemplate=hover + '<extra></extra>',
    ))
    menor, maior = min(dados[valor].min(), 0), max(dados[valor].max(), 0)
    folga = (maior - menor) * 0.35 or 0.001
    return _layout(
        figura, max(320, len(dados) * 30), showlegend=False, margin={'l': 10, 'r': 20, 't': 20, 'b': 30},
        xaxis={'tickformat': '.2%', 'title': None, 'zeroline': True,
               'range': [menor - (folga if menor < 0 else 0), maior + (folga if maior > 0 else folga * 0.1)]},
        yaxis={'title': None, 'automargin': True},
    )


# ---------------------------------------------------------------------------
# Restrições operacionais
# ---------------------------------------------------------------------------

def grafico_restricoes(tabela, meta):
    tabela = tabela.iloc[::-1]
    figura = go.Figure()
    figura.add_trace(go.Bar(
        y=tabela['restricao'], x=tabela['ocupacao_sem'], orientation='h', name='Sem a restrição',
        marker_color=COR_AA, text=_fmt(tabela['ocupacao_sem'], fmt_pct, casas=1), textposition='outside',
        hovertemplate='<b>%{y}</b><br>Sem a restrição: %{x:.1%}<extra></extra>',
    ))
    figura.add_trace(go.Bar(
        y=tabela['restricao'], x=tabela['ocupacao_com'], orientation='h', name='Com a restrição',
        marker_color=np.where(tabela['ocupacao_com'] >= meta, COR_POSITIVO, COR_NEGATIVO),
        text=_fmt(tabela['ocupacao_com'], fmt_pct, casas=1), textposition='outside',
        customdata=np.column_stack([_fmt(tabela['participacao_volume'], fmt_pct, casas=0), tabela['clientes']]),
        hovertemplate='<b>%{y}</b><br>Com a restrição: %{x:.1%}<br>%{customdata[0]} do volume'
                      '<br>%{customdata[1]} clientes<extra></extra>',
    ))
    figura.add_vline(x=meta, line_dash='dash', line_color=COR_META, line_width=2)
    return _layout(
        figura, max(300, len(tabela) * 80), barmode='group', bargap=0.3, margin={'l': 10, 'r': 20, 't': 50, 'b': 20},
        xaxis={'tickformat': '.0%', 'range': [0, 1.02], 'title': f'Linha amarela: meta {fmt_pct(meta, 1)}'},
        yaxis={'title': None, 'automargin': True},
    )


# ---------------------------------------------------------------------------
# Ocupação dia a dia
# ---------------------------------------------------------------------------

def grafico_ocupacao_dia(dia_real, dia_aa, meta, corte):
    figura = go.Figure()
    figura.add_trace(go.Bar(
        x=dia_real['dia'], y=dia_real['ocupacao_dia'], name='Ocupação do dia (Real)',
        marker_color=np.where(dia_real['dia'] > corte, COR_ALERTA, COR_AA), opacity=0.85,
        hovertemplate='Dia %{x}<br>Ocupação do dia: %{y:.1%}<extra></extra>',
    ))
    figura.add_trace(go.Scatter(
        x=dia_aa['dia'], y=dia_aa['ocupacao_acumulada'], name='Acumulada no mês (AA)',
        mode='lines', line={'color': COR_NEUTRO, 'width': 2, 'dash': 'dot'},
        hovertemplate='Dia %{x}<br>Acumulada AA: %{y:.2%}<extra></extra>',
    ))
    figura.add_trace(go.Scatter(
        x=dia_real['dia'], y=dia_real['ocupacao_acumulada'], name='Acumulada no mês (Real)',
        mode='lines', line={'color': COR_PRINCIPAL, 'width': 3.5},
        hovertemplate='Dia %{x}<br>Acumulada Real: %{y:.2%}<extra></extra>',
    ))
    figura.add_hline(y=meta, line_dash='dash', line_color=COR_META, line_width=1.5,
                     annotation_text=f'Meta {fmt_pct(meta, 1)}', annotation_position='bottom right',
                     annotation_font_color=COR_META)
    figura.add_vrect(x0=corte + 0.5, x1=31.5, fillcolor=COR_ALERTA, opacity=0.08, line_width=0,
                     annotation_text='Fechamento', annotation_position='top right')

    validos = dia_real.dropna(subset=['ocupacao_acumulada'])
    no_corte = validos.loc[validos['dia'] <= corte].tail(1)
    final = validos.tail(1)
    for ponto, rotulo, posicao in ((no_corte, f'Até dia {corte}', 'top'), (final, 'Fechou em', 'bottom')):
        if not ponto.empty:
            figura.add_annotation(
                x=ponto['dia'].iloc[0], y=ponto['ocupacao_acumulada'].iloc[0],
                text=f"<b>{rotulo}: {fmt_pct(ponto['ocupacao_acumulada'].iloc[0])}</b>",
                showarrow=True, arrowhead=2, ax=0, ay=-45 if posicao == 'top' else 45,
                bgcolor='rgba(255,255,255,0.85)', font={'color': COR_PRINCIPAL},
            )
    valores = pd.concat([dia_real['ocupacao_acumulada'], dia_aa['ocupacao_acumulada']]).dropna()
    minimo = min(valores.min() if not valores.empty else meta, meta) - 0.12
    return _layout(
        figura, 420, bargap=0.15,
        xaxis={'dtick': 1, 'title': 'Dia do mês', 'range': [0.5, 31.5]},
        yaxis={'tickformat': '.0%', 'title': None, 'range': [max(0, minimo), 1]},
    )


# ---------------------------------------------------------------------------
# Paletizado × Estivado
# ---------------------------------------------------------------------------

def grafico_tipo(detalhe):
    figura = go.Figure()
    for visao, cor, nome in (('aa', COR_AA, 'Ano anterior'), ('real', COR_PRINCIPAL, 'Real')):
        figura.add_trace(go.Bar(
            x=detalhe['tipo_carregamento'], y=detalhe[f'representatividade_{visao}'], name=f'% do volume – {nome}',
            marker_color=cor, text=_fmt(detalhe[f'representatividade_{visao}'], fmt_pct, casas=1),
            textposition='outside', hovertemplate='%{x}<br>' + nome + ': %{y:.1%} do volume<extra></extra>',
        ))
    representatividade = _layout(figura, 320, barmode='group', yaxis={'tickformat': '.0%', 'title': None, 'range': [0, 1.05]})

    figura = go.Figure()
    for visao, cor, nome in (('aa', COR_AA, 'Ano anterior'), ('real', COR_PRINCIPAL, 'Real')):
        figura.add_trace(go.Bar(
            x=detalhe['tipo_carregamento'], y=detalhe[f'ocupacao_{visao}'], name=f'Ocupação – {nome}',
            marker_color=cor, text=_fmt(detalhe[f'ocupacao_{visao}'], fmt_pct, casas=1),
            textposition='outside', hovertemplate='%{x}<br>' + nome + ': %{y:.1%}<extra></extra>',
        ))
    ocupacao = _layout(figura, 320, barmode='group', yaxis={'tickformat': '.0%', 'title': None, 'range': [0, 1.05]})
    return representatividade, ocupacao


def grafico_mudanca_tipo(dados, coluna):
    """% paletizado do cliente: ano anterior (cinza) -> Real (cor), um por linha."""
    dados = dados.iloc[::-1].reset_index(drop=True)
    cor = np.where(dados['perc_paletizado_real'] > dados['perc_paletizado_aa'], COR_NEGATIVO, COR_POSITIVO)
    figura = go.Figure()
    for i, linha in dados.iterrows():
        figura.add_trace(go.Scatter(
            x=[linha['perc_paletizado_aa'], linha['perc_paletizado_real']], y=[linha[coluna]] * 2,
            mode='lines', line={'color': cor[i], 'width': 4}, hoverinfo='skip', showlegend=False,
        ))
    figura.add_trace(go.Scatter(
        x=dados['perc_paletizado_aa'], y=dados[coluna], mode='markers', name='Ano anterior',
        marker={'color': COR_AA, 'size': 13, 'line': {'color': '#FFFFFF', 'width': 1}},
        hovertemplate='<b>%{y}</b><br>Ano anterior: %{x:.0%} paletizado<extra></extra>',
    ))
    figura.add_trace(go.Scatter(
        x=dados['perc_paletizado_real'], y=dados[coluna], mode='markers+text', name='Real',
        marker={'color': cor, 'size': 13, 'line': {'color': '#FFFFFF', 'width': 1}},
        text=_fmt(dados['perc_paletizado_real'], fmt_pct, casas=0),
        textposition=['middle right' if r > a else 'middle left'
                      for r, a in zip(dados['perc_paletizado_real'], dados['perc_paletizado_aa'])],
        hovertemplate='<b>%{y}</b><br>Real: %{x:.0%} paletizado<extra></extra>',
    ))
    return _layout(
        figura, max(320, len(dados) * 32), margin={'l': 10, 'r': 40, 't': 40, 'b': 30},
        xaxis={'tickformat': '.0%', 'range': [-0.08, 1.12], 'title': '% do volume do cliente que é paletizado'},
        yaxis={'title': None, 'automargin': True},
    )


# ---------------------------------------------------------------------------
# Mapa e heatmap
# ---------------------------------------------------------------------------

COORDENADAS_UF = {
    'AC': (-9.02, -70.81), 'AL': (-9.70, -34.80), 'AP': (1.41, -51.77), 'AM': (-3.47, -65.10),
    'BA': (-12.96, -41.70), 'CE': (-5.20, -39.53), 'DF': (-15.75, -46.80), 'ES': (-19.20, -38.80),
    'GO': (-15.98, -49.86), 'MA': (-5.42, -45.44), 'MT': (-12.64, -55.42), 'MS': (-20.51, -54.54),
    'MG': (-18.10, -44.38), 'PA': (-3.79, -52.48), 'PB': (-7.10, -34.50), 'PR': (-24.89, -51.55),
    'PE': (-8.15, -34.90), 'PI': (-6.60, -42.28), 'RJ': (-22.40, -40.50), 'RN': (-5.70, -34.60),
    'RS': (-30.17, -53.50), 'RO': (-10.83, -63.34), 'RR': (2.73, -61.33), 'SC': (-27.45, -50.95),
    'SP': (-22.19, -48.79), 'SE': (-10.80, -35.30), 'TO': (-10.25, -48.25),
}

# Estados pequenos demais para mostrar rotulo sem encavalar (aparecem no passar do mouse).
UFS_PEQUENAS = {'DF', 'SE', 'AL', 'PB', 'RN', 'PE', 'ES', 'RJ'}

_CODIGO_UF = {
    '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO',
    '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL',
    '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP', '41': 'PR',
    '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF',
}


def carregar_geojson(caminho):
    with open(caminho, encoding='utf-8') as arquivo:
        geojson = json.load(arquivo)
    candidatos = ['sigla', 'SIGLA', 'uf', 'UF', 'abbrev_state', 'SIGLA_UF', 'CD_UF', 'codigo_ibge', 'id']
    for feature in geojson.get('features', []):
        prop = feature.get('properties', {})
        valor = next((prop.get(c) for c in candidatos if prop.get(c) is not None), feature.get('id'))
        texto = str(valor).upper().strip()
        uf = texto if len(texto) == 2 and texto.isalpha() else _CODIGO_UF.get(texto)
        if uf:
            feature['id'] = uf
    return geojson


def grafico_mapa(dados_uf, geojson, meta, uf_ativa=None):
    dados = dados_uf.loc[dados_uf['ocupacao_real'].notna()].copy()
    dados['ocupacao_pct'] = dados['ocupacao_real'] * 100
    dados['hover'] = (
        '<b>' + dados['uf'] + '</b><br>Ocupação Real: ' + _fmt(dados['ocupacao_real'], fmt_pct)
        + '<br>Ocupação AA: ' + _fmt(dados['ocupacao_aa'], fmt_pct)
        + '<br>Variação: ' + _fmt(dados['variacao_ocupacao_pp'], fmt_pp)
        + '<br>Volume Real: ' + _fmt(dados['metro_carregado_real'], fmt_num) + ' m³'
        + '<br>Impacto na meta: ' + _fmt(dados['impacto_meta_pp'], fmt_pp)
    )
    corte = float(np.clip(meta, 0, 1))
    escala = [[0.0, COR_NEGATIVO], [corte, COR_NEGATIVO], [corte, COR_POSITIVO], [1.0, COR_POSITIVO]]
    figura = px.choropleth(
        dados, geojson=geojson, locations='uf', featureidkey='id', color='ocupacao_pct',
        custom_data=['uf', 'hover'], color_continuous_scale=escala, range_color=[0, 100],
    )
    figura.update_traces(
        hovertemplate='%{customdata[1]}<extra></extra>', marker_line_color='#FFFFFF',
        marker_line_width=1, selector={'type': 'choropleth'},
        selected={'marker': {'opacity': 1.0}}, unselected={'marker': {'opacity': 0.4}},
    )
    if uf_ativa:
        opacidade = np.where(dados['uf'].eq(uf_ativa), 1.0, 0.35)
        figura.update_traces(marker_opacity=opacidade, selector={'type': 'choropleth'})
    rotulados = dados.loc[~dados['uf'].isin(UFS_PEQUENAS)].copy()
    dados = rotulados
    dados['lat'] = dados['uf'].map(lambda u: COORDENADAS_UF.get(u, (None, None))[0])
    dados['lon'] = dados['uf'].map(lambda u: COORDENADAS_UF.get(u, (None, None))[1])
    figura.add_trace(go.Scattergeo(
        lat=dados['lat'], lon=dados['lon'], mode='text',
        text=dados['uf'] + '<br>' + dados['ocupacao_pct'].round(0).astype(int).astype(str) + '%',
        textfont={'size': 10, 'color': '#FFFFFF', 'family': 'Segoe UI Semibold, Arial Black'},
        hoverinfo='skip', showlegend=False,
    ))
    figura.update_geos(fitbounds='locations', visible=False, bgcolor='rgba(0,0,0,0)', projection_type='mercator')
    return _layout(
        figura, 540, margin={'l': 0, 'r': 0, 't': 0, 'b': 0}, clickmode='event+select',
        paper_bgcolor='rgba(0,0,0,0)', geo={'bgcolor': 'rgba(0,0,0,0)'},
        coloraxis_showscale=False,
    )


def exibir(figura, **kwargs):
    """Mostra o grafico no Streamlit sem a barra de ferramentas do Plotly."""
    import streamlit as st
    return st.plotly_chart(figura, config={'displayModeBar': False, 'responsive': True}, **kwargs)
