import streamlit as st

import calculos as calc
import graficos as gr
from graficos import fmt_num, fmt_pct, fmt_pp

ctx = st.session_state['ctx']
cargas, meta = ctx['cargas'], ctx['meta']
total_padrao = ctx['total_real']['metro_padrao']
corte = calc.DIA_CORTE_FECHAMENTO
arquivo_limites = ctx['arquivos']['limites']

if cargas.empty:
    st.info('Base por OC indisponível. Rode python src/atualizar_bases.py.')
    st.stop()

# --- Fechamento do mês --------------------------------------------------------------
fech_real = calc.analise_fechamento(cargas, 'Real', total_padrao)
fech_aa = calc.analise_fechamento(cargas, 'AA', ctx['total_aa']['metro_padrao'])

st.markdown(f'#### :material/calendar_month: Fechamento do mês (depois do dia {corte})')
with st.container(horizontal=True):
    st.metric(f'Acumulado até o dia {corte}', fmt_pct(fech_real['ocupacao_ate']),
              f"AA: {fmt_pct(fech_aa['ocupacao_ate'])}", delta_color='off', border=True)
    st.metric(f'Cargas do dia {corte + 1} em diante', fmt_pct(fech_real['ocupacao_apos']),
              f"AA: {fmt_pct(fech_aa['ocupacao_apos'])}", delta_color='off', border=True)
    st.metric('Fechou o período em', fmt_pct(fech_real['ocupacao_final']),
              f"{fmt_pp(fech_real['ocupacao_final'] - fech_real['ocupacao_ate'])} desde o dia {corte}", border=True)
with st.container(border=True):
    st.markdown('##### Ocupação dia a dia')
    st.caption(
        'Linha azul: ocupação acumulada no mês até aquele dia. Pontilhada: ano anterior. '
        f'Barras: ocupação das cargas de cada dia — em laranja, os dias de fechamento.'
        + (' No acumulado do ano, cada dia soma todos os meses.' if cargas['mes_numero'].nunique() > 1 else '')
    )
    gr.exibir(
        gr.grafico_ocupacao_dia(calc.ocupacao_por_dia(cargas, 'Real'), calc.ocupacao_por_dia(cargas, 'AA'), meta, corte),
        key='ocupacao_dia',
    )

# --- Cargas abaixo do mínimo -----------------------------------------------------------
st.markdown('#### :material/block: Cargas abaixo do mínimo do veículo')
real = calc.resumo_cargas_criticas(cargas, 'Real')
aa = calc.resumo_cargas_criticas(cargas, 'AA')
per_real = calc.criticas_por_periodo(cargas, 'Real')
if real['perfis_sem_cadastro']:
    st.warning('Veículos sem cadastro (não avaliados): ' + ', '.join(real['perfis_sem_cadastro']))

criticas = cargas.loc[cargas['visao'].eq('Real') & cargas['abaixo_minimo']].copy()
criticas['pontos'] = criticas['efeito_minimo_pp']  # quanto ganharíamos se a carga saísse no mínimo do veículo

with st.container(horizontal=True):
    st.metric('OCs abaixo do mínimo', fmt_num(real['ocs']),
              f"{fmt_pct(calc.dividir(real['ocs'], real['ocs_total']), 1)} das OCs (AA: {fmt_num(aa['ocs'])})",
              delta_color='off', border=True)
    st.metric(f'Saíram depois do dia {corte}', fmt_num(per_real['ocs_apos']),
              f"{fmt_pct(calc.dividir(per_real['ocs_apos'], real['ocs']), 0)} delas", delta_color='off', border=True)
    st.metric('Pontos perdidos', fmt_pp(real['efeito_pp']),
              f"até dia {corte}: {fmt_pp(per_real['ate_pp'])} · depois: {fmt_pp(per_real['apos_pp'])}",
              delta_color='off', border=True,
              help=(f'Quanto a ocupação total subiria se essas cargas tivessem saído no mínimo do veículo. '
                    f'A parte até o dia {corte} é a barra "Cargas abaixo do mínimo" do bridge; '
                    f'a parte depois do dia {corte} está dentro da barra "Fechamento do mês".'))

if criticas.empty:
    st.success('Nenhuma OC abaixo do mínimo no recorte atual.')
    st.stop()


def resumo(dados, coluna):
    tabela = (
        dados.groupby(coluna)
        .agg(ocs=('oc', 'nunique'), car=('metro_carregado', 'sum'), pad=('metro_padrao', 'sum'),
             impacto=('pontos', 'sum'))
        .reset_index().sort_values('impacto').reset_index(drop=True)
    )
    tabela['ocupacao'] = calc.dividir(tabela['car'], tabela['pad'])
    return tabela[[coluna, 'ocs', 'ocupacao', 'impacto']]


config = {
    'ocs': st.column_config.NumberColumn('OCs', format='%d'),
    'ocupacao': st.column_config.ProgressColumn('Ocupação média', format='percent', min_value=0, max_value=1),
    'impacto': st.column_config.NumberColumn('Pontos perdidos', format='percent'),
}
col_pai, col_filho = st.columns(2, gap='medium')
with col_pai.container(border=True):
    st.markdown('##### Por cliente (clique para abrir)')
    pais = resumo(criticas, 'cliente_pai')
    sel_pai = st.dataframe(
        pais, hide_index=True, on_select='rerun', selection_mode='single-row', key='crit_pais', height=380,
        column_config={'cliente_pai': st.column_config.TextColumn('Cliente', width='medium'), **config},
    )
    linhas = sel_pai.selection.rows if sel_pai else []
    pai = pais.loc[linhas[0] if linhas else 0, 'cliente_pai']
with col_filho.container(border=True):
    st.markdown(f'##### Códigos-filhos de {pai}')
    base_pai = criticas.loc[criticas['cliente_pai'].eq(pai)]
    filhos = resumo(base_pai.assign(codigo=base_pai['cod_cliente'] + ' - ' + base_pai['cliente_unidade'].astype(str)), 'codigo')
    sel_filho = st.dataframe(
        filhos, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'crit_filhos_{pai}', height=380,
        column_config={'codigo': st.column_config.TextColumn('Código', width='medium'), **config},
    )
    linhas_f = sel_filho.selection.rows if sel_filho else []
    codigo = filhos.loc[linhas_f[0] if linhas_f else 0, 'codigo']

ocs = (
    base_pai.loc[(base_pai['cod_cliente'] + ' - ' + base_pai['cliente_unidade'].astype(str)).eq(codigo)]
    .groupby('oc').agg(data_oc=('data_oc', 'first'), ocupacao_oc=('ocupacao_oc', 'first'),
                       perfil_veiculo=('perfil_veiculo', 'first'), tipo_carregamento=('tipo_carregamento', 'first'),
                       pontos=('pontos', 'sum'))
    .reset_index()
)
with st.expander(f'{len(ocs)} OCs do código {codigo.split(" - ")[0]}', icon=':material/list_alt:', expanded=True):
    st.dataframe(
        ocs.sort_values('ocupacao_oc')[['oc', 'data_oc', 'ocupacao_oc', 'perfil_veiculo', 'tipo_carregamento']],
        hide_index=True,
        column_config={
            'oc': st.column_config.TextColumn('OC'), 'data_oc': st.column_config.DateColumn('Data', format='DD/MM/YYYY'),
            'ocupacao_oc': st.column_config.ProgressColumn('Ocupação da carga', format='percent', min_value=0, max_value=1),
            'perfil_veiculo': 'Veículo', 'tipo_carregamento': 'Carregamento',
        },
    )

with st.expander('Configurar ocupação mínima por veículo', icon=':material/tune:'):
    limites_editados = st.data_editor(
        ctx['limites'], hide_index=True,
        disabled=['codigo_perfil', 'perfil_padrao', 'capacidade_m3', 'capacidade_kg'],
        column_config={
            'codigo_perfil': 'Código', 'perfil_padrao': 'Veículo',
            'capacidade_m3': st.column_config.NumberColumn('Capacidade (m³)', format='%.1f'),
            'capacidade_kg': st.column_config.NumberColumn('Capacidade (kg)', format='localized'),
            'ocupacao_minima': st.column_config.NumberColumn('Ocupação mínima', min_value=0.10, max_value=1.0, step=0.05, format='percent'),
        },
        key='editor_limites',
    )
    if st.button('Salvar limites', icon=':material/save:'):
        arquivo_limites.parent.mkdir(parents=True, exist_ok=True)
        calc.preparar_limites(limites_editados).to_csv(arquivo_limites, sep=';', decimal=',', index=False)
        st.rerun()
