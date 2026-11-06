"""Testes das regras de calculo com dados sinteticos.

    python -m pytest tests      (ou)      python tests/test_calculos.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import calculos as calc  # noqa: E402


def _linha(cliente, visao, tipo, car, pad, mes=1, uf='SP'):
    return {
        'cliente_pai': cliente, 'cliente_unidade': cliente, 'cod_cliente': cliente, 'visao': visao,
        'tipo_carregamento': tipo, 'metro_carregado': car, 'metro_padrao': pad, 'frete_total': 0.0,
        'mes_numero': mes, 'mes_nome': 'Janeiro', 'uf': uf, 'perfil_veiculo': 'TRUCK SECO',
    }


def base_exemplo():
    return pd.DataFrame([
        _linha('A', 'AA', 'Estivado', 80, 100),
        _linha('A', 'Real', 'Paletizado', 60, 100),     # troca integral, piorou
        _linha('B', 'AA', 'Paletizado', 50, 100),
        _linha('B', 'Real', 'Paletizado', 70, 200),     # cresceu
        _linha('C', 'AA', 'Estivado', 30, 50),
        _linha('C', 'AA', 'Paletizado', 20, 50),
        _linha('C', 'Real', 'Estivado', 40, 60),        # misto
        _linha('C', 'Real', 'Paletizado', 10, 40),
        _linha('D', 'Real', 'Estivado', 9, 10),         # novo no Real
        _linha('E', 'AA', 'Estivado', 5, 10),           # sumiu no Real
    ])


def test_ocupacao_ponderada():
    total = calc.totais_visao(pd.DataFrame([_linha('A', 'Real', 'Estivado', 1, 2), _linha('B', 'Real', 'Estivado', 80, 100)]), 'Real')
    assert np.isclose(total['ocupacao'], 81 / 102)


def test_meta_automatica():
    assert np.isclose(calc.calcular_meta(0.6574), 0.6624)
    assert calc.calcular_meta(0.6574, modo_automatico=False, meta_manual=0.7) == 0.7


def test_impacto_meta_e_contribuicao_somam_exatamente():
    df = base_exemplo()
    real = calc.totais_visao(df, 'Real')['ocupacao']
    aa = calc.totais_visao(df, 'AA')['ocupacao']
    meta = calc.calcular_meta(aa)
    comp = calc.comparativo_grupo(df, 'cliente_pai', meta)
    assert np.isclose(comp['impacto_meta_pp'].sum(), real - meta)
    assert np.isclose(comp['contribuicao_aa_pp'].sum(), real - aa)
    assert np.allclose(comp['efeito_ocupacao_pp'] + comp['efeito_composicao_pp'], comp['contribuicao_aa_pp'])
    status = comp.set_index('cliente_pai')['status']
    assert status['D'] == 'Novo no Real' and status['E'] == 'Sem movimento no Real'


def test_classificacao_troca_integral():
    df = base_exemplo()
    tab = calc.tipo_carregamento_por_cliente(df, 'cliente_pai', 0.6).set_index('cliente_pai')
    assert tab.loc['A', 'classificacao'] == 'Troca integral: Estivado → Paletizado'
    assert tab.loc['B', 'classificacao'] == 'Sem mudança de tipo'
    assert tab.loc['C', 'classificacao'] == 'Composição mista'
    assert pd.isna(tab.loc['C', 'impacto_troca_pp'])
    # A: peso Real 100/410 x (60% - 80%)
    assert np.isclose(tab.loc['A', 'impacto_troca_pp'], 100 / 410 * (0.6 - 0.8))
    # Contribuicoes de representatividade somam a variacao global.
    global_ = calc.analise_tipo_carregamento(df)['detalhe'].set_index('tipo_carregamento')
    assert np.isclose(tab['contrib_repr_paletizado_pp'].sum(), global_.loc['Paletizado', 'variacao_representatividade_pp'])


def test_aliases_de_perfil():
    esperado = {
        'VAN REFRIGERADA': 'VAN (R)', 'VAN SECO': 'VAN (S)', 'VUC REFRIGERADO': 'VUC (R)',
        'VUC SECO': 'VUC (S)', '3/4 REFRIGERADO': 'F-4000 (R)', '3/4 SECO': 'F-4000 (S)',
        'TOCO REFRIGERADO': 'TOCO (R)', 'TOCO SECO': 'TOCO (S)', 'TRUCK REFRIGERADO': 'TRUCK (R)',
        'TRUCK SECO': 'TRUCK (S)', 'CARRETA REFRIGERADA': 'CARRETA (R)', 'CARRETA SECA': 'CARRETA (S)',
        'BI TREM SECO': 'BI TREM', ' toco  seco ': 'TOCO (S)', 'F-4000 (R)': 'F-4000 (R)',
    }
    for origem, destino in esperado.items():
        assert calc.normalizar_perfil(origem) == destino, origem


def test_oc_compartilhada_nao_vira_critica():
    # Uma carreta com 3 clientes: cada um com pouco volume, mas a carga esta 90% cheia.
    cargas = pd.DataFrame([
        {'oc': 1, 'visao': 'Real', 'cod_cliente': c, 'perfil_veiculo': 'CARRETA SECA',
         'metro_carregado': 25.5, 'metro_padrao': 85 / 3, 'data_oc': pd.Timestamp('2026-01-05')}
        for c in ('X', 'Y', 'Z')
    ] + [
        {'oc': 2, 'visao': 'Real', 'cod_cliente': 'W', 'perfil_veiculo': 'VAN SECO',
         'metro_carregado': 2.0, 'metro_padrao': 6.0, 'data_oc': pd.Timestamp('2026-01-25')}
    ])
    total = cargas['metro_padrao'].sum()
    res = calc.classificar_cargas(cargas, calc.preparar_limites(), {'Real': total})
    por_oc = res.groupby('oc')['abaixo_minimo'].first()
    assert not por_oc[1] and por_oc[2]
    assert np.isclose(res['deficit_minimo_m3'].sum(), 0.5 * 6 - 2)
    assert np.isclose(res['efeito_minimo_pp'].sum(), -(1.0) / total)


def test_bridge_parte_da_meta_e_fecha_no_real():
    b = calc.calcular_bridge(0.6707, 0.6659, 0.6757, -0.0027, -0.0032, -0.0031)
    assert b['etapas'][0] == ('Meta', 0.6757, 'absolute')
    soma = b['etapas'][0][1] + sum(v for _, v, m in b['etapas'] if m == 'relative')
    assert np.isclose(soma, 0.6659)
    nomes = [n for n, _, _ in b['etapas']]
    assert nomes == ['Meta', 'Tipo de carregamento', 'Fechamento do mês', 'Cargas abaixo do mínimo',
                     'Demais efeitos', 'Ocupação Real']
    assert np.isclose(b['demais_pp'], (0.6659 - 0.6757) - (-0.0027 - 0.0032 - 0.0031))


def test_bridge_esconde_motivo_que_ajudou():
    b = calc.calcular_bridge(0.67, 0.66, 0.675, -0.003, 0.001, -0.004)
    nomes = [n for n, _, _ in b['etapas']]
    assert 'Cargas abaixo do mínimo' not in nomes
    soma = b['etapas'][0][1] + sum(v for _, v, m in b['etapas'] if m == 'relative')
    assert np.isclose(soma, 0.66)


def test_mudanca_de_tipo_por_cliente():
    df = base_exemplo()
    tab = calc.tipo_carregamento_por_cliente(df, 'cliente_pai', 0.6).set_index('cliente_pai')
    # A passou de 0% para 100% paletizado: peso 100/410 x (+1) x (ocup. pal. - ocup. est.)
    real = df.loc[df['visao'].eq('Real')]
    pal = real.loc[real['tipo_carregamento'].eq('Paletizado')]
    est = real.loc[real['tipo_carregamento'].eq('Estivado')]
    dif = pal['metro_carregado'].sum() / pal['metro_padrao'].sum() - est['metro_carregado'].sum() / est['metro_padrao'].sum()
    assert np.isclose(tab.loc['A', 'impacto_mudanca_tipo_pp'], 100 / 410 * 1.0 * dif)
    assert pd.isna(tab.loc['D', 'impacto_mudanca_tipo_pp'])  # novo no Real


def test_criticas_separadas_por_periodo_sem_sobreposicao():
    cargas = pd.DataFrame([
        {'oc': 1, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'VAN SECO', 'metro_carregado': 1, 'metro_padrao': 6, 'data_oc': pd.Timestamp('2026-01-10')},
        {'oc': 2, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'VAN SECO', 'metro_carregado': 2, 'metro_padrao': 6, 'data_oc': pd.Timestamp('2026-01-25')},
        {'oc': 3, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'VAN SECO', 'metro_carregado': 5, 'metro_padrao': 6, 'data_oc': pd.Timestamp('2026-01-26')},
    ])
    res = calc.classificar_cargas(cargas, calc.preparar_limites(), {'Real': 18})
    per = calc.criticas_por_periodo(res, 'Real')
    assert np.isclose(per['ate_pp'], -(3 - 1) / 18) and np.isclose(per['apos_pp'], -(3 - 2) / 18)
    assert np.isclose(per['ate_pp'] + per['apos_pp'], calc.resumo_cargas_criticas(res, 'Real')['efeito_pp'])


def test_fechamento_sem_criticas():
    cargas = pd.DataFrame([
        {'oc': 1, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'TRUCK SECO', 'metro_carregado': 30, 'metro_padrao': 40, 'data_oc': pd.Timestamp('2026-01-10')},
        {'oc': 2, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'TRUCK SECO', 'metro_carregado': 20, 'metro_padrao': 40, 'data_oc': pd.Timestamp('2026-01-25')},
        {'oc': 3, 'visao': 'Real', 'cod_cliente': 'A', 'perfil_veiculo': 'TRUCK SECO', 'metro_carregado': 10, 'metro_padrao': 40, 'data_oc': pd.Timestamp('2026-01-28')},
    ])
    total = 120
    res = calc.classificar_cargas(cargas, calc.preparar_limites(), {'Real': total})
    f = calc.analise_fechamento(res, 'Real', total)
    assert np.isclose(f['impacto_pp'], (30 - 0.75 * 80) / total)
    # OC 3 (25%) esta abaixo do minimo e sai da conta; OC 2 (50%) fica.
    assert np.isclose(f['impacto_sem_criticas_pp'], (20 - 0.75 * 40) / total)


def test_diagnostico_parcelas_somam_o_impacto():
    df = base_exemplo()
    meta = calc.calcular_meta(calc.totais_visao(df, 'AA')['ocupacao'])
    cargas = df.loc[df['visao'].eq('Real')].assign(
        oc=range(5), data_oc=pd.Timestamp('2026-01-10'),
    )
    total = calc.totais_visao(df, 'Real')['metro_padrao']
    classificadas = calc.classificar_cargas(cargas, calc.preparar_limites(), {'Real': total})
    diag = calc.diagnostico_clientes(df, classificadas, meta)
    soma = diag[['perfil', 'criticas', 'fechamento', 'execucao']].sum(axis=1)
    assert np.allclose(soma, diag['impacto_meta_pp'])
    assert set(diag['causa']) <= set(calc.CAUSAS.values()) | {'Na meta ou acima'}


def test_restricoes_e_ocupacao_por_restricao():
    part = pd.DataFrame({
        'cod_cliente_filho': ['A', 'B'],
        'aceita_carga_compartilhada_cadastro': ['NÃO', 'SIM'],
        'restricao_veiculo_cadastro': ['ATÉ TRUCK', 'ATÉ CARRETA'],
        'aceita_sobreposicao': ['NÃO', 'SIM'],
        'paletizado_especial': ['SIM', 'NÃO'],
    })
    r = calc.restricoes_por_codigo(part).set_index('cod_cliente')
    assert r.loc['A'].all() and not r.loc['B'].any()
    df = base_exemplo()
    tabela = calc.ocupacao_por_restricao(df, r.reset_index(), 0.6).set_index('restricao')
    linha = tabela.loc[calc.RESTRICOES['nao_compartilha']]
    assert np.isclose(linha['ocupacao_com'], 60 / 100)
    assert np.isclose(linha['ocupacao_sem'], (70 + 50 + 9) / (200 + 100 + 10))


def test_ocupacao_por_dia_acumulada():
    cargas = pd.DataFrame([
        {'oc': 1, 'visao': 'Real', 'data_oc': pd.Timestamp('2026-01-01'), 'metro_carregado': 8, 'metro_padrao': 10},
        {'oc': 2, 'visao': 'Real', 'data_oc': pd.Timestamp('2026-02-01'), 'metro_carregado': 6, 'metro_padrao': 10},
        {'oc': 3, 'visao': 'Real', 'data_oc': pd.Timestamp('2026-01-25'), 'metro_carregado': 2, 'metro_padrao': 10},
    ])
    dia = calc.ocupacao_por_dia(cargas, 'Real').set_index('dia')
    assert np.isclose(dia.loc[1, 'ocupacao_dia'], 0.7)
    assert np.isclose(dia.loc[24, 'ocupacao_acumulada'], 0.7)
    assert np.isclose(dia.loc[31, 'ocupacao_acumulada'], 16 / 30)


def test_referencia_do_perfil_exclui_o_proprio_cliente():
    df = pd.DataFrame([
        _linha('A', 'Real', 'Estivado', 50, 100),
        _linha('B', 'Real', 'Estivado', 90, 100),
    ])
    diag = calc.diagnostico_clientes(df, pd.DataFrame(), 0.7).set_index('cliente_pai')
    assert np.isclose(diag.loc['A', 'ocupacao_referencia'], 0.9)
    assert np.isclose(diag.loc['B', 'ocupacao_referencia'], 0.5)


def test_impacto_somavel_fecha_na_distancia_para_a_meta():
    df = base_exemplo()
    real = calc.totais_visao(df, 'Real')['ocupacao']
    meta = calc.calcular_meta(calc.totais_visao(df, 'AA')['ocupacao'])
    comp = calc.comparativo_grupo(df, 'cliente_pai', meta)
    assert np.isclose(calc.impacto_meta_somavel(comp).sum(), real - meta)
    assert np.isclose(calc.impacto_meta_somavel(comp, automatica=False).sum(), real - meta)


if __name__ == '__main__':
    for nome, funcao in list(globals().items()):
        if nome.startswith('test_'):
            funcao()
            print(f'ok  {nome}')
