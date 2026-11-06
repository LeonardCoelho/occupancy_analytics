import pandas as pd
import streamlit as st

import calculos as calc
import graficos as gr
from graficos import fmt_num, fmt_pct, fmt_pp

ctx = st.session_state['ctx']
df, cargas, meta = ctx['df'], ctx['cargas'], ctx['meta']
real = ctx['total_real']
uf_ativa = st.session_state.get('uf_mapa')

restricoes = calc.restricoes_por_codigo(ctx['particularidades'])
diagnostico = calc.diagnostico_clientes(df, cargas, meta)
diagnostico = diagnostico.merge(
    calc.restricoes_dos_clientes(df, restricoes)[['cliente_pai', 'restricoes']], on='cliente_pai', how='left',
)
diagnostico['restricoes'] = diagnostico['restricoes'].fillna('')
abaixo = diagnostico.loc[diagnostico['impacto_meta_pp'] < 0].sort_values('impacto_meta_pp')

if not abaixo.empty:
    parcela_top10 = abaixo.head(10)['impacto_meta_pp'].sum() / abaixo['impacto_meta_pp'].sum()
    st.markdown(
        f"**{len(abaixo)} de {len(diagnostico)} clientes** estão abaixo da meta{' em ' + uf_ativa if uf_ativa else ''}. "
        f"Os **10 piores explicam {fmt_pct(parcela_top10, 0)}** da perda — comece por eles."
    )

# --- Clientes prioritários ----------------------------------------------------------
with st.container(border=True):
    cab, ctrl = st.columns([2, 3], vertical_alignment='bottom')
    cab.markdown('##### :material/leaderboard: Clientes prioritários: volume × ocupação')
    with ctrl.container(horizontal=True, horizontal_alignment='right', vertical_alignment='bottom'):
        ordem = st.segmented_control(
            'Ordenar por', ['Maior volume', 'Mais tira da meta'], default='Maior volume', key='cli_ordem',
            label_visibility='collapsed',
        ) or 'Maior volume'
        quantidade = st.select_slider('Quantidade', [10, 15, 20, 30], value=10, key='cli_qtd', label_visibility='collapsed')
    lista = diagnostico.sort_values('metro_carregado_real', ascending=False) if ordem == 'Maior volume' else abaixo
    lista = lista.head(quantidade).reset_index(drop=True)
    if lista.empty:
        st.success('Nenhum cliente abaixo da meta neste recorte.')
        st.stop()
    gr.exibir(gr.grafico_prioridades(lista, 'cliente_pai', meta), key='cli_prioridades')
    st.caption(
        '**Impacto na meta** = quantos pontos de ocupação o cliente tirou (−) ou somou (+) do resultado total '
        'em relação à meta. Considera o volume e a ocupação dele juntos.'
    )

# --- Restrições ---------------------------------------------------------------------
with st.container(border=True):
    st.markdown('##### :material/rule: Restrições dos clientes que derrubam a ocupação')
    # So cargas paletizadas: o estivado ocupa mais por natureza e distorceria a comparacao.
    paletizado = df.loc[df['tipo_carregamento'].eq('Paletizado')]
    tabela_restricoes = calc.ocupacao_por_restricao(paletizado, restricoes, meta)
    tabela_restricoes = tabela_restricoes.loc[tabela_restricoes['participacao_volume'].ge(0.03)]
    if tabela_restricoes.empty:
        st.caption('Sem dados de restrições para cargas paletizadas neste recorte.')
    else:
        gr.exibir(gr.grafico_restricoes(tabela_restricoes, meta), key='cli_restricoes')
        pior = tabela_restricoes.iloc[0]
        st.caption(
            'Comparação só entre cargas **paletizadas**, para não misturar com o estivado (que ocupa mais por natureza). '
            f"Ex.: clientes com a restrição **{pior['restricao'].lower()}** ocupam {fmt_pct(pior['ocupacao_com'], 1)}, "
            f"contra {fmt_pct(pior['ocupacao_sem'], 1)} dos demais. Fonte: planilha de particularidades."
        )

# --- Tabela clicável ------------------------------------------------------------------
st.markdown('#### Escolha um cliente para ver o motivo e as cargas')
tabela = lista[['cliente_pai', 'metro_carregado_real', 'ocupacao_real', 'ocupacao_aa', 'impacto_meta_pp', 'causa', 'restricoes']]
selecao = st.dataframe(
    tabela, hide_index=True, on_select='rerun', selection_mode='single-row', key='cli_tabela',
    column_config={
        'cliente_pai': st.column_config.TextColumn('Cliente', width='medium'),
        'metro_carregado_real': st.column_config.NumberColumn('Volume (m³)', format='localized'),
        'ocupacao_real': st.column_config.ProgressColumn('Ocupação', format='percent', min_value=0, max_value=1),
        'ocupacao_aa': st.column_config.NumberColumn('Ocupação AA', format='percent'),
        'impacto_meta_pp': st.column_config.NumberColumn('Impacto na meta', format='percent'),
        'causa': 'Causa principal',
        'restricoes': st.column_config.TextColumn('Restrições', width='large'),
    },
)
linhas = selecao.selection.rows if selecao else []
cliente = tabela.loc[linhas[0] if linhas else 0, 'cliente_pai']
linha = diagnostico.loc[diagnostico['cliente_pai'].eq(cliente)].iloc[0]

# --- Detalhe do cliente ----------------------------------------------------------------
st.divider()
st.subheader(cliente)
with st.container(horizontal=True):
    st.metric('Ocupação', fmt_pct(linha['ocupacao_real']), f"{fmt_pp(linha['variacao_ocupacao_pp'])} vs. AA", border=True)
    st.metric('Volume', f"{fmt_num(linha['metro_carregado_real'])} m³",
              f"{fmt_pct(linha['participacao_volume_real'])} do total", delta_color='off', border=True)
    st.metric('Impacto na meta', fmt_pp(linha['impacto_meta_pp']), border=True)
    st.metric('OCs abaixo do mínimo', f"{int(linha['ocs_criticas'])} de {int(linha['ocs'])}", border=True)

col_porque, col_restr = st.columns([3, 2], gap='medium')
with col_porque.container(border=True, height='stretch'):
    if linha['causa_chave'] == 'acima':
        st.markdown(':green[**Cliente na meta ou acima.**] Manter o padrão de carregamento.')
    else:
        motivos = []
        diferenca = linha['ocupacao_real'] - linha['ocupacao_referencia']
        if linha['perfil'] < 0:
            motivos.append(
                f"- Outros clientes com o **mesmo tipo de carregamento e veículo** ocupam {fmt_pct(linha['ocupacao_referencia'], 1)} "
                f"— abaixo da meta ({fmt_pct(meta, 1)}): o perfil de carga já é difícil."
            )
        if diferenca < -0.005:
            motivos.append(f"- Ele carrega **{fmt_pp(abs(diferenca), 1, False)} abaixo** desses clientes comparáveis.")
        if linha['ocs_criticas'] > 0:
            motivos.append(f"- **{int(linha['ocs_criticas'])} OCs** saíram abaixo do mínimo do veículo.")
        if linha['fechamento'] < -0.0001:
            motivos.append(f"- As cargas depois do dia {calc.DIA_CORTE_FECHAMENTO} saem mais vazias que no início do mês.")
        if str(linha['classificacao_tipo']).startswith('Troca integral'):
            motivos.append(f"- {linha['classificacao_tipo']} em relação ao ano anterior.")
        st.markdown(f"**Por que** · :red[{linha['causa']}]")
        st.markdown('\n'.join(motivos) if motivos else '- Ocupação abaixo da meta.')
        st.markdown(f"**O que fazer:** {linha['acao']}")

# Códigos-filhos
base_pai = df.loc[df['cliente_pai'].eq(cliente)]
filhos = calc.comparativo_grupo(base_pai, 'cod_cliente', meta)
fator = calc.dividir(base_pai.loc[base_pai['visao'].eq('Real'), 'metro_padrao'].sum(), real['metro_padrao'])
filhos['impacto_meta_pp'] = filhos['impacto_meta_pp'] * fator  # em p.p. da ocupação total
filhos = filhos.merge(base_pai[['cod_cliente', 'cliente_unidade']].drop_duplicates('cod_cliente'), on='cod_cliente', how='left')
cargas_pai = cargas.loc[cargas['visao'].eq('Real') & cargas['cliente_pai'].eq(cliente)] if not cargas.empty else pd.DataFrame()
filhos['ocs_criticas'] = (
    filhos['cod_cliente'].map(cargas_pai.loc[cargas_pai['abaixo_minimo']].groupby('cod_cliente')['oc'].nunique()).fillna(0)
    if not cargas_pai.empty else 0
)
filhos = filhos.loc[filhos['metro_carregado_real'] > 0].sort_values('impacto_meta_pp').reset_index(drop=True)
if filhos.empty:
    st.stop()

st.markdown('#### Códigos-filhos')
sel_filho = st.dataframe(
    filhos[['cod_cliente', 'cliente_unidade', 'metro_carregado_real', 'ocupacao_real', 'impacto_meta_pp', 'ocs_criticas']],
    hide_index=True, on_select='rerun', selection_mode='single-row', key=f'cli_filhos_{cliente}',
    column_config={
        'cod_cliente': 'Código', 'cliente_unidade': 'Unidade',
        'metro_carregado_real': st.column_config.NumberColumn('Volume (m³)', format='localized'),
        'ocupacao_real': st.column_config.ProgressColumn('Ocupação', format='percent', min_value=0, max_value=1),
        'impacto_meta_pp': st.column_config.NumberColumn('Impacto na meta', format='percent'),
        'ocs_criticas': st.column_config.NumberColumn('OCs abaixo do mín.', format='%d'),
    },
)
linhas_filho = sel_filho.selection.rows if sel_filho else []
codigo = filhos.loc[linhas_filho[0] if linhas_filho else 0, 'cod_cliente']

# Particularidades do código (coluna da direita, ao lado do "por que")
CAMPOS = {
    'restricao_veiculo_cadastro': 'Restrição de veículo', 'aceita_carga_compartilhada_cadastro': 'Aceita carga compartilhada',
    'aceita_sobreposicao': 'Aceita sobreposição', 'paletizado_especial': 'Paletização especial',
    'itens_por_palete': 'Itens por palete', 'altura_maxima': 'Altura máxima do palete',
    'aceita_negocios_juntos': 'Aceita negócios diferentes no mesmo veículo', 'shelf_life': 'Shelf life',
    'agendado': 'Entrega agendada', 'janela_entrega': 'Janela de entrega',
    'regra_de_ouro': 'Regra de ouro', 'observacoes_operacionais': 'Observações',
}
with col_restr.container(border=True, height='stretch'):
    st.markdown(f'**Particularidades do código {codigo}**')
    particularidades = ctx['particularidades']
    registro = (
        particularidades.loc[particularidades['cod_cliente_filho'].astype(str).eq(str(codigo))]
        if not particularidades.empty else pd.DataFrame()
    )
    flags = restricoes.loc[restricoes['cod_cliente'].eq(str(codigo))]
    if not flags.empty:
        ativas = [nome for chave, nome in calc.RESTRICOES.items() if bool(flags.iloc[0][chave])]
        for nome in ativas:
            st.badge(nome, icon=':material/warning:', color='orange')
    if registro.empty:
        st.caption('Nenhuma particularidade cadastrada.')
    else:
        registro = registro.iloc[0]
        itens = [
            f'- **{rotulo}:** {registro.get(campo)}' for campo, rotulo in CAMPOS.items()
            if registro.get(campo) is not None and pd.notna(registro.get(campo))
            and str(registro.get(campo)).strip().lower() not in ('', 'nan', 'none', '-', '0')
        ]
        st.markdown('\n'.join(itens) if itens else 'Nenhum campo preenchido.')

# Cargas fora do padrão do código: só as abaixo do mínimo do veículo
if not cargas_pai.empty:
    criticas = cargas_pai.loc[cargas_pai['cod_cliente'].eq(codigo) & cargas_pai['abaixo_minimo']].copy()
    if not criticas.empty:
        por_oc = (
            criticas.groupby('oc')
            .agg(data_oc=('data_oc', 'first'), ocupacao_oc=('ocupacao_oc', 'first'), perfil_veiculo=('perfil_veiculo', 'first'),
                 tipo_carregamento=('tipo_carregamento', 'first'), pontos=('efeito_minimo_pp', 'sum'))
            .reset_index().sort_values('ocupacao_oc')
        )
        titulo = (f'{len(por_oc)} cargas do código {codigo} saíram abaixo do mínimo do veículo · '
                  f'pontos perdidos: {fmt_pp(por_oc["pontos"].sum())}')
        with st.expander(titulo, icon=':material/warning:'):
            st.dataframe(
                por_oc[['oc', 'data_oc', 'ocupacao_oc', 'perfil_veiculo', 'tipo_carregamento']],
                hide_index=True,
                column_config={
                    'oc': st.column_config.TextColumn('OC'), 'data_oc': st.column_config.DateColumn('Data', format='DD/MM/YYYY'),
                    'ocupacao_oc': st.column_config.ProgressColumn('Ocupação da carga', format='percent', min_value=0, max_value=1),
                    'perfil_veiculo': 'Veículo', 'tipo_carregamento': 'Carregamento',
                },
            )
