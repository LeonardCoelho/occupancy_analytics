import streamlit as st

import calculos as calc
import graficos as gr
from graficos import fmt_num, fmt_pct, fmt_pp, fmt_var

ctx = st.session_state['ctx']
df, cargas, meta = ctx['df'], ctx['cargas'], ctx['meta']
real, aa = ctx['total_real'], ctx['total_aa']
uf_ativa = st.session_state.get('uf_mapa')


@st.cache_data(max_entries=2)
def geojson_brasil(caminho):
    return gr.carregar_geojson(caminho)


# --- Indicadores ------------------------------------------------------------------
with st.container(horizontal=True):
    st.metric('Ocupação Real', fmt_pct(real['ocupacao']), f'{fmt_pp(real["ocupacao"] - meta)} vs. meta', border=True)
    st.metric('Meta', fmt_pct(meta), 'AA + 0,50 p.p.' if ctx['meta_automatica'] else 'manual',
              delta_color='off', border=True)
    st.metric('Ano anterior (AA)', fmt_pct(aa['ocupacao']),
              f'{fmt_pp(real["ocupacao"] - aa["ocupacao"])} Real × AA', border=True)
    st.metric(
        'Volume Real', f"{fmt_num(real['metro_carregado'])} m³",
        f'{fmt_var(real["metro_carregado"] / aa["metro_carregado"] - 1 if aa["metro_carregado"] else None)} vs. AA',
        delta_color='off', border=True,
    )

# --- Mapa -------------------------------------------------------------------------
col_mapa, col_estados = st.columns([5, 3], gap='large')
por_uf = calc.comparativo_grupo(ctx['df_mapa'], 'uf', meta)
with col_mapa:
    with st.container(border=True):
        st.markdown('##### :material/map: Clique no estado para analisar só ele')
        arquivo_geojson = ctx['arquivos']['geojson']
        if not arquivo_geojson.exists():
            st.warning(f'Arquivo do mapa não encontrado: {arquivo_geojson}')
        else:
            evento = gr.exibir(
                gr.grafico_mapa(por_uf, geojson_brasil(str(arquivo_geojson)), meta, uf_ativa),
                on_select='rerun', selection_mode='points',
                key=f'mapa_{st.session_state.get("mapa_versao", 0)}',
            )
            pontos = (evento or {}).get('selection', {}).get('points', [])
            if pontos:
                dados_ponto = pontos[0].get('customdata') or []
                uf = str(dados_ponto[0] if dados_ponto else pontos[0].get('location', '')).upper().strip()
                if uf and uf != uf_ativa:
                    st.session_state['uf_mapa'] = uf
                    st.rerun()
        if uf_ativa and st.button('Ver Brasil inteiro', icon=':material/public:'):
            st.session_state['uf_mapa'] = None
            st.session_state['mapa_versao'] = st.session_state.get('mapa_versao', 0) + 1
            st.rerun()
with col_estados:
    with st.container(border=True):
        st.markdown('##### :material/location_on: Estados que mais tiram da meta')
        brasil_real = calc.totais_visao(ctx['df_mapa'], 'Real')
        meta_brasil = calc.calcular_meta(calc.totais_visao(ctx['df_mapa'], 'AA')['ocupacao'], ctx['meta_automatica'], meta)
        por_uf['impacto_estado'] = calc.impacto_meta_somavel(por_uf, ctx['meta_automatica'])
        piores = por_uf.loc[(por_uf['metro_carregado_real'] > 0) & (por_uf['impacto_estado'] < 0)].nsmallest(8, 'impacto_estado')
        if piores.empty:
            st.success('Nenhum estado tirou da meta.')
        else:
            gr.exibir(
                gr.grafico_pontos(
                    piores, 'uf', 'impacto_estado', 'Impacto na meta',
                    extra_hover={'Ocupação Real': gr._fmt(piores['ocupacao_real'], fmt_pct),
                                 'Ocupação AA': gr._fmt(piores['ocupacao_aa'], fmt_pct),
                                 'Volume vs. AA': gr._fmt(piores['variacao_volume_pct'], gr.fmt_var)},
                ),
                key='estados_piores',
            )
        st.markdown(
            f"**Somando todos os estados: {fmt_pp(por_uf['impacto_estado'].sum())}** — "
            f"a distância do Brasil para a meta ({fmt_pct(brasil_real['ocupacao'])} × {fmt_pct(meta_brasil)})."
        )
        st.caption('Cada estado é comparado com o próprio ano anterior e responde pela sua parte dos 0,50 p.p. da meta.')

# --- Bridge -----------------------------------------------------------------------
corte = calc.DIA_CORTE_FECHAMENTO
tipo = calc.analise_tipo_carregamento(df)
nan = float('nan')
crit_ate, fech_real, fech_aa = nan, {'impacto_pp': nan}, {'impacto_pp': nan}
if not cargas.empty:
    crit_ate = calc.criticas_por_periodo(cargas, 'Real')['ate_pp']
    fech_real = calc.analise_fechamento(cargas, 'Real', real['metro_padrao'])
    fech_aa = calc.analise_fechamento(cargas, 'AA', aa['metro_padrao'])
bridge = calc.calcular_bridge(aa['ocupacao'], real['ocupacao'], meta, tipo['efeito_pp'], crit_ate, fech_real['impacto_pp'])
with st.container(border=True):
    distancia = bridge['gap_meta_pp']
    st.markdown(
        f"##### :material/trending_down: Por que estamos {fmt_pp(abs(distancia), 2, False)} "
        f"{'abaixo' if distancia < 0 else 'acima'} da meta"
    )
    st.caption('Da meta até o Real. Cada barra mostra quanto a ocupação seria maior se aquele problema não tivesse acontecido.')
    gr.exibir(gr.grafico_bridge(bridge), key='bridge')
    ajudaram = [nome.lower() for nome, valor in bridge['efeitos'].items() if valor >= 0]
    with st.expander('O que significa cada barra'):
        st.markdown(
            f"""
- **Tipo de carregamento**: quanto teríamos a mais se a proporção de paletizado e estivado fosse a do ano anterior
  (carga paletizada ocupa menos).
- **Fechamento do mês**: quanto teríamos a mais se as cargas do dia {corte + 1} em diante tivessem saído tão cheias
  quanto as de antes do dia {corte}. São as decisões para faturar: veículo maior, envio urgente, carga incompleta.
  Para comparar: no ano anterior o fechamento {'ajudou' if fech_aa['impacto_pp'] >= 0 else 'atrapalhou'}
  ({fmt_pp(fech_aa['impacto_pp'])}).
- **Cargas abaixo do mínimo**: quanto teríamos a mais se as cargas do dia 1 ao {corte} que saíram abaixo do mínimo
  do veículo tivessem saído pelo menos no mínimo (as de depois do dia {corte} já estão no fechamento).
- **Demais efeitos**: o que sobra para a conta fechar — clientes carregando pior que antes, mudança de clientes
  e a melhoria de 0,50 p.p. que a meta pede. Para ver quais clientes, use a página **Clientes**.
"""
            + (f"\nNão aparecem por não terem afastado da meta neste recorte: {', '.join(ajudaram)}." if ajudaram else '')
        )

# --- Evolução mensal ---------------------------------------------------------------
with st.container(border=True):
    st.markdown('##### :material/show_chart: Evolução mensal')
    gr.exibir(gr.grafico_evolucao(calc.evolucao_mensal(ctx['df_sem_periodo'])), key='evolucao')

st.page_link('app_pages/clientes.py', label='Próximo passo: quais clientes atacar', icon=':material/arrow_forward:')
