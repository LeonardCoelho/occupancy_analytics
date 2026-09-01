import pandas as pd
from config import RAW_DIR, PROCESSED_DIR

# LEITURA DOS DADOS

df_ocupacao = pd.read_excel(RAW_DIR / 'dados_ocupacao.xlsx', header=2)
df_clientes = pd.read_excel(RAW_DIR / 'dados_clientes.xlsx', header=2)

# FILTROS DE NEGÓCIO

tipos_excluir = ['ST']
df_ocupacao = df_ocupacao[~df_ocupacao['Tp. Or.'].isin(tipos_excluir)].copy()
df_real = df_ocupacao[df_ocupacao['Visão'] == 'Real'].copy()

# JOINS

df_ocupacao = df_ocupacao.merge(df_clientes, on='Cod cliente', how='left', validate='many_to_one')

# VALIDAÇÃO

ocupacao_geral_real = (df_real['m³ carregado'].sum() / df_real['m³ padrão'].sum())
linhas_sem_correspondencia = df_ocupacao['Cliente'].isna().sum()
clientes_sem_correspondencia = df_ocupacao.loc[df_ocupacao['Cliente'].isna(), 'Cod cliente'].nunique()

print(f'Registros de ocupação real: {len(df_real):,}')
print(f'Registros iniciais: {len(df_ocupacao):,}')
print(f'Ocupação real: {ocupacao_geral_real:.4%}')
print(f'Linhas sem correspondência: {linhas_sem_correspondencia:,}')
print(f'Clientes único sem correspondência: {clientes_sem_correspondencia:,}')

# EXPORTAÇÃO

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
df_ocupacao.to_parquet(PROCESSED_DIR / 'df_ocupacao.parquet', index=False)

print(f'Arquivo de ocupação exportado para {PROCESSED_DIR}')