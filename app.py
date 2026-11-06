"""Painel de ocupacao logistica - ponto de entrada.

Carrega as bases, aplica os filtros da barra lateral (compartilhados por todas
as paginas), calcula o contexto comum e executa a pagina selecionada.

Executar:  python -m streamlit run app.py
"""

import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR / 'src') not in sys.path:
    sys.path.insert(0, str(BASE_DIR / 'src'))

import calculos as calc  # noqa: E402
import graficos  # noqa: E402

# Recarrega as regras a cada execucao: alteracoes em src/ valem no proximo F5,
# sem reiniciar o servidor. As paginas importam os mesmos objetos de modulo.
calc = importlib.reload(calc)
graficos = importlib.reload(graficos)
fmt_pct = graficos.fmt_pct

PROCESSED = BASE_DIR / 'data' / 'processed'
ARQUIVO_ANALITICO = PROCESSED / 'ocupacao_analitica.parquet'
ARQUIVO_CARGAS = PROCESSED / 'ocupacao_cargas.parquet'
ARQUIVO_PARTICULARIDADES = PROCESSED / 'particularidades_clientes.parquet'
ARQUIVO_LIMITES = BASE_DIR / 'data' / 'config' / 'limites_ocupacao.csv'
ARQUIVO_GEOJSON = BASE_DIR / 'data' / 'geo' / 'br_states.json'

st.set_page_config(page_title='Ocupação logística', page_icon=':material/local_shipping:', layout='wide')


# ---------------------------------------------------------------------------
# Carga de dados (cache invalida sozinho quando o Parquet e regravado)
# ---------------------------------------------------------------------------

def _versao(caminho):
    return caminho.stat().st_mtime if caminho.exists() else None


@st.cache_data(show_spinner='Carregando bases...', max_entries=10)
def carregar_parquet(caminho, versao):
    if versao is None:
        return pd.DataFrame()
    dados = pd.read_parquet(caminho)
    # Linhas sem m3 padrao nao entram na ocupacao (nem no numerador).
    if 'metro_padrao' in dados and 'visao' in dados:
        dados = dados.loc[dados['metro_padrao'].gt(0)].copy()
    if 'cod_cliente' in dados:
        dados['cod_cliente'] = dados['cod_cliente'].map(calc.normalizar_codigo)
    return dados


def carregar_limites():
    if ARQUIVO_LIMITES.exists():
        try:
            salvo = pd.read_csv(ARQUIVO_LIMITES, sep=';', decimal=',')
            padrao = pd.DataFrame(calc.CAPACIDADES_PADRAO)
            if set(padrao.columns).issubset(salvo.columns):
                return calc.preparar_limites(salvo[padrao.columns])
        except (OSError, ValueError, pd.errors.ParserError):
            pass
    return calc.preparar_limites()


if not ARQUIVO_ANALITICO.exists():
    st.error(f'Base não encontrada: {ARQUIVO_ANALITICO}')
    st.info('Atualize as bases com: python src/atualizar_bases.py')
    st.stop()

df_base = carregar_parquet(ARQUIVO_ANALITICO, _versao(ARQUIVO_ANALITICO))
cargas_base = carregar_parquet(ARQUIVO_CARGAS, _versao(ARQUIVO_CARGAS))
particularidades = carregar_parquet(ARQUIVO_PARTICULARIDADES, _versao(ARQUIVO_PARTICULARIDADES))

if 'uf_mapa' not in st.session_state:
    st.session_state['uf_mapa'] = None


# ---------------------------------------------------------------------------
# Filtros (barra lateral)
# ---------------------------------------------------------------------------

meses = df_base[['mes_numero', 'mes_nome']].drop_duplicates().dropna().sort_values('mes_numero')
nome_mes = dict(zip(meses['mes_numero'].astype(int), meses['mes_nome']))
meses_real = sorted(df_base.loc[df_base['visao'].eq('Real'), 'mes_numero'].dropna().astype(int).unique())
if not meses_real:
    st.error('Não existem meses na visão Real.')
    st.stop()
ultimo_mes = meses_real[-1]

with st.sidebar:
    st.header('Filtros')
    modo_periodo = st.segmented_control(
        'Período', ['Acumulado no ano', 'Mês'], default='Acumulado no ano', key='modo_periodo',
    ) or 'Acumulado no ano'
    if modo_periodo == 'Mês':
        mes = st.selectbox(
            'Mês', meses_real, index=len(meses_real) - 1,
            format_func=lambda m: nome_mes.get(m, str(m)), key='mes_selecionado',
        )
        numeros_meses = [mes]
        rotulo_periodo = nome_mes.get(mes, str(mes))
    else:
        numeros_meses = list(range(1, ultimo_mes + 1))
        rotulo_periodo = f'Janeiro a {nome_mes.get(ultimo_mes, ultimo_mes)}'
    st.caption(f'Real × ano anterior (AA): {rotulo_periodo}')

    cds = sorted(df_base['cd_origem'].dropna().unique().tolist())
    cds_sel = st.multiselect('CD de origem', cds, default=cds, key='filtro_cd')

    filtros = {'cd_origem': cds_sel}
    base_opcoes = df_base.loc[df_base['mes_numero'].isin(numeros_meses) & df_base['cd_origem'].isin(cds_sel)]
    with st.expander('Filtros adicionais'):
        rotulos = {
            'cliente_pai': 'Cliente-pai', 'cliente_unidade': 'Cliente / unidade',
            'cod_cliente': 'Código do cliente', 'territorio': 'Território', 'canal': 'Canal',
            'tipo_carregamento': 'Tipo de carregamento', 'tipo_produto': 'Tipo de produto',
            'perfil_veiculo': 'Veículo', 'tipo_ordem': 'Tipo de ordem', 'uf': 'UF',
        }
        for coluna, rotulo in rotulos.items():
            opcoes = sorted(base_opcoes[coluna].dropna().unique().tolist())
            selecao = st.multiselect(rotulo, opcoes, placeholder='Todos', key=f'filtro_{coluna}')
            filtros[coluna] = selecao
            base_opcoes = calc.aplicar_filtros(base_opcoes, {coluna: selecao})

    if st.session_state['uf_mapa']:
        st.info(f'Estado selecionado no mapa: **{st.session_state["uf_mapa"]}**', icon=':material/location_on:')
        if st.button('Ver Brasil inteiro', icon=':material/public:', key='limpar_uf_lateral'):
            st.session_state['uf_mapa'] = None
            st.session_state['mapa_versao'] = st.session_state.get('mapa_versao', 0) + 1
            st.rerun()

    st.divider()
    modo_meta = st.segmented_control(
        'Meta', ['AA + 0,50 p.p.', 'Manual'], default='AA + 0,50 p.p.', key='modo_meta',
    ) or 'AA + 0,50 p.p.'
    meta_manual = None
    if modo_meta == 'Manual':
        meta_manual = st.number_input('Meta (%)', 0.0, 100.0, 67.31, 0.01, key='meta_manual') / 100

if not cds_sel:
    st.warning('Selecione ao menos um CD.')
    st.stop()

df_base_periodo = df_base.loc[df_base['visao'].isin(calc.VISOES) & df_base['mes_numero'].isin(numeros_meses)]
# O mapa ignora a UF clicada para continuar mostrando todos os estados.
df_mapa = calc.aplicar_filtros(df_base_periodo, filtros)

if st.session_state['uf_mapa']:
    filtros_uf = filtros.get('uf') or []
    filtros['uf'] = [st.session_state['uf_mapa']] if not filtros_uf or st.session_state['uf_mapa'] in filtros_uf else ['__nenhuma__']

# Mesmos filtros nas duas bases (analitica e por OC).
df_sem_periodo = calc.aplicar_filtros(df_base.loc[df_base['visao'].isin(calc.VISOES)], filtros)
df = df_sem_periodo.loc[df_sem_periodo['mes_numero'].isin(numeros_meses)].copy()
cargas = pd.DataFrame()
if not cargas_base.empty:
    cargas = calc.aplicar_filtros(
        cargas_base.loc[cargas_base['visao'].isin(calc.VISOES) & cargas_base['mes_numero'].isin(numeros_meses)],
        filtros,
    ).copy()

if df.loc[df['visao'].eq('Real')].empty:
    st.warning('Nenhum registro do Real para os filtros atuais.')
    st.stop()

# ---------------------------------------------------------------------------
# Contexto compartilhado
# ---------------------------------------------------------------------------

total_real = calc.totais_visao(df, 'Real')
total_aa = calc.totais_visao(df, 'AA')
# A meta usa exatamente o mesmo recorte do AA exibido no painel.
meta = calc.calcular_meta(total_aa['ocupacao'], modo_meta != 'Manual', meta_manual)
limites = carregar_limites()
cargas_classificadas = calc.classificar_cargas(
    cargas, limites, {'Real': total_real['metro_padrao'], 'AA': total_aa['metro_padrao']},
)

st.session_state['ctx'] = {
    'df': df,
    'df_mapa': df_mapa,
    'df_sem_periodo': df_sem_periodo.loc[df_sem_periodo['mes_numero'] <= ultimo_mes],
    'cargas': cargas_classificadas,
    'particularidades': particularidades,
    'limites': limites,
    'meta': meta,
    'meta_automatica': modo_meta != 'Manual',
    'total_real': total_real,
    'total_aa': total_aa,
    'rotulo_periodo': rotulo_periodo,
    'arquivos': {
        'limites': ARQUIVO_LIMITES,
        'geojson': ARQUIVO_GEOJSON,
    },
}

with st.sidebar:
    st.metric(
        'Meta aplicada', fmt_pct(meta),
        f'AA {fmt_pct(total_aa["ocupacao"])} + 0,50 p.p.' if modo_meta != 'Manual' else 'definida manualmente',
        delta_color='off',
    )


# ---------------------------------------------------------------------------
# Navegacao
# ---------------------------------------------------------------------------

pagina = st.navigation(
    {
        '': [
            st.Page('app_pages/resultado.py', title='Resultado', icon=':material/map:', default=True),
            st.Page('app_pages/clientes.py', title='Clientes', icon=':material/groups:'),
            st.Page('app_pages/cargas.py', title='Cargas e fechamento', icon=':material/local_shipping:'),
            st.Page('app_pages/tipo_carregamento.py', title='Paletizado × Estivado', icon=':material/pallet:'),
        ],
    },
    position='top',
)
st.title(pagina.title)
st.caption(
    f"{st.session_state['uf_mapa'] or 'Brasil'} · {rotulo_periodo} · Real × ano anterior · Meta {fmt_pct(meta)}"
)
pagina.run()
