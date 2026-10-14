import numpy as np
import pandas as pd


def _normalizar_codigo(valor):
    if pd.isna(valor):
        return pd.NA
    texto = str(valor).strip().replace("'", '')
    if texto.endswith('.0'):
        texto = texto[:-2]
    digitos = ''.join(c for c in texto if c.isdigit())
    return digitos or pd.NA


def gerar_bases_diagnostico(df_ocupacao, raw_dir, processed_dir, meses):
    arquivo_cargas = processed_dir / 'ocupacao_cargas.parquet'
    dimensoes = [
        'OC', 'Data OC', 'Cliente curto', 'Cod cliente', 'Pai curto - cod',
        'Visão', 'Filial/Fábrica', 'Região', 'Território', 'Canal',
        'Cidade', 'UF', 'Perfil veículo', 'Tipo carregto', 'Tipo produto',
        'Tp. Or.', 'Cod Transportadora'
    ]
    cargas = (
        df_ocupacao.groupby(dimensoes, dropna=False)
        .agg(
            metro_carregado=('m³ carregado', 'sum'),
            metro_padrao=('m³ padrão', lambda c: c.sum(min_count=1)),
            frete_total=('R$ frete', 'sum')
        )
        .reset_index()
    )
    cargas['ocupacao'] = np.where(
        cargas['metro_padrao'].notna() & cargas['metro_padrao'].gt(0),
        cargas['metro_carregado'] / cargas['metro_padrao'],
        np.nan
    )
    cargas['mes_numero'] = cargas['Data OC'].dt.month
    cargas['mes_nome'] = cargas['mes_numero'].map(meses)
    cargas = cargas.rename(columns={
        'OC': 'oc', 'Data OC': 'data_oc', 'Cliente curto': 'cliente_unidade',
        'Cod cliente': 'cod_cliente', 'Pai curto - cod': 'cliente_pai',
        'Visão': 'visao', 'Filial/Fábrica': 'cd_origem', 'Região': 'regiao',
        'Território': 'territorio', 'Canal': 'canal', 'Cidade': 'cidade',
        'UF': 'uf', 'Perfil veículo': 'perfil_veiculo',
        'Tipo carregto': 'tipo_carregamento', 'Tipo produto': 'tipo_produto',
        'Tp. Or.': 'tipo_ordem', 'Cod Transportadora': 'cod_transportadora'
    })
    cargas.to_parquet(arquivo_cargas, index=False)
    print(f'Base detalhada por OC exportada para: {arquivo_cargas}')

    origem = raw_dir / 'particularidade_clientes.xlsx'
    destino = processed_dir / 'particularidades_clientes.parquet'
    if not origem.exists():
        print(f'Aviso: particularidades nao encontradas em {origem}')
        return

    bruto = pd.read_excel(origem, sheet_name='Hoja1', header=3)
    mapa = {
        3: 'status_cliente', 4: 'cod_cliente_pai', 5: 'cod_cliente_filho',
        6: 'cliente_particularidade', 7: 'uf_particularidade',
        8: 'cidade_particularidade', 10: 'canal_particularidade',
        11: 'territorio_particularidade', 12: 'paletizado_especial',
        13: 'itens_por_palete', 14: 'altura_maxima',
        15: 'aceita_sobreposicao', 16: 'restricao_veiculo_cadastro',
        17: 'janela_entrega', 21: 'aceita_carga_compartilhada_cadastro',
        22: 'aceita_arcor_bagley', 23: 'observacoes_operacionais',
        24: 'cd_faturamento', 30: 'agendado', 31: 'tipo_agendamento',
        35: 'particularidade_agendamento', 39: 'aceita_backorder',
        40: 'pedido_expira', 41: 'prazo_expiracao_dias',
        42: 'informacoes_extras', 43: 'qtd_ajudantes',
        44: 'horario_recebimento', 45: 'paga_gnre', 46: 'shelf_life',
        47: 'laudo_tecnico', 49: 'restricao_veiculo',
        50: 'carga_compartilhada', 63: 'regra_de_ouro',
        66: 'data_atualizacao', 69: 'informacoes_operacoes'
    }
    mapa = {i: nome for i, nome in mapa.items() if i < bruto.shape[1]}
    particularidades = bruto.iloc[:, list(mapa)].copy()
    particularidades.columns = list(mapa.values())
    for coluna in ['cod_cliente_pai', 'cod_cliente_filho']:
        particularidades[coluna] = particularidades[coluna].map(_normalizar_codigo)
    particularidades = (
        particularidades.loc[particularidades['cod_cliente_filho'].notna()]
        .drop_duplicates('cod_cliente_filho', keep='last')
        .reset_index(drop=True)
    )
    # A planilha mistura texto e numeros em algumas colunas. Padronizar como
    # texto evita falha de serializacao e preserva o conteudo operacional.
    for coluna in particularidades.select_dtypes(include='object').columns:
        particularidades[coluna] = particularidades[coluna].astype('string')
    particularidades.to_parquet(destino, index=False)
    print(f'Particularidades sanitizadas exportadas para: {destino}')
