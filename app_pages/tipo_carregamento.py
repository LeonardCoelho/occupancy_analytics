import streamlit as st

import calculos as calc
import graficos as gr
from graficos import fmt_pct, fmt_pp

ctx = st.session_state['ctx']
df, meta = ctx['df'], ctx['meta']

analise = calc.analise_tipo_carregamento(df)
detalhe = analise['detalhe']
por_tipo = detalhe.set_index('tipo_carregamento')

with st.container(horizontal=True):
    st.metric(
        'Efeito na ocupação total', fmt_pp(analise['efeito_pp']),
        'a mudança ajudou' if analise['efeito_pp'] >= 0 else 'a mudança prejudicou',
        delta_color='normal' if analise['efeito_pp'] >= 0 else 'inverse', border=True,
        help='Quanto a ocupação total mudou só porque a proporção entre Paletizado e Estivado mudou contra o AA.',
    )
    for tipo in calc.TIPOS_CARREGAMENTO:
        if tipo in por_tipo.index:
            st.metric(f'Ocupação {tipo.lower()}', fmt_pct(por_tipo.loc[tipo, 'ocupacao_real'], 1),
                      f"{fmt_pp(por_tipo.loc[tipo, 'variacao_ocupacao_pp'])} vs. AA", border=True)

grafico_repr, grafico_ocup = gr.grafico_tipo(detalhe)
col_a, col_b = st.columns(2, gap='medium')
with col_a.container(border=True):
    st.markdown('##### :material/pie_chart: Quanto do volume é paletizado e estivado')
    gr.exibir(grafico_repr, key='tipo_repr')
with col_b.container(border=True):
    st.markdown('##### :material/bar_chart: Ocupação de cada tipo')
    gr.exibir(grafico_ocup, key='tipo_ocup')
if {'Paletizado', 'Estivado'} <= set(por_tipo.index):
    st.caption(
        f"A carga paletizada ocupa {fmt_pct(por_tipo.loc['Paletizado', 'ocupacao_real'], 1)} e a estivada "
        f"{fmt_pct(por_tipo.loc['Estivado', 'ocupacao_real'], 1)}: quanto mais paletizado no total, menor a ocupação."
    )

# --- Clientes que mudaram o tipo ---------------------------------------------------------
por_cliente = calc.tipo_carregamento_por_cliente(df, 'cliente_pai', meta)
mudaram = por_cliente.loc[
    por_cliente['perc_paletizado_aa'].notna() & por_cliente['perc_paletizado_real'].notna()
    & por_cliente['variacao_paletizado_pp'].abs().ge(0.05)
].copy()

with st.container(border=True):
    st.markdown('##### :material/swap_horiz: Clientes que mudaram o tipo de carregamento')
    st.caption(
        'Clientes que existem nos dois anos e mudaram pelo menos 5 p.p. no % paletizado, ordenados por volume. '
        'Ponto cinza: ano anterior. Ponto colorido: Real.'
    )
    mais_pal = mudaram.loc[mudaram['variacao_paletizado_pp'] > 0].nlargest(15, 'metro_carregado_real')
    mais_est = mudaram.loc[mudaram['variacao_paletizado_pp'] < 0].nlargest(15, 'metro_carregado_real')
    colunas = {
        'cliente_pai': st.column_config.TextColumn('Cliente', width='medium'),
        'perc_paletizado_aa': st.column_config.ProgressColumn('% paletizado AA', format='percent', min_value=0, max_value=1),
        'perc_paletizado_real': st.column_config.ProgressColumn('% paletizado Real', format='percent', min_value=0, max_value=1),
        'variacao_paletizado_pp': st.column_config.NumberColumn('Variação', format='percent'),
        'metro_carregado_real': st.column_config.NumberColumn('Volume (m³)', format='localized'),
        'ocupacao_real': st.column_config.NumberColumn('Ocupação Real', format='percent'),
    }
    aba_pal, aba_est = st.tabs([
        f':red[:material/arrow_upward:] Passaram a paletizar mais ({len(mudaram.loc[mudaram["variacao_paletizado_pp"] > 0])})',
        f':green[:material/arrow_downward:] Passaram a estivar mais ({len(mudaram.loc[mudaram["variacao_paletizado_pp"] < 0])})',
    ])
    for aba, tabela, chave in ((aba_pal, mais_pal, 'pal'), (aba_est, mais_est, 'est')):
        with aba:
            if tabela.empty:
                st.info('Nenhum cliente neste grupo.')
                continue
            gr.exibir(gr.grafico_mudanca_tipo(tabela, 'cliente_pai'), key=f'mudanca_{chave}')
            with st.expander('Ver tabela'):
                st.dataframe(tabela[list(colunas)], hide_index=True, column_config=colunas)
