# Predição de Falhas em Motores Elétricos Industriais com Machine Learning

Trabalho de Conclusão de Curso — João Vitor Toledo Hass

Sistema que recebe medições de vibração e corrente coletadas em campo por um
técnico, classifica a condição do motor e explica o diagnóstico, cruzando a
predição do modelo com indicadores normativos da ISO 10816/20816.

---

## Subir o sistema completo (Docker)

```bash
cp .env.example .env
```

Edite o `.env` e defina `POSTGRES_PASSWORD` e `JWT_SECRET_KEY`. Gere a chave com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

```bash
docker compose up -d --build
```

A interface fica em **http://localhost:8080**. Interface e API são servidas na
mesma origem pelo nginx — os cookies de autenticação são httpOnly e SameSite, e
seriam tratados como *third-party* (portanto descartados) se estivessem em
origens diferentes.

Crie o primeiro usuário — não há usuário padrão embutido na imagem, de propósito:

```bash
docker compose exec api python scripts/seed_admin.py --email voce@empresa.com --name "Seu Nome"
```

Os três serviços: `db` (PostgreSQL, sem porta exposta), `api` (FastAPI com a
camada de ML no mesmo processo) e `web` (nginx servindo a interface e fazendo
proxy da API). O entrypoint da API aplica as migrations e registra os modelos
antes de atender.

---

## Como rodar a demonstração

**Pré-requisitos** (uma vez só):

```bash
pip install numpy scipy pandas scikit-learn xgboost npTDMS pyarrow joblib
```

**No VSCode:** abra a pasta do projeto, pressione **F5** e escolha
*"Demonstracao do sistema (4 casos)"*.

**No terminal:**

```bash
python demo.py
```

Outros modos:

```bash
python demo.py --metricas
```

```bash
python demo.py --listar
```

```bash
python demo.py 0Nm_BPFO_10
```

A demonstração usa **predições out-of-fold**: cada medição é classificada por um
modelo que nunca viu aquele espécime. É o número honesto, não o do modelo
treinado com tudo.

---

## O que o sistema faz

Para cada medição, o sistema produz:

1. **Tipo de falha** — rolamento, desalinhamento, desbalanceamento ou normal
   (ensemble Random Forest + XGBoost);
2. **Severidade** — HEALTHY / WARNING / FAILURE;
3. **Indicadores normativos** — velocidade RMS na banda ISO, componentes 1× e 2×
   da rotação, aceleração em alta frequência;
4. **Matriz de decisão** — cruza a predição do modelo com a assinatura física e
   sinaliza divergência entre as evidências;
5. **Comparação com baseline** — opcional, quando o motor tem uma medição de
   referência registrada.

## Resultados

| Alvo | Protocolo | Acurácia |
| :--- | :--- | ---: |
| Severidade | leave-one-specimen-out | 63,0 % |
| Severidade | leave-one-load-out | 95,3 % |
| Tipo de falha | leave-one-specimen-out | 88,7 % |
| Tipo de falha | leave-one-load-out | 80,6 % |

Os dois protocolos estabelecem cenários de dificuldade distintos para a
generalização do modelo, fornecendo uma faixa de referência metodológica para
interpretar resultados futuros obtidos em dados de campo.

**Para comparação:** o mesmo modelo, com split aleatório por janela, atinge
**100,0 % de acurácia** — a medida exata do vazamento de dados que o split por
espécime evita.

## Metodologia — por que o split é por espécime

A unidade experimental independente do dataset não é a janela, nem a sessão de
gravação, nem a condição de carga: é o **espécime**, a montagem física da
bancada. Os metadados dos arquivos comprovam que cada defeito foi montado uma
única vez e medido sob as três cargas em sequência, com 6 a 43 minutos de
intervalo — sem desmontagem. As três sessões de um mesmo defeito compartilham
rolamento, fixação e alinhamento, e por isso vão inteiras para o mesmo lado da
partição.

Detalhamento em [`docs/02-resultados-baseline.md`](docs/02-resultados-baseline.md).

## Estrutura

```
docker-compose.yml              banco, API e interface
demo.py                         demonstração do sistema (sem containers)
backend/                        FastAPI, ML e migrations
frontend/                       React + TypeScript + Vite
ml/
  config.py                     caminhos e constantes
  kaist/
    sessions.py                 parsing e rotulagem por família de falha
    loaders.py                  leitura de .mat (vibração) e .tdms (corrente)
    features.py                 extração de características por janela
    severity.py                 indicadores normativos ISO 10816/20816
    splits.py                   leave-one-specimen-out
    decision.py                 matriz de decisão modelo × evidência física
  scripts/
    01_extract_tdms.py          extrai os arquivos de corrente/temperatura
    02_inventory.py             inventário e sanidade física das 45 sessões
    03_extract_features.py      matriz de features (4.500 janelas × 97)
    04_evaluate.py              avaliação nos dois alvos e dois protocolos
    05_calibrate_decision.py    calibração da matriz de decisão
    08_single_channel_profile.py  features do perfil de canal único
    09_train_profiles.py        treina e serializa os dois perfis
    07_generate_oof.py          predições out-of-fold para a demonstração
docs/
  01-inventario-dataset.md      achados do dataset que alteram a especificação
  02-resultados-baseline.md     resultados, metodologia e limitações
```

## Reproduzir do zero

Os sinais brutos (~7,6 GB) não são versionados. Baixe o dataset KAIST
(Mendeley, DOI 10.17632/ztmf3m7h5x), coloque os arquivos em
`ml/data/raw/vibration/` e `ml/data/raw/current_temp/`, e execute:

```bash
python ml/scripts/02_inventory.py
```

```bash
python ml/scripts/03_extract_features.py
```

```bash
python ml/scripts/04_evaluate.py
```

```bash
python ml/scripts/09_train_profiles.py
```

```bash
python ml/scripts/07_generate_oof.py
```

## Limitações conhecidas

- **Recall de WARNING = 0,0 %** sob leave-one-specimen-out. O dataset tem um
  único espécime por nível de severidade, então o modelo precisa graduar uma
  escala que nunca viu. Sob leave-one-load-out o mesmo recall é 85,8 %.
- **Espécime saudável único.** Nenhuma partição avalia generalização para uma
  máquina saudável nunca vista — limitação do dataset, comum a bancadas de
  laboratório.
- **Seleção de modelo sobre os folds de avaliação.** A inclusão dos indicadores
  normativos e a calibração da matriz de decisão foram decididas observando as
  métricas out-of-fold, o que as torna otimistas em grau não quantificado.
- **Temperatura fora do modelo.** Sua variação entre sessões é ~7× maior que
  dentro de uma sessão, o que a torna uma impressão digital da gravação e não um
  sinal de falha.
- **Acústica fora do escopo.** O pacote original cobre apenas 5 das 45 sessões.

## Dataset

Jung, W. et al. (2023). *Vibration, acoustic, temperature, and motor current
dataset of rotating machine under varying operating conditions for fault
diagnosis.* Data in Brief. Mendeley Data, DOI 10.17632/ztmf3m7h5x.
