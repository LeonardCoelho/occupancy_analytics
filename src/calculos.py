"""Regras de calculo do painel de ocupacao.

Todas as funcoes sao puras (recebem DataFrames e devolvem DataFrames/dicts),
sem dependencia do Streamlit, para poderem ser testadas isoladamente.

Convencoes
----------
- Ocupacao sempre ponderada: SUM(m3 carregado) / SUM(m3 padrao).
- Valores em p.p. sao fracoes (0.005 = 0,50 p.p.).
- "pad" = m3 padrao (capacidade), "car" = m3 carregado.
- Na base por OC, o m3 padrao de uma OC compartilhada e rateado entre as
  linhas (clientes) proporcionalmente; por isso a ocupacao de cada linha e
  igual a ocupacao da OC e o deficit por linha soma o deficit da OC.
"""

import unicodedata

import numpy as np
import pandas as pd

VISOES = ('Real', 'AA')
TIPOS_CARREGAMENTO = ('Paletizado', 'Estivado')
INCREMENTO_META_AUTOMATICA = 0.005
LIMITE_TROCA_INTEGRAL = 0.95
DIA_CORTE_FECHAMENTO = 20

CAPACIDADES_PADRAO = [
    {'codigo_perfil': 39, 'perfil_padrao': 'VAN (R)', 'capacidade_m3': 6.0, 'capacidade_kg': 1600, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 14, 'perfil_padrao': 'VAN (S)', 'capacidade_m3': 7.0, 'capacidade_kg': 1600, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 13, 'perfil_padrao': 'VUC (R)', 'capacidade_m3': 11.0, 'capacidade_kg': 2000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 12, 'perfil_padrao': 'VUC (S)', 'capacidade_m3': 12.0, 'capacidade_kg': 2000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 11, 'perfil_padrao': 'F-4000 (R)', 'capacidade_m3': 15.0, 'capacidade_kg': 3000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 10, 'perfil_padrao': 'F-4000 (S)', 'capacidade_m3': 18.0, 'capacidade_kg': 3000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 4, 'perfil_padrao': 'TOCO (R)', 'capacidade_m3': 23.0, 'capacidade_kg': 6000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 3, 'perfil_padrao': 'TOCO (S)', 'capacidade_m3': 25.0, 'capacidade_kg': 6000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 9, 'perfil_padrao': 'TRUCK (R)', 'capacidade_m3': 36.0, 'capacidade_kg': 12000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 8, 'perfil_padrao': 'TRUCK (S)', 'capacidade_m3': 42.0, 'capacidade_kg': 12000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 2, 'perfil_padrao': 'CARRETA (R)', 'capacidade_m3': 74.0, 'capacidade_kg': 25000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 1, 'perfil_padrao': 'CARRETA (S)', 'capacidade_m3': 82.0, 'capacidade_kg': 25000, 'ocupacao_minima': 0.50},
    {'codigo_perfil': 40, 'perfil_padrao': 'BI TREM', 'capacidade_m3': 120.0, 'capacidade_kg': 34000, 'ocupacao_minima': 0.50},
]

# Nomes usados na base operacional -> perfil do cadastro.
ALIASES_PERFIL = {
    'VAN REFRIGERADA': 'VAN (R)', 'VAN REFRIGERADO': 'VAN (R)',
    'VAN SECO': 'VAN (S)', 'VAN SECA': 'VAN (S)',
    'VUC REFRIGERADO': 'VUC (R)', 'VUC REFRIGERADA': 'VUC (R)',
    'VUC SECO': 'VUC (S)', 'VUC SECA': 'VUC (S)',
    '3/4 REFRIGERADO': 'F-4000 (R)', '3/4 REFRIGERADA': 'F-4000 (R)',
    '3/4 SECO': 'F-4000 (S)', '3/4 SECA': 'F-4000 (S)',
    'TOCO REFRIGERADO': 'TOCO (R)', 'TOCO REFRIGERADA': 'TOCO (R)',
    'TOCO SECO': 'TOCO (S)', 'TOCO SECA': 'TOCO (S)',
    'TRUCK REFRIGERADO': 'TRUCK (R)', 'TRUCK REFRIGERADA': 'TRUCK (R)',
    'TRUCK SECO': 'TRUCK (S)', 'TRUCK SECA': 'TRUCK (S)',
    'CARRETA REFRIGERADA': 'CARRETA (R)', 'CARRETA REFRIGERADO': 'CARRETA (R)',
    'CARRETA SECA': 'CARRETA (S)', 'CARRETA SECO': 'CARRETA (S)',
    'BI TREM': 'BI TREM', 'BI TREM SECO': 'BI TREM', 'BITREM': 'BI TREM',
    'BI-TREM': 'BI TREM',
}

# Dimensoes que existem na base analitica e na base por OC. Os filtros do
# painel sao aplicados nas duas com as mesmas regras.
DIMENSOES_FILTRO = [
    'cd_origem', 'cliente_pai', 'cliente_unidade', 'cod_cliente',
    'territorio', 'canal', 'tipo_carregamento', 'tipo_produto',
    'perfil_veiculo', 'tipo_ordem', 'uf',
]


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def _sem_acento(texto):
    normalizado = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in normalizado if not unicodedata.combining(c))


def normalizar_perfil(valor):
    """Converte o nome do perfil da base para o perfil do cadastro."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    texto = ' '.join(_sem_acento(str(valor)).upper().split())
    if texto in ALIASES_PERFIL:
        return ALIASES_PERFIL[texto]
    # Formato do proprio cadastro: "TOCO (S)", "F-4000 (R)", "F 4000 ( R )".
    compacto = texto.replace('-', ' ').replace('( ', '(').replace(' )', ')')
    compacto = ' '.join(compacto.split())
    cadastro = {p['perfil_padrao'].replace('-', ' '): p['perfil_padrao'] for p in CAPACIDADES_PADRAO}
    return cadastro.get(compacto)


def normalizar_codigo(valor):
    if valor is None or pd.isna(valor):
        return ''
    texto = str(valor).strip()
    return texto[:-2] if texto.endswith('.0') else texto


def dividir(numerador, denominador):
    """Divisao segura para escalares e Series."""
    if isinstance(denominador, pd.Series):
        resultado = numerador / denominador.where(denominador > 0)
        return resultado.astype(float)
    if denominador is None or pd.isna(denominador) or denominador <= 0:
        return np.nan
    return numerador / denominador


def aplicar_filtros(dataframe, filtros):
    """filtros: {coluna: [valores]}. Lista vazia/None = todos."""
    mascara = pd.Series(True, index=dataframe.index)
    for coluna, valores in filtros.items():
        if valores and coluna in dataframe.columns:
            mascara &= dataframe[coluna].isin(valores)
    return dataframe.loc[mascara]


# ---------------------------------------------------------------------------
# Totais e meta
# ---------------------------------------------------------------------------

def totais_visao(dataframe, visao):
    base = dataframe.loc[dataframe['visao'].eq(visao)]
    car = base['metro_carregado'].sum()
    pad = base['metro_padrao'].sum()
    return {
        'metro_carregado': car,
        'metro_padrao': pad,
        'ocupacao': dividir(car, pad),
        'frete_total': base['frete_total'].sum() if 'frete_total' in base else np.nan,
        'registros': len(base),
    }


def impacto_meta_somavel(comparativo, automatica=True):
    """Impacto de cada grupo na meta que SOMA exatamente Real - meta.

    Meta automatica (AA + 0,50): impacto = contribuicao Real x AA do grupo
    - peso_Real x 0,50 p.p. Cada grupo e comparado com o proprio AA e tambem
    responde pelo volume que ganhou/perdeu. Meta manual: impacto contra a meta.
    """
    if automatica:
        return comparativo['contribuicao_aa_pp'] - comparativo['peso_real'] * INCREMENTO_META_AUTOMATICA
    return comparativo['impacto_meta_pp']


def calcular_meta(ocupacao_aa, modo_automatico=True, meta_manual=None, padrao=0.6731):
    if modo_automatico and pd.notna(ocupacao_aa):
        return min(ocupacao_aa + INCREMENTO_META_AUTOMATICA, 1.0)
    if meta_manual is not None:
        return meta_manual
    return padrao


# ---------------------------------------------------------------------------
# Comparativo por grupo (cliente-pai, codigo-filho, UF ...)
# ---------------------------------------------------------------------------

def comparativo_grupo(dataframe, coluna, meta):
    """Real x AA por grupo, com metricas de impacto que somam exatamente.

    - impacto_meta_pp: (car_R - meta * pad_R) / PAD_R.
      Soma de todos os grupos = Ocupacao Real - meta.
    - contribuicao_aa_pp: w_R (o_R - O_AA) - w_AA (o_AA - O_AA), com w = peso
      do grupo no m3 padrao total. Soma de todos os grupos = Real - AA.
      Divide-se em efeito_ocupacao_pp (o grupo carregou melhor/pior) e
      efeito_composicao_pp (o grupo ganhou/perdeu peso no total).
    """
    agrupado = (
        dataframe.groupby([coluna, 'visao'], dropna=False)
        .agg(metro_carregado=('metro_carregado', 'sum'),
             metro_padrao=('metro_padrao', 'sum'),
             frete_total=('frete_total', 'sum'))
        .reset_index()
    )
    tabela = agrupado.pivot_table(
        index=coluna, columns='visao',
        values=['metro_carregado', 'metro_padrao', 'frete_total'],
        aggfunc='sum', fill_value=0.0,
    )
    tabela.columns = [f'{m}_{str(v).lower()}' for m, v in tabela.columns]
    tabela = tabela.reset_index()
    for metrica in ('metro_carregado', 'metro_padrao', 'frete_total'):
        for visao in ('real', 'aa'):
            if f'{metrica}_{visao}' not in tabela:
                tabela[f'{metrica}_{visao}'] = 0.0

    total_r = totais_visao(dataframe, 'Real')
    total_a = totais_visao(dataframe, 'AA')
    o_aa_total = total_a['ocupacao']

    tabela['ocupacao_real'] = dividir(tabela['metro_carregado_real'], tabela['metro_padrao_real'])
    tabela['ocupacao_aa'] = dividir(tabela['metro_carregado_aa'], tabela['metro_padrao_aa'])
    tabela['variacao_ocupacao_pp'] = tabela['ocupacao_real'] - tabela['ocupacao_aa']
    tabela['variacao_volume_pct'] = dividir(tabela['metro_carregado_real'], tabela['metro_carregado_aa']) - 1
    tabela['participacao_volume_real'] = dividir(tabela['metro_carregado_real'], pd.Series(total_r['metro_carregado'], index=tabela.index))
    tabela['participacao_volume_aa'] = dividir(tabela['metro_carregado_aa'], pd.Series(total_a['metro_carregado'], index=tabela.index))
    tabela['variacao_participacao_pp'] = (
        tabela['participacao_volume_real'].fillna(0) - tabela['participacao_volume_aa'].fillna(0)
    )

    peso_r = dividir(tabela['metro_padrao_real'], pd.Series(total_r['metro_padrao'], index=tabela.index)).fillna(0)
    peso_a = dividir(tabela['metro_padrao_aa'], pd.Series(total_a['metro_padrao'], index=tabela.index)).fillna(0)
    tabela['peso_real'] = peso_r
    tabela['peso_aa'] = peso_a

    tabela['impacto_meta_pp'] = (
        (tabela['metro_carregado_real'] - meta * tabela['metro_padrao_real'])
        / total_r['metro_padrao'] if total_r['metro_padrao'] > 0 else np.nan
    )

    if pd.notna(o_aa_total):
        termo_r = peso_r * (tabela['ocupacao_real'].fillna(0) - o_aa_total)
        termo_a = peso_a * (tabela['ocupacao_aa'].fillna(0) - o_aa_total)
        termo_r = termo_r.where(peso_r > 0, 0.0)
        termo_a = termo_a.where(peso_a > 0, 0.0)
        tabela['contribuicao_aa_pp'] = termo_r - termo_a
        ambos = (peso_r > 0) & (peso_a > 0)
        tabela['efeito_ocupacao_pp'] = np.where(
            ambos, peso_r * (tabela['ocupacao_real'] - tabela['ocupacao_aa']), 0.0
        )
        tabela['efeito_composicao_pp'] = tabela['contribuicao_aa_pp'] - tabela['efeito_ocupacao_pp']
    else:
        tabela['contribuicao_aa_pp'] = np.nan
        tabela['efeito_ocupacao_pp'] = np.nan
        tabela['efeito_composicao_pp'] = np.nan

    tabela['status'] = np.select(
        [(peso_r > 0) & (peso_a > 0), peso_r > 0, peso_a > 0],
        ['Comparável', 'Novo no Real', 'Sem movimento no Real'],
        default='Sem dados',
    )
    return tabela


# ---------------------------------------------------------------------------
# Tipo de carregamento (Paletizado x Estivado)
# ---------------------------------------------------------------------------

def analise_tipo_carregamento(dataframe):
    """Efeito da mudanca de representatividade entre os tipos.

    efeito = SUM_t o_R,t * (w_R,t - w_AA,t): quanto a ocupacao Real mudou so
    porque a composicao de capacidade entre Paletizado e Estivado mudou,
    mantendo a ocupacao atual de cada tipo.
    """
    base = dataframe.loc[dataframe['tipo_carregamento'].isin(TIPOS_CARREGAMENTO)]
    agrupado = (
        base.groupby(['tipo_carregamento', 'visao'])
        .agg(metro_carregado=('metro_carregado', 'sum'),
             metro_padrao=('metro_padrao', 'sum'))
        .reset_index()
    )
    detalhe = agrupado.pivot_table(
        index='tipo_carregamento', columns='visao',
        values=['metro_carregado', 'metro_padrao'], aggfunc='sum', fill_value=0.0,
    )
    detalhe.columns = [f'{m}_{str(v).lower()}' for m, v in detalhe.columns]
    detalhe = detalhe.reindex(list(TIPOS_CARREGAMENTO)).fillna(0.0).reset_index()
    for coluna in ('metro_carregado_real', 'metro_carregado_aa', 'metro_padrao_real', 'metro_padrao_aa'):
        if coluna not in detalhe:
            detalhe[coluna] = 0.0

    detalhe['ocupacao_real'] = dividir(detalhe['metro_carregado_real'], detalhe['metro_padrao_real'])
    detalhe['ocupacao_aa'] = dividir(detalhe['metro_carregado_aa'], detalhe['metro_padrao_aa'])
    detalhe['representatividade_real'] = dividir(detalhe['metro_padrao_real'], pd.Series(detalhe['metro_padrao_real'].sum(), index=detalhe.index))
    detalhe['representatividade_aa'] = dividir(detalhe['metro_padrao_aa'], pd.Series(detalhe['metro_padrao_aa'].sum(), index=detalhe.index))
    detalhe['variacao_representatividade_pp'] = detalhe['representatividade_real'] - detalhe['representatividade_aa']
    detalhe['variacao_ocupacao_pp'] = detalhe['ocupacao_real'] - detalhe['ocupacao_aa']
    detalhe['variacao_volume_pct'] = dividir(detalhe['metro_carregado_real'], detalhe['metro_carregado_aa']) - 1

    validos = detalhe['ocupacao_real'].notna() & detalhe['representatividade_aa'].notna()
    if validos.any() and detalhe['metro_padrao_aa'].sum() > 0:
        efeito = (
            detalhe.loc[validos, 'ocupacao_real']
            * detalhe.loc[validos, 'variacao_representatividade_pp']
        ).sum()
        simulada = (
            detalhe.loc[validos, 'ocupacao_real'] * detalhe.loc[validos, 'representatividade_aa']
        ).sum()
    else:
        efeito, simulada = np.nan, np.nan

    return {
        'detalhe': detalhe,
        'efeito_pp': efeito,
        'ocupacao_composicao_aa': simulada,
    }


def classificar_troca(perc_pal_aa, perc_pal_real, limite=LIMITE_TROCA_INTEGRAL):
    if pd.isna(perc_pal_aa) or pd.isna(perc_pal_real):
        return 'Sem base de comparação'
    pal_aa, pal_r = perc_pal_aa >= limite, perc_pal_real >= limite
    est_aa, est_r = perc_pal_aa <= 1 - limite, perc_pal_real <= 1 - limite
    if est_aa and pal_r:
        return 'Troca integral: Estivado → Paletizado'
    if pal_aa and est_r:
        return 'Troca integral: Paletizado → Estivado'
    if (pal_aa and pal_r) or (est_aa and est_r):
        return 'Sem mudança de tipo'
    return 'Composição mista'


def tipo_carregamento_por_cliente(dataframe, coluna, meta):
    """Composicao Paletizado x Estivado por cliente e impacto das trocas.

    - perc_paletizado_*: participacao do Paletizado no m3 padrao do cliente.
    - contrib_repr_paletizado_pp: quanto o cliente mexeu na representatividade
      global do Paletizado (soma dos clientes = variacao global).
    - impacto_troca_pp: para troca integral, efeito de ocupacao do cliente no
      consolidado = w_R * (o_R - o_AA). Para mistos fica vazio.
    """
    base = dataframe.loc[dataframe['tipo_carregamento'].isin(TIPOS_CARREGAMENTO)]
    pad = (
        base.groupby([coluna, 'visao', 'tipo_carregamento'])['metro_padrao']
        .sum().unstack(['visao', 'tipo_carregamento'], fill_value=0.0)
    )
    for visao in VISOES:
        for tipo in TIPOS_CARREGAMENTO:
            if (visao, tipo) not in pad.columns:
                pad[(visao, tipo)] = 0.0
    total_pad = {v: base.loc[base['visao'].eq(v), 'metro_padrao'].sum() for v in VISOES}

    resultado = pd.DataFrame(index=pad.index)
    for visao in VISOES:
        sufixo = visao.lower()
        total_cliente = pad[(visao, 'Paletizado')] + pad[(visao, 'Estivado')]
        resultado[f'perc_paletizado_{sufixo}'] = dividir(pad[(visao, 'Paletizado')], total_cliente)
        for tipo in TIPOS_CARREGAMENTO:
            resultado[f'peso_{tipo.lower()}_{sufixo}'] = (
                pad[(visao, tipo)] / total_pad[visao] if total_pad[visao] > 0 else np.nan
            )
    for tipo in TIPOS_CARREGAMENTO:
        t = tipo.lower()
        resultado[f'contrib_repr_{t}_pp'] = (
            resultado[f'peso_{t}_real'].fillna(0) - resultado[f'peso_{t}_aa'].fillna(0)
        )
    resultado['classificacao'] = [
        classificar_troca(a, r)
        for a, r in zip(resultado['perc_paletizado_aa'], resultado['perc_paletizado_real'])
    ]
    resultado['tipo_predominante_real'] = np.where(
        resultado['perc_paletizado_real'].isna(), 'Sem Real',
        np.where(resultado['perc_paletizado_real'] >= 0.5, 'Paletizado', 'Estivado'),
    )
    resultado = resultado.reset_index()

    comparativo = comparativo_grupo(dataframe, coluna, meta)[[
        coluna, 'metro_carregado_real', 'metro_carregado_aa', 'ocupacao_real',
        'ocupacao_aa', 'variacao_ocupacao_pp', 'efeito_ocupacao_pp',
        'contribuicao_aa_pp', 'impacto_meta_pp', 'participacao_volume_real',
    ]]
    resultado = resultado.merge(comparativo, on=coluna, how='left')
    troca = resultado['classificacao'].str.startswith('Troca integral')
    resultado['impacto_troca_pp'] = np.where(troca, resultado['efeito_ocupacao_pp'], np.nan)

    # Mudanca de tipo do proprio cliente (so quem existe nos dois anos):
    # peso do cliente x variacao do % paletizado x (ocup. paletizado - ocup. estivado).
    ocup_tipo = {}
    for tipo in TIPOS_CARREGAMENTO:
        parte = base.loc[base['visao'].eq('Real') & base['tipo_carregamento'].eq(tipo)]
        ocup_tipo[tipo] = dividir(parte['metro_carregado'].sum(), parte['metro_padrao'].sum())
    diferenca_tipos = ocup_tipo['Paletizado'] - ocup_tipo['Estivado']
    peso_cliente = resultado['peso_paletizado_real'].fillna(0) + resultado['peso_estivado_real'].fillna(0)
    resultado['variacao_paletizado_pp'] = resultado['perc_paletizado_real'] - resultado['perc_paletizado_aa']
    resultado['impacto_mudanca_tipo_pp'] = (
        peso_cliente * resultado['variacao_paletizado_pp'] * diferenca_tipos
        if pd.notna(diferenca_tipos) else np.nan
    )
    return resultado


# ---------------------------------------------------------------------------
# Cargas (OCs) abaixo do minimo
# ---------------------------------------------------------------------------

def preparar_limites(limites=None):
    tabela = pd.DataFrame(CAPACIDADES_PADRAO) if limites is None else limites.copy()
    tabela['ocupacao_minima'] = (
        pd.to_numeric(tabela['ocupacao_minima'], errors='coerce').fillna(0.50).clip(0.10, 1.00)
    )
    return tabela


def classificar_cargas(cargas, limites, total_padrao_por_visao):
    """Marca OCs abaixo da ocupacao minima do perfil.

    A ocupacao da OC usa o proprio m3 padrao da OC (mesmo denominador do
    indicador consolidado). Como o m3 padrao e rateado entre os clientes da
    OC, cada linha tem a mesma ocupacao da OC e o deficit e somavel.
    """
    if cargas.empty:
        return cargas.assign(
            perfil_padrao=pd.Series(dtype=str), ocupacao_minima=pd.Series(dtype=float),
            ocupacao_oc=pd.Series(dtype=float), abaixo_minimo=pd.Series(dtype=bool),
            deficit_minimo_m3=pd.Series(dtype=float), efeito_minimo_pp=pd.Series(dtype=float),
        )
    resultado = cargas.copy()
    resultado['perfil_padrao'] = resultado['perfil_veiculo'].map(normalizar_perfil)
    resultado = resultado.merge(
        limites[['perfil_padrao', 'capacidade_m3', 'ocupacao_minima']],
        on='perfil_padrao', how='left',
    )
    por_oc = resultado.groupby(['visao', 'oc'])
    resultado['metro_carregado_oc'] = por_oc['metro_carregado'].transform('sum')
    resultado['metro_padrao_oc'] = por_oc['metro_padrao'].transform('sum')
    resultado['clientes_na_oc'] = por_oc['cod_cliente'].transform('nunique')
    resultado['ocupacao_oc'] = dividir(resultado['metro_carregado_oc'], resultado['metro_padrao_oc'])
    resultado['abaixo_minimo'] = (
        resultado['ocupacao_minima'].notna()
        & resultado['ocupacao_oc'].lt(resultado['ocupacao_minima'])
    )
    deficit = (resultado['ocupacao_minima'] * resultado['metro_padrao'] - resultado['metro_carregado']).clip(lower=0)
    resultado['deficit_minimo_m3'] = deficit.where(resultado['abaixo_minimo'], 0.0).fillna(0.0)
    total = resultado['visao'].map(total_padrao_por_visao).astype(float)
    resultado['efeito_minimo_pp'] = -dividir(resultado['deficit_minimo_m3'], total).fillna(0.0)
    return resultado


def resumo_cargas_criticas(cargas_classificadas, visao):
    base = cargas_classificadas.loc[cargas_classificadas['visao'].eq(visao)]
    criticas = base.loc[base['abaixo_minimo']]
    return {
        'ocs': criticas['oc'].nunique(),
        'ocs_total': base['oc'].nunique(),
        'ocupacao_media': dividir(criticas['metro_carregado'].sum(), criticas['metro_padrao'].sum()),
        'deficit_m3': criticas['deficit_minimo_m3'].sum(),
        'efeito_pp': criticas['efeito_minimo_pp'].sum(),
        'perfis_sem_cadastro': sorted(base.loc[base['perfil_padrao'].isna(), 'perfil_veiculo'].dropna().unique().tolist()),
    }


# ---------------------------------------------------------------------------
# Fechamento do mes (ate dia 20 x apos dia 20)
# ---------------------------------------------------------------------------

def analise_fechamento(cargas_classificadas, visao, total_padrao, dia_corte=DIA_CORTE_FECHAMENTO):
    """Efeito das cargas expedidas apos o dia de corte de cada mes.

    Ocupacao simulada = (car_ate20 + o_ate20 * pad_apos20) / PAD.
    Impacto = (car_apos20 - o_ate20 * pad_apos20) / PAD.

    impacto_sem_criticas_pp considera somente OCs que NAO estao abaixo do
    minimo (as criticas ja entram no bloco proprio do bridge).
    """
    base = cargas_classificadas.loc[cargas_classificadas['visao'].eq(visao)].copy()
    vazio = {
        'ocupacao_ate': np.nan, 'ocupacao_apos': np.nan, 'ocupacao_final': np.nan,
        'impacto_pp': np.nan, 'impacto_sem_criticas_pp': np.nan, 'resumo': pd.DataFrame(),
    }
    if base.empty or total_padrao <= 0:
        return vazio
    base['data_oc'] = pd.to_datetime(base['data_oc'], errors='coerce')
    base = base.loc[base['data_oc'].notna()]
    base['periodo'] = np.where(base['data_oc'].dt.day <= dia_corte, f'Até dia {dia_corte}', f'Após dia {dia_corte}')
    ate = base['periodo'].str.startswith('Até')

    def ocup(mascara):
        return dividir(base.loc[mascara, 'metro_carregado'].sum(), base.loc[mascara, 'metro_padrao'].sum())

    o_ate, o_apos, o_final = ocup(ate), ocup(~ate), ocup(pd.Series(True, index=base.index))
    car_apos, pad_apos = base.loc[~ate, 'metro_carregado'].sum(), base.loc[~ate, 'metro_padrao'].sum()
    impacto = (car_apos - o_ate * pad_apos) / total_padrao if pd.notna(o_ate) else np.nan

    nao_critica = ~base['abaixo_minimo'].fillna(False).astype(bool)
    o_ate_nc = ocup(ate & nao_critica)
    car_apos_nc = base.loc[~ate & nao_critica, 'metro_carregado'].sum()
    pad_apos_nc = base.loc[~ate & nao_critica, 'metro_padrao'].sum()
    impacto_nc = (car_apos_nc - o_ate_nc * pad_apos_nc) / total_padrao if pd.notna(o_ate_nc) else np.nan

    resumo = (
        base.groupby('periodo')
        .agg(ocs=('oc', 'nunique'), metro_carregado=('metro_carregado', 'sum'),
             metro_padrao=('metro_padrao', 'sum'))
        .reset_index()
        .sort_values('periodo', ascending=False)
    )
    resumo['ocupacao'] = dividir(resumo['metro_carregado'], resumo['metro_padrao'])
    return {
        'ocupacao_ate': o_ate, 'ocupacao_apos': o_apos, 'ocupacao_final': o_final,
        'impacto_pp': impacto, 'impacto_sem_criticas_pp': impacto_nc, 'resumo': resumo,
    }


# ---------------------------------------------------------------------------
# Bridge AA -> Real
# ---------------------------------------------------------------------------

def criticas_por_periodo(cargas_classificadas, visao, dia_corte=DIA_CORTE_FECHAMENTO):
    """Perda das OCs abaixo do minimo separada em ate / apos o dia de corte."""
    base = cargas_classificadas.loc[
        cargas_classificadas['visao'].eq(visao) & cargas_classificadas['abaixo_minimo']
    ]
    apos = pd.to_datetime(base['data_oc'], errors='coerce').dt.day > dia_corte
    return {
        'ate_pp': base.loc[~apos, 'efeito_minimo_pp'].sum(),
        'apos_pp': base.loc[apos, 'efeito_minimo_pp'].sum(),
        'ocs_ate': base.loc[~apos, 'oc'].nunique(),
        'ocs_apos': base.loc[apos, 'oc'].nunique(),
    }


def calcular_bridge(ocupacao_aa, ocupacao_real, meta, efeito_tipo, efeito_criticas_ate, efeito_fechamento):
    """Ponte da meta ate a ocupacao Real: por que nao chegamos.

    Cada barra responde "quanto a ocupacao seria maior se...":
    - Tipo de carregamento: ...a proporcao Paletizado x Estivado fosse a do AA;
    - Fechamento do mes: ...as cargas apos o dia de corte tivessem a mesma
      ocupacao das cargas ate o dia de corte (inclui as abaixo do minimo);
    - Cargas abaixo do minimo: ...as cargas abaixo do minimo ate o dia de
      corte tivessem saido no minimo do veiculo.
    Os grupos de OCs nao se sobrepoem. "Demais efeitos" e o residuo, para a
    soma fechar no Real.
    """
    def limpar(valor):
        return 0.0 if valor is None or pd.isna(valor) else valor

    fechamento = limpar(efeito_fechamento)
    todos = {
        'Tipo de carregamento': limpar(efeito_tipo),
        'Fechamento do mês': fechamento,
        'Cargas abaixo do mínimo': limpar(efeito_criticas_ate),
    }
    # So os motivos que afastaram da meta aparecem; os que ajudaram entram
    # em "Demais efeitos" (o bridge mostra por que nao chegamos).
    efeitos = {nome: valor for nome, valor in todos.items() if valor < 0}
    demais = ocupacao_real - meta - sum(efeitos.values())
    etapas = [('Meta', meta, 'absolute')]
    etapas += [(nome, valor, 'relative') for nome, valor in efeitos.items()]
    etapas += [('Demais efeitos', demais, 'relative'), ('Ocupação Real', ocupacao_real, 'total')]
    return {
        'etapas': etapas,
        'efeitos': todos,
        'demais_pp': demais,
        'meta': meta,
        'fechamento_pp': fechamento,
        'gap_meta_pp': ocupacao_real - meta,
        'variacao_aa_pp': ocupacao_real - ocupacao_aa,
    }


# ---------------------------------------------------------------------------
# Diagnostico de clientes: causa principal e acao sugerida
# ---------------------------------------------------------------------------

CAUSAS = {
    'perfil': 'Perfil de carga desfavorável',
    'criticas': 'Cargas abaixo do mínimo',
    'fechamento': 'Piora no fechamento do mês',
    'execucao': 'Carrega abaixo do padrão',
}

ACOES = {
    'perfil': 'Negociar com o cliente a paletização (altura, itens por palete, sobreposição), o pedido '
              'mínimo ou um veículo mais adequado.',
    'criticas': 'Consolidar pedidos, ajustar a janela de entrega ou usar veículo menor nessas rotas; '
                'justificar as OCs abaixo do mínimo.',
    'fechamento': f'Antecipar faturamento e programação para antes do dia {DIA_CORTE_FECHAMENTO} e evitar '
                  'liberar cargas incompletas no fechamento.',
    'execucao': 'Revisar a montagem e a consolidação das cargas e conferir as restrições do cliente.',
}


def diagnostico_clientes(df, cargas_classificadas, meta, coluna='cliente_pai', dia_corte=DIA_CORTE_FECHAMENTO):
    """Ranking de clientes com a causa principal da perda contra a meta.

    O impacto na meta do cliente e separado em parcelas que somam exatamente
    o impacto (p.p. do total do painel, negativo = perda):
    - perfil: o mix de tipo de carregamento x perfil de veiculo do cliente,
      avaliado pela ocupacao media do painel nesse mix, fica abaixo da meta;
    - execucao: o cliente carrega pior (ou melhor) que a media do painel no
      mesmo tipo e veiculo. Dentro da execucao, destacam-se:
        - criticas: perda das OCs abaixo do minimo do perfil;
        - fechamento: cargas nao criticas apos o dia de corte piores que as
          do inicio do mes do proprio cliente;
        - execucao (restante).
    A causa principal e a parcela mais negativa.
    """
    base = comparativo_grupo(df, coluna, meta)
    base = base.loc[base['metro_carregado_real'] > 0].copy()
    real_df = df.loc[df['visao'].eq('Real')]
    total_pad = real_df['metro_padrao'].sum()
    base['ganho_potencial_m3'] = (meta * base['metro_padrao_real'] - base['metro_carregado_real']).clip(lower=0)

    # Referencia: ocupacao dos OUTROS clientes no mesmo tipo de carregamento e
    # veiculo (o proprio cliente fica fora para nao puxar a propria referencia).
    chave = ['tipo_carregamento', 'perfil_veiculo']
    celula_cliente = real_df.groupby([coluna] + chave)[['metro_carregado', 'metro_padrao']].sum().reset_index()
    celula_total = real_df.groupby(chave)[['metro_carregado', 'metro_padrao']].sum().add_suffix('_total').reset_index()
    mix = celula_cliente.merge(celula_total, on=chave, how='left')
    outros_pad = mix['metro_padrao_total'] - mix['metro_padrao']
    referencia = dividir(mix['metro_carregado_total'] - mix['metro_carregado'], outros_pad)
    mix['esperado'] = referencia.fillna(meta) * mix['metro_padrao']
    esperado = mix.groupby(coluna)[['esperado', 'metro_padrao']].sum()

    parcelas = pd.DataFrame(index=base[coluna])
    parcelas['ocupacao_referencia'] = dividir(esperado['esperado'], esperado['metro_padrao'])
    parcelas['perfil'] = (esperado['esperado'] - meta * esperado['metro_padrao']) / total_pad if total_pad > 0 else 0.0
    real = cargas_classificadas.loc[cargas_classificadas['visao'].eq('Real')] if not cargas_classificadas.empty else cargas_classificadas
    if not real.empty and total_pad > 0:
        criticas = real.loc[real['abaixo_minimo']]
        parcelas['criticas'] = criticas.groupby(coluna)['efeito_minimo_pp'].sum()
        parcelas['ocs_criticas'] = criticas.groupby(coluna)['oc'].nunique()
        parcelas['ocs'] = real.groupby(coluna)['oc'].nunique()

        normais = real.loc[~real['abaixo_minimo']].copy()
        normais['apos'] = pd.to_datetime(normais['data_oc'], errors='coerce').dt.day > dia_corte
        soma = normais.groupby([coluna, 'apos'])[['metro_carregado', 'metro_padrao']].sum().unstack('apos', fill_value=0.0)
        if (('metro_carregado', True) in soma.columns) and (('metro_carregado', False) in soma.columns):
            ocup_ate = dividir(soma[('metro_carregado', False)], soma[('metro_padrao', False)])
            efeito = (soma[('metro_carregado', True)] - ocup_ate * soma[('metro_padrao', True)]) / total_pad
            parcelas['fechamento'] = efeito.where(ocup_ate.notna(), 0.0).clip(upper=0)
    for coluna_parcela in ('criticas', 'fechamento', 'ocs_criticas', 'ocs'):
        if coluna_parcela not in parcelas:
            parcelas[coluna_parcela] = 0.0
    parcelas[['criticas', 'fechamento', 'ocs_criticas', 'ocs', 'perfil']] = (
        parcelas[['criticas', 'fechamento', 'ocs_criticas', 'ocs', 'perfil']].fillna(0.0)
    )

    tipos = tipo_carregamento_por_cliente(df, coluna, meta).set_index(coluna)
    parcelas['classificacao_tipo'] = tipos['classificacao'].reindex(parcelas.index).fillna('Sem dados')
    parcelas['impacto_troca_pp'] = tipos['impacto_troca_pp'].reindex(parcelas.index)

    base = base.merge(parcelas.reset_index(), on=coluna, how='left')
    # perfil + criticas + fechamento + execucao = impacto na meta (exato).
    base['execucao'] = base['impacto_meta_pp'] - base['perfil'] - base['criticas'] - base['fechamento']

    componentes = base[['perfil', 'criticas', 'fechamento', 'execucao']]
    principal = componentes.idxmin(axis=1)
    acima = base['impacto_meta_pp'] >= 0
    base['causa_chave'] = np.where(acima, 'acima', principal)
    base['causa'] = np.where(acima, 'Na meta ou acima', principal.map(CAUSAS))
    base['acao'] = np.where(acima, 'Manter o padrão de carregamento.', principal.map(ACOES))
    return base


# ---------------------------------------------------------------------------
# Restricoes operacionais (particularidades)
# ---------------------------------------------------------------------------

RESTRICOES = {
    'nao_compartilha': 'Não aceita carga compartilhada',
    'veiculo_limitado': 'Veículo limitado (até truck/toco)',
    'nao_sobrepoe': 'Não aceita sobreposição',
    'palete_especial': 'Exige paletização especial',
}


def _texto(serie):
    return serie.astype('string').fillna('').map(lambda v: _sem_acento(str(v)).upper().strip())


def restricoes_por_codigo(particularidades):
    """Converte a planilha de particularidades em indicadores de restricao."""
    if particularidades.empty:
        return pd.DataFrame(columns=['cod_cliente', *RESTRICOES])
    p = particularidades
    compartilha = _texto(p.get('aceita_carga_compartilhada_cadastro', pd.Series(index=p.index, dtype=str)))
    compartilha_2 = _texto(p.get('carga_compartilhada', pd.Series(index=p.index, dtype=str)))
    veiculo = _texto(p.get('restricao_veiculo_cadastro', pd.Series(index=p.index, dtype=str)))
    veiculo_2 = _texto(p.get('restricao_veiculo', pd.Series(index=p.index, dtype=str)))
    resultado = pd.DataFrame({
        'cod_cliente': p['cod_cliente_filho'].astype(str),
        'nao_compartilha': compartilha.str.startswith('NAO') | compartilha_2.eq('NAO'),
        'veiculo_limitado': (
            veiculo.str.contains(r'\b(?:TRUCK|TOCO|VUC|VAN|3/4)\b', regex=True)
            | veiculo_2.str.contains(r'ATE (?:TRUCK|TOCO|VUC|VAN|3/4)', regex=True)
        ),
        'nao_sobrepoe': _texto(p.get('aceita_sobreposicao', pd.Series(index=p.index, dtype=str))).eq('NAO'),
        'palete_especial': _texto(p.get('paletizado_especial', pd.Series(index=p.index, dtype=str))).eq('SIM'),
    })
    return resultado.drop_duplicates('cod_cliente')


def restricoes_dos_clientes(df, restricoes, coluna='cliente_pai', corte=0.5):
    """Lista as restricoes de cada cliente (quando cobrem >= corte do volume dele)."""
    real = df.loc[df['visao'].eq('Real'), [coluna, 'cod_cliente', 'metro_padrao']]
    base = real.merge(restricoes, on='cod_cliente', how='left')
    pesos = {}
    for chave in RESTRICOES:
        marcado = base[chave].fillna(False).astype(bool)
        pesos[chave] = (base['metro_padrao'].where(marcado, 0.0)).groupby(base[coluna]).sum()
    total = base.groupby(coluna)['metro_padrao'].sum()
    tabela = pd.DataFrame({chave: dividir(valor, total) for chave, valor in pesos.items()})
    tabela['restricoes'] = tabela.apply(
        lambda linha: ', '.join(RESTRICOES[c] for c in RESTRICOES if linha[c] >= corte), axis=1,
    )
    return tabela.reset_index()


def ocupacao_por_restricao(df, restricoes, meta):
    """Ocupacao Real com x sem cada restricao (nivel codigo-filho)."""
    real = df.loc[df['visao'].eq('Real')].merge(restricoes, on='cod_cliente', how='left')
    total_pad = real['metro_padrao'].sum()
    linhas = []
    for chave, nome in RESTRICOES.items():
        marcado = real[chave].fillna(False).astype(bool)
        com, sem = real.loc[marcado], real.loc[~marcado]
        linhas.append({
            'restricao': nome,
            'ocupacao_com': dividir(com['metro_carregado'].sum(), com['metro_padrao'].sum()),
            'ocupacao_sem': dividir(sem['metro_carregado'].sum(), sem['metro_padrao'].sum()),
            'participacao_volume': dividir(com['metro_padrao'].sum(), total_pad),
            'impacto_meta_pp': dividir(com['metro_carregado'].sum() - meta * com['metro_padrao'].sum(), total_pad),
            'clientes': com['cliente_pai'].nunique(),
        })
    tabela = pd.DataFrame(linhas)
    tabela['diferenca_pp'] = tabela['ocupacao_com'] - tabela['ocupacao_sem']
    return tabela.sort_values('diferenca_pp')


# ---------------------------------------------------------------------------
# Ocupacao dia a dia (fechamento)
# ---------------------------------------------------------------------------

def ocupacao_por_dia(cargas_classificadas, visao):
    """Ocupacao diaria e acumulada por dia do mes (soma os meses do periodo)."""
    base = cargas_classificadas.loc[cargas_classificadas['visao'].eq(visao)].copy()
    if base.empty:
        return pd.DataFrame(columns=['dia', 'ocupacao_dia', 'ocupacao_acumulada', 'metro_carregado'])
    base['dia'] = pd.to_datetime(base['data_oc'], errors='coerce').dt.day
    dia = base.groupby('dia')[['metro_carregado', 'metro_padrao']].sum().reindex(range(1, 32), fill_value=0.0)
    dia['ocupacao_dia'] = dividir(dia['metro_carregado'], dia['metro_padrao'])
    acumulado = dia[['metro_carregado', 'metro_padrao']].cumsum()
    dia['ocupacao_acumulada'] = dividir(acumulado['metro_carregado'], acumulado['metro_padrao'])
    return dia.reset_index().rename(columns={'index': 'dia'})


# ---------------------------------------------------------------------------
# Evolucao mensal
# ---------------------------------------------------------------------------

def evolucao_mensal(dataframe):
    agrupado = (
        dataframe.groupby(['mes_numero', 'mes_nome', 'visao'])
        .agg(metro_carregado=('metro_carregado', 'sum'), metro_padrao=('metro_padrao', 'sum'))
        .reset_index()
    )
    agrupado['ocupacao'] = dividir(agrupado['metro_carregado'], agrupado['metro_padrao'])
    tabela = agrupado.pivot_table(
        index=['mes_numero', 'mes_nome'], columns='visao',
        values=['ocupacao', 'metro_carregado'], aggfunc='first',
    )
    tabela.columns = [f'{m}_{str(v).lower()}' for m, v in tabela.columns]
    tabela = tabela.reset_index().sort_values('mes_numero')
    for coluna in ('ocupacao_real', 'ocupacao_aa', 'metro_carregado_real', 'metro_carregado_aa'):
        if coluna not in tabela:
            tabela[coluna] = np.nan
    tabela['meta'] = tabela['ocupacao_aa'] + INCREMENTO_META_AUTOMATICA
    return tabela
