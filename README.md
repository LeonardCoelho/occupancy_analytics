
# Occupancy Analytics

Dashboard interativo e pipeline de dados para análise da ocupação logística por cliente.

A solução utiliza Python, pandas, Streamlit e Plotly para transformar dados operacionais em indicadores, filtros e visualizações que apoiam a identificação de clientes com alto volume carregado e ocupação abaixo da meta.

> Os dados corporativos utilizados no desenvolvimento não são disponibilizados neste repositório. Arquivos de entrada, bases processadas e relatórios gerados são ignorados pelo Git.

## Objetivo

O projeto foi desenvolvido para analisar a ocupação logística em diferentes níveis de cliente:

```text
Cliente-pai
    ↓
Cliente/unidade
    ↓
Código-filho
```

A análise começa em uma visão macro por cliente-pai, permitindo identificar os grupos com maior volume e ocupação abaixo da meta.

Depois, o usuário pode abrir o detalhamento por unidade e código-filho para investigar quais operações estão influenciando o resultado.

## Problema de negócio

Uma média simples dos percentuais de ocupação pode gerar resultados incorretos, pois considera operações pequenas e grandes com o mesmo peso.

Por esse motivo, a ocupação é calculada com base nos volumes totais:

```text
Ocupação = soma do m³ carregado ÷ soma do m³ padrão
```

Exemplo:

```text
Operação A: 1 m³ carregado ÷ 2 m³ padrão = 50%
Operação B: 80 m³ carregados ÷ 100 m³ padrão = 80%
```

A média simples seria:

```text
(50% + 80%) ÷ 2 = 65%
```

O cálculo correto é:

```text
(1 + 80) ÷ (2 + 100)
81 ÷ 102 = 79,41%
```

No dashboard, o indicador é recalculado após cada filtro utilizando os volumes do conjunto selecionado.

## Funcionalidades

- Extração de dados provenientes de arquivos Excel
- Tratamento e enriquecimento cadastral dos clientes
- Exclusão de operações fora do escopo da análise
- Tratamento de valores nulos e denominadores inválidos
- Persistência dos dados processados em Parquet
- Comparação entre período Real e ano anterior
- Consolidação de alterações de código pela unidade logística
- Dashboard interativo criado com Streamlit
- Visualizações interativas criadas com Plotly
- Filtros por período, CD e dimensões operacionais
- Visão macro por cliente-pai
- Detalhamento por cliente/unidade
- Detalhamento por código-filho
- Identificação de clientes com alto volume abaixo da meta
- Exportação dos dados filtrados em CSV
- Geração de relatório auxiliar em Excel
- Validações automáticas de qualidade dos dados

## Dashboard

O dashboard apresenta os seguintes indicadores:

- Ocupação ponderada
- m³ carregados
- m³ padrão
- Frete total
- Quantidade de unidades
- Quantidade de códigos de cliente

### Visão por cliente-pai

O gráfico principal permite identificar:

- clientes-pai com maior volume carregado;
- clientes-pai abaixo da meta de ocupação;
- quantidade de unidades pertencentes ao agrupamento;
- quantidade de códigos-filhos;
- volume padrão;
- frete total.

As barras representam o volume carregado e os marcadores representam a ocupação ponderada.

A classificação visual utiliza:

```text
Vermelho: ocupação abaixo da meta
Azul: ocupação igual ou acima da meta
```

### Detalhamento

Após selecionar um cliente-pai, o dashboard apresenta:

- ocupação consolidada do cliente-pai;
- diferença em relação à meta;
- volume carregado;
- quantidade de unidades;
- quantidade de códigos-filhos;
- frete total;
- gráfico por cliente/unidade;
- tabela consolidada por código-filho;
- dados operacionais detalhados.

## Filtros disponíveis

### Filtros principais

- Visão
- Mês
- CD de origem

### Filtros adicionais

- Cliente-pai
- Cliente/unidade
- Código do cliente
- Território
- Canal
- Perfil do veículo
- Tipo de carregamento
- Tipo de produto
- Tipo de ordem
- UF

Quando um filtro adicional fica vazio, o dashboard considera todos os valores daquela dimensão.

## Arquitetura do pipeline

```text
Arquivos de origem em Excel
            ↓
        extract.py
            ↓
   df_ocupacao.parquet
            ↓
       transform.py
            ↓
 ┌───────────────────────────────┐
 ↓                               ↓
ocupacao_analitica.parquet       ocupacao_por_unidade.parquet
 ↓                               ↓
Dashboard Streamlit              output.py
                                 ↓
                       Relatório auxiliar em Excel
```

## Etapas do processamento

### Extração

O arquivo `src/extract.py` é responsável por:

1. Ler os arquivos de origem;
2. Remover operações fora do escopo;
3. Enriquecer a base com informações cadastrais;
4. Validar registros sem correspondência;
5. Validar a ocupação geral;
6. Exportar a base tratada em Parquet.

### Transformação

O arquivo `src/transform.py` é responsável por:

1. Validar o campo de m³ padrão;
2. Proteger o cálculo contra valores nulos ou inválidos;
3. Criar as dimensões de período;
4. Criar a base analítica para filtros;
5. Consolidar os dados por cliente e visão;
6. Comparar Real e ano anterior;
7. Calcular a variação em pontos percentuais;
8. Classificar as unidades;
9. Validar os totais processados;
10. Exportar as bases finais em Parquet.

### Apresentação

O arquivo `app.py` é responsável por:

1. Carregar a base analítica;
2. Criar os filtros interativos;
3. Recalcular os indicadores;
4. Criar a visão macro por cliente-pai;
5. Permitir o detalhamento por unidade;
6. Apresentar os códigos-filhos;
7. Exibir os dados operacionais;
8. Disponibilizar o download dos dados filtrados.

O arquivo `src/output.py` permanece como uma saída auxiliar para geração do relatório em Excel.

## Estrutura do projeto

```text
occupancy_analytics/
├── app.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── output/
├── src/
│   ├── config.py
│   ├── extract.py
│   ├── transform.py
│   └── output.py
├── requirements.txt
├── .gitignore
└── README.md
```

As pastas de dados não são versionadas, pois podem conter informações corporativas.

## Tecnologias utilizadas

- Python
- pandas
- NumPy
- Streamlit
- Plotly
- OpenPyXL
- PyArrow
- Parquet
- Git
- GitHub

## Qualidade dos dados

O pipeline possui verificações para:

- quantidade de registros recebidos;
- distribuição entre Real e ano anterior;
- valores nulos em m³ padrão;
- valores iguais a zero em m³ padrão;
- valores negativos em m³ padrão;
- preservação dos registros;
- preservação do total de m³ carregado;
- preservação do total de m³ padrão;
- preservação do frete total;
- duplicidade na granularidade final;
- registros sem correspondência cadastral;
- distribuição dos status de comparação.

As validações interrompem o processamento quando uma inconsistência crítica é identificada.

## Observação sobre quantidade de ordens

A quantidade de ordens é uma métrica não aditiva.

Uma mesma ordem pode aparecer em diferentes combinações de:

- produto;
- perfil do veículo;
- tipo de carregamento;
- código do cliente;
- unidade;
- transportadora.

Por esse motivo, a soma das quantidades agrupadas não representa necessariamente a quantidade distinta de ordens.

Uma evolução planejada é criar uma base específica no nível da ordem para permitir contagens distintas com filtros flexíveis.

## Como executar o projeto

### Pré-requisitos

- Python 3.11 ou superior
- Git
- Ambiente virtual Python

### 1. Clonar o repositório

```bash
git clone https://github.com/LeonardCoelho/occupancy_analytics.git
cd occupancy_analytics
```

### 2. Criar o ambiente virtual

No Windows PowerShell:

```powershell
python -m venv .venv
```

### 3. Ativar o ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Se a execução de scripts estiver bloqueada no PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar as dependências

```powershell
python -m pip install -r requirements.txt
```

### 5. Preparar os dados

Os arquivos de origem devem ser colocados em:

```text
data/raw/
```

> Os arquivos originais não são disponibilizados neste repositório por conterem dados corporativos.

### 6. Executar a extração

```powershell
python src/extract.py
```

### 7. Executar a transformação

```powershell
python src/transform.py
```

### 8. Executar o dashboard

```powershell
python -m streamlit run app.py
```

O Streamlit normalmente abrirá no endereço:

```text
http://localhost:8501
```

### 9. Gerar o relatório auxiliar em Excel

```powershell
python src/output.py
```

## Segurança e privacidade

Este projeto foi desenvolvido a partir de uma necessidade real de análise logística, mas os dados corporativos não fazem parte do repositório.

Não são versionados:

- arquivos Excel de origem;
- arquivos CSV;
- arquivos Parquet;
- relatórios gerados;
- nomes e códigos reais de clientes;
- dados operacionais;
- custos de frete;
- credenciais;
- variáveis de ambiente.

Uma versão pública e executável será disponibilizada futuramente utilizando somente dados sintéticos e nomes fictícios.

## Roadmap

- [X] Estruturar o pipeline do projeto
- [X] Criar processo de extração
- [X] Criar processo de transformação
- [X] Persistir dados em Parquet
- [X] Validar a ocupação ponderada
- [X] Consolidar mudanças cadastrais pela unidade
- [X] Criar relatório auxiliar em Excel
- [X] Criar dashboard em Streamlit
- [X] Adicionar filtros operacionais
- [X] Criar visão macro por cliente-pai
- [X] Criar detalhamento por unidade
- [X] Criar detalhamento por código-filho
- [X] Identificar clientes de alto volume abaixo da meta
- [X] Adicionar exportação dos dados filtrados
- [ ] Adicionar comparação visual entre Real e ano anterior
- [ ] Adicionar evolução mensal da ocupação
- [ ] Criar base específica no nível da ordem
- [ ] Adicionar testes automatizados
- [ ] Refatorar o dashboard em módulos
- [ ] Criar dados sintéticos para demonstração
- [ ] Adicionar imagens da versão sintética
- [ ] Publicar demonstração no Streamlit Community Cloud

## Próximas evoluções

As próximas etapas previstas são:

1. Comparação de ocupação entre Real e ano anterior;
2. Variação em pontos percentuais por cliente-pai;
3. Evolução mensal da ocupação;
4. Ranking de maiores quedas e evoluções;
5. Base detalhada no nível da ordem;
6. Testes automatizados;
7. Separação do aplicativo em módulos;
8. Geração de dados sintéticos;
9. Publicação de uma demonstração online.

## Aprendizados do projeto

O desenvolvimento deste projeto envolveu conceitos de:

- ETL;
- qualidade de dados;
- granularidade;
- enriquecimento cadastral;
- métricas ponderadas;
- medidas não aditivas;
- modelagem analítica;
- persistência em Parquet;
- criação de aplicações de dados;
- filtros interativos;
- visualização de dados;
- versionamento com Git.

## Autor

**Leonardo Coelho**

Projeto desenvolvido como parte dos estudos e da evolução profissional em Python, Engenharia de Dados e Analytics Engineering.
