
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

- Pipeline Excel → Parquet com validação de totais (m³ carregado, m³ padrão e frete)
- Comparação Real × AA no mesmo período (acumulado ou mês)
- Meta automática = ocupação AA do recorte + 0,50 p.p. (ou manual)
- Bridge do AA ao Real que fecha exatamente no Real
- Impacto de cada cliente na meta e na variação Real × AA
- Paletizado × Estivado: efeito da composição, trocas integrais por cliente e quem mudou a representatividade
- Cargas (OCs) abaixo da ocupação mínima por perfil, com justificativas
- Efeito do fechamento do mês (cargas após o dia 20)
- Diagnóstico cliente-pai → código-filho → OC, com particularidades operacionais
- Mapa clicável por UF e heatmap UF × perfil
- Evolução mensal Real × AA × meta
- Exportação da base filtrada

## Painel

Os filtros da barra lateral (período, CD, filtros adicionais e meta) valem para todas as páginas.
Os mesmos filtros são aplicados à base analítica e à base por OC.

Fluxo: **estado → resultado → clientes que mais tiram da meta → códigos-filhos → OCs**.

| Página | Conteúdo |
|---|---|
| Resultado | Indicadores, mapa clicável (o estado escolhido filtra todo o painel), bridge meta → Real só com os motivos que afastaram da meta, evolução mensal |
| Clientes | Volume × ocupação lado a lado, restrições que explicam a ocupação, causa principal e ação sugerida; clique no cliente → códigos-filhos → particularidades → cargas |
| Cargas e fechamento | Ocupação dia a dia (até o dia 20 × fechamento), OCs abaixo do mínimo com impacto na meta: cliente → código-filho → OCs |
| Paletizado × Estivado | Efeito da composição, ocupação de cada tipo e clientes que passaram a paletizar ou a estivar mais (% paletizado AA → Real) |

**Regras adicionais**
- Linhas sem m³ padrão (8 na base atual) ficam fora da ocupação — antes o m³ carregado delas entrava no numerador.
- A referência do perfil compara o cliente com os **outros** clientes no mesmo tipo de carregamento e veículo.
- Restrições vêm da planilha de particularidades: não aceita carga compartilhada, veículo limitado, não aceita sobreposição e paletização especial.

**Causa principal do cliente** (`calculos.diagnostico_clientes`): o impacto na meta é separado em
*perfil de carga* (o tipo de carregamento e o veículo do cliente, avaliados pela média do painel, ficam abaixo da meta),
*cargas abaixo do mínimo*, *fechamento do mês* e *carregamento abaixo do padrão* (pior que outros clientes no mesmo tipo e veículo).
As parcelas somam exatamente o impacto; a mais negativa vira a causa e define a ação sugerida.

## Regras de cálculo

Todas as regras estão em `src/calculos.py` e cobertas por testes em `tests/`.

**Ocupação** = Σ m³ carregado ÷ Σ m³ padrão (nunca média de percentuais).

**Impacto na meta** de um grupo (cliente, filho, OC) =
`(m³ carregado − meta × m³ padrão) ÷ m³ padrão total do painel`.
A soma de todos os grupos é exatamente `Real − meta`.

**Contribuição Real × AA** de um grupo =
`peso_Real × (ocup_Real − Ocup_AA_total) − peso_AA × (ocup_AA − Ocup_AA_total)`,
com peso = participação no m³ padrão. A soma de todos os grupos é exatamente `Real − AA`.
Divide-se em *por ocupação* (`peso_Real × (ocup_Real − ocup_AA)`) e *por volume* (resto).

**Tipo de carregamento** = `Σ ocup_Real,tipo × (repr_Real,tipo − repr_AA,tipo)`.
Troca integral: ≥ 95% de um tipo no AA e ≥ 95% do outro no Real; impacto = efeito por ocupação do cliente.
Clientes mistos não recebem cálculo de troca.

**Cargas abaixo do mínimo**: a ocupação da OC usa a carga inteira (Σ carregado ÷ Σ padrão da OC),
então uma OC compartilhada por vários clientes não é marcada como crítica só porque cada parte é pequena.
Déficit = mínimo do perfil × m³ padrão − m³ carregado; perda = −déficit ÷ m³ padrão total.

**Pós-dia 20** = `(carregado_após − ocup_até20 × padrão_após) ÷ m³ padrão total`.
No bridge entra a versão sem as OCs abaixo do mínimo, para não contar duas vezes.

**Bridge** (meta → Real, por que não chegamos): cada barra é quanto a ocupação seria maior se o problema não tivesse acontecido — *tipo de carregamento* (proporção paletizado/estivado do AA), *fechamento do mês* (cargas após o dia 20 com a ocupação das cargas até o dia 20) e *cargas abaixo do mínimo* (cargas até o dia 20 levadas ao mínimo do veículo). Os grupos de OCs não se sobrepõem; motivos que ajudaram não aparecem; *demais efeitos* é o resíduo que fecha no Real.

## Arquitetura

```text
data/raw/*.xlsx
      ↓  src/extract.py
df_ocupacao.parquet
      ↓  src/transform.py  (+ src/diagnostico.py)
ocupacao_analitica.parquet   ocupacao_cargas.parquet   particularidades_clientes.parquet
      ↓
app.py  →  filtros + contexto  →  app_pages/*.py
             src/calculos.py (regras)   src/graficos.py (Plotly + formatação)
```

## Estrutura do projeto

```text
occupancy_analytics/
├── app.py                    # entrada: dados, filtros, navegação
├── app_pages/                # uma página por tema
├── src/
│   ├── atualizar_bases.py    # extract + transform em um comando
│   ├── calculos.py           # regras de negócio (sem Streamlit)
│   ├── graficos.py           # gráficos e formatação
│   ├── config.py, extract.py, transform.py, diagnostico.py, output.py
├── tests/test_calculos.py
├── scripts/iniciar_painel.bat
├── .streamlit/config.toml    # porta 8524, acesso pela rede
└── data/                     # não versionado
```

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

### 6. Atualizar as bases

```powershell
python src/atualizar_bases.py
```

Roda a extração e a transformação em sequência. O painel percebe sozinho que os Parquets mudaram (não precisa limpar cache).

### 7. Executar o dashboard

```powershell
python -m streamlit run app.py
```

A porta e o acesso pela rede ficam em `.streamlit/config.toml` (porta 8524). Para manter rodando e reiniciar se cair, use `scripts/iniciar_painel.bat`.

### Deixar o painel sempre no ar (PC da operação)

- Link para o time: `http://<nome-do-pc>:8524` (o nome do PC não muda quando o IP muda).
- A tarefa **Painel Ocupacao** do Agendador de Tarefas roda `scripts/iniciar_painel.bat` escondido ao entrar no Windows
  e a cada 30 minutos. Se o painel já estiver no ar, ela não faz nada; se o painel cair, o próprio script reinicia.
- Registro do que acontece: `logs/painel.log`.
- Suspensão e hibernação do PC desligadas quando na tomada.
- Depois de um reinício do Windows, o painel volta quando o usuário entra no Windows (a tarefa roda no usuário, sem permissão de administrador).
- Atualização mensal: trocar os Excel em `data/raw` e rodar `python src/atualizar_bases.py`. Não precisa reiniciar o painel.

### 8. Rodar os testes

```powershell
python tests/test_calculos.py
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

- [X] Pipeline Excel → Parquet com validações
- [X] Dashboard em Streamlit com filtros
- [X] Comparação Real × AA e meta automática
- [X] Evolução mensal da ocupação
- [X] Base no nível da OC
- [X] Bridge AA → Real
- [X] Impacto por cliente (meta e Real × AA)
- [X] Paletizado × Estivado por cliente
- [X] Testes automatizados das regras
- [X] Dashboard separado em módulos e páginas
- [ ] Hospedagem 24h com login corporativo
- [ ] Justificativas em base compartilhada (hoje em CSV local)
- [ ] Dados sintéticos para versão pública

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
