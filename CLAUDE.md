# CLAUDE.md — Contexto do Projeto (TCC: Predição de Falhas em Motores Elétricos)

> Arquivo de handoff para retomar o projeto em qualquer sessão (chat ou Claude Code). Spec técnica completa em `prompt-mestre-tcc-motores-v2.md` — este arquivo é o resumo executivo \+ status \+ próximos passos.

## Objetivo

TCC de graduação: sistema de software para prever falhas em motores elétricos industriais usando Machine Learning. Um técnico coleta medições em campo (instrumento portátil), insere manualmente no sistema, e o sistema classifica a condição do motor em tempo real (HEALTHY / WARNING / FAILURE), com histórico e explicabilidade da predição.

## Status atual

* **Arquitetura: fechada e validada.** Banco, API, ML, segurança e escopo do MVP já definidos em detalhe — ver `docs/prompt-mestre-tcc-motores-v2.md`.
* **Noite 1: CONCLUÍDA.** Dataset baixado, parsing das duas modalidades validado, inventário das 45 sessões gerado e sanidade física confirmada. Ver `docs/01-inventario-dataset.md` — contém achados que **alteram a especificação original** (resumo abaixo).
* **Pipeline de ML: funcionando ponta a ponta.** Ingestão, features (4.500 janelas × 90 features), split por espécime, ensemble RF+XGBoost e avaliação nos dois alvos. Falta serializar o modelo de produção e a tabela `ml_models`.
* **Código:** `ml/config.py`, `ml/kaist/{sessions,loaders,features,severity,splits}.py`, `ml/scripts/{01..04}`. Banco/backend/frontend ainda não iniciados.
* **Prazo:** meta de ter o núcleo (banco + API + ML) funcionando em ~10 noites, 3–4h/noite, com apoio do Claude Code.

## Achados da Noite 1 que mudam a especificação

Detalhamento e evidências em `docs/01-inventario-dataset.md`.

1. **Duas bibliotecas, duas taxas.** Vibração é `.mat` a 25.600 Hz (`scipy.io`); corrente+temperatura é `.tdms` a 25.608,19 Hz (`npTDMS`). Alinhamento entre modalidades é por tempo, não por índice.
2. **Features espectrais são obrigatórias, não opcionais.** Desbalanceamento (15 das 45 sessões) é indistinguível do normal no RMS (0,102 → 0,105 g), mas a amplitude em 1× a rotação cresce monotonicamente (0,00069 → 0,00241). Só com features do domínio do tempo, um terço do dataset viraria falso negativo.
3. **Temperatura fora do modelo v1.** Variação intra-sessão ~0,27 °C contra 1,82 °C entre sessões: é impressão digital da sessão (dia do ensaio), não sinal de falha. Entraria como vazamento. Passa a variável operacional complementar, como a tensão.
4. **Corrente entra com uma única fase.** As 9 sessões BPFO têm os canais das fases S e T vazios; usar as três eliminaria a família de pista externa do treino.
5. **Acústica fora do escopo.** O pacote traz só 5 das 45 sessões, todas a 0 Nm.
6. **Rotação medida: 50,15 Hz (3.009 rpm)**, base para as features de 1×/2×/3×.
7. **Durações são irregulares:** 60 s (rolamento), 120 s (desalinhamento, desbalanceamento, normal a 2 e 4 Nm) e 300 s (normal a 0 Nm).

## Split: leave-one-specimen-out (DECIDIDO)

A unidade experimental independente **não** é a janela, a sessão nem a carga: é o **espécime** (a montagem física). O `RunNumber` dos TDMS prova que cada defeito foi montado uma vez e medido nas 3 cargas em 6–43 min de intervalo, então as 3 sessões de um defeito compartilham rolamento e fixação. Isso descarta o split 70/30 aleatório, o split por sessão e o *leave-one-load-out* — todos deixariam o mesmo espécime nos dois lados.

Implementado em `ml/kaist/splits.py`: **14 folds**, um por espécime de falha, com as 3 sessões do espécime indo inteiras para o teste. As 3 sessões normais são distribuídas entre 3 folds distintos, de modo que **cada sessão é testada exatamente uma vez** — as predições out-of-fold cobrem todas as janelas uma só vez, base honesta para a matriz de confusão agregada. As invariantes são validadas em tempo de execução (`_validate`).

**Limitação declarada:** existe um único espécime saudável, então nenhuma partição avalia generalização para uma máquina saudável nunca vista. É limitação do dataset (o CWRU tem a mesma), não do método — vai na seção de limitações do TCC.

## Pendência para conferir com o artigo (Jung et al., 2023)

`0Nm_BPFI_03` e `0Nm_BPFI_10` têm o nome do arquivo divergindo do log interno do FlexLogger, e a divergência cruza a fronteira WARNING/FAILURE. As outras 16 sessões de rolamento conferem. A evidência física (RMS coerente entre cargas para cada sufixo) favorece **o nome do arquivo**, que é o que o código usa hoje. Confirmar no artigo antes de fechar a rotulagem — ver Anexo A.2 de `docs/01-inventario-dataset.md`.

## Onde estão os dados

* Sinais brutos (~7,6 GB, fora de versionamento): `ml/data/raw/vibration/*.mat` e `ml/data/raw/current_temp/*.tdms`.
* Pacotes originais (zips) permanecem em `Downloads/DATA KAIST`.
* Inventário gerado: `ml/data/interim/session_inventory.csv`.

## Decisões técnicas já fechadas (não reabrir sem motivo forte)

* **Algoritmo:** ensemble Random Forest \+ XGBoost (soft voting ou stacking). Ambos tree-based → compatíveis com SHAP TreeExplainer para explicabilidade unificada.  
* **Dataset:** KAIST — "Vibration, Acoustic, Temperature, and Motor Current Dataset" (Jung et al., 2023; Mendeley DOI 10.17632/ztmf3m7h5x). Vibração (4 acelerômetros) \+ acústica (1 mic) \+ temperatura (2 termopares) \+ corrente (3 TCs), 25,6 kHz, 3 cargas (0/2/4 Nm). 15 condições únicas × 3 cargas \= 45 sessões de gravação (120s normal / 60s falha).  
  * Tensão **não** está no dataset — fica como campo operacional complementar, não entra no modelo v1 (nota de trabalho futuro: estimar via P \= √3×V×I×fator de potência).  
* **Mapeamento de labels — CRÍTICO:** severidade por família de falha, não um limiar global:  
  * Rolamento (IR/OR): diâmetro 0,3mm → WARNING; 1,0/3,0mm → FAILURE  
  * Desalinhamento de eixo (3 níveis): nível 1 → WARNING; níveis 2–3 → FAILURE  
  * Desbalanceamento de rotor (5 níveis): nível 1 → WARNING; níveis 2–5 → FAILURE  
  * Localização/tipo do defeito vira metadado para explicabilidade, não determina a classe.  
* **Split treino/teste:** por GRUPO (sessão de gravação), nunca por janela aleatória — evita vazamento de dados. Usar `GroupKFold`.  
* **Fluxo de dados (v1):** 100% manual, sem integração com PLC/OPC UA/Modbus/MQTT (isso é trabalho futuro). Inserção síncrona: técnico envia medição → API já responde com a predição na mesma requisição.  
* **UX de referência:** ecossistema Dynamox (DynaSens \= inspeção manual, DynaDetect \= diagnóstico por IA) — citar como comparação acadêmica, não como pipeline replicado.  
* **Segurança:** bcrypt/argon2 para senha, JWT com refresh token em cookie httpOnly, rate limiting, validação de range nos valores de sensor, CORS explícito, ORM (SQLAlchemy) contra SQL injection, nota de LGPD para dados de usuário.  
* **Banco:** PostgreSQL. Inclui tabela `ml_models` (versionamento — toda previsão referencia o modelo que a gerou), índice composto `(motor_id, created_at)`, soft delete em motores.  
* **API:** prefixo `/api/v1/`, paginação em endpoints de histórico, erro padronizado (estilo RFC 7807).  
* **Escopo do MVP acadêmico:** ensemble já definido, 1 técnica de explicabilidade (SHAP), sem RBAC refinado de 3 perfis na v1 (login único), sem protocolos industriais, sem modo offline.

## Composição do dataset (referência p/ dimensionamento do treino)

45 sessões × 25,6 kHz. Com janelas de 1s sem sobreposição, como referência:

* HEALTHY: \~360 janelas  
* WARNING \+ FAILURE combinados: \~2.520 janelas (distribuição desigual entre famílias de falha → atenção ao balanceamento de classes)

## Maior risco identificado

Parsing e extração de features dos arquivos brutos multissensor do KAIST (não o backend, nem o ensemble). É a parte menos previsível do projeto — deve ser atacada **primeiro**, não por último, para sobrar margem de correção de rota se travar.

## Plano de 10 noites (núcleo: banco \+ API \+ ML, sem frontend)

| Noite | Foco |
| :---- | :---- |
| 1 | ~~Baixar KAIST, explorar arquivos brutos, validar parsing e sanidade física~~ **CONCLUÍDA** |
| 2 | Setup do projeto (FastAPI \+ PostgreSQL \+ SQLAlchemy) \+ schema do banco em código |
| 3 | Extração de features completa (45 sessões, janelamento, RMS/curtose/temperatura/corrente) \+ labels por família de falha |
| 4 | Split por grupo (GroupKFold) \+ treino do ensemble RF+XGBoost \+ avaliação (matriz de confusão, recall) |
| 5 | Serialização do modelo \+ SHAP básico |
| 6 | Migrations \+ CRUD de motores |
| 7 | Autenticação (JWT \+ bcrypt) |
| 8 | Endpoint `/measurements` com validação de range \+ inferência síncrona |
| 9 | Testes end-to-end, tabela `ml_models`, ajustes |
| 10 | Buffer — imprevistos tendem a aparecer nas noites 3, 4 e 8 |

Com apoio do Claude Code, a estimativa de esforço do núcleo cai de \~34–60h para \~20–35h, o que dá folga dentro das 30–40h disponíveis nas 10 noites (3–4h/noite) — abrindo espaço para puxar parte do frontend básico, se a execução for bem.

## Próximos passos imediatos

1. Noite 1: exploração e parsing do dataset KAIST (maior risco do projeto — atacar primeiro).  
2. Ao rodar isso com o Claude Code, apontar `prompt-mestre-tcc-motores-v2.md` como spec de referência para gerar schema, endpoints e pipeline seção por seção.  
3. Reavaliar escopo depois da noite 1 caso o parsing se mostre mais custoso que o esperado (ex.: simplificar para vibração \+ temperatura antes de incluir corrente).

## Lembrete para a defesa do TCC

Documentar explicitamente, com justificativa: (a) critério de mapeamento de severidade por família de falha, (b) por que split por grupo evita vazamento, (c) por que tensão ficou fora do escopo do modelo v1, (d) por que RF+XGBoost em vez de SVM/redes neurais.  


## Saída do modelo: dois alvos + camada normativa (DECIDIDO)

O modelo prevê **severidade** (HEALTHY/WARNING/FAILURE, objetivo do TCC) **e** **tipo de falha** (normal/rolamento/desalinhamento/desbalanceamento, que alimenta a explicabilidade). Os indicadores da ISO 10816/20816 entram como **camada de validação física** exibida ao lado da predição — não a substituem.

Resultados finais (`ml/scripts/04_evaluate.py`, resumo em `ml/data/interim/evaluation_summary.csv`):

| Alvo | Protocolo | Acurácia |
| :--- | :--- | ---: |
| Severidade | leave-one-specimen-out | 63,0 % |
| Severidade | leave-one-load-out | 95,3 % |
| Tipo de falha | leave-one-specimen-out | 88,7 % |
| Tipo de falha | leave-one-load-out | 80,6 % |

**Como reportar (formulação acordada):** os dois protocolos estabelecem cenários de dificuldade distintos para a generalização do modelo, fornecendo uma faixa de referência metodológica para interpretar resultados futuros obtidos em dados de campo. **Não** se deve afirmar que o desempenho em campo ficará entre os dois valores — isso depende da distribuição real dos motores.

Achados que sustentam a decisão (detalhe em `docs/02-resultados-baseline.md`):

* Split aleatório por janela dá **100 % de acurácia** — a medida exata do vazamento que o split por espécime evita. Essa tabela de 4 protocolos é o resultado metodológico principal do trabalho.
* Incluir os indicadores normativos elevou o recall de HEALTHY de **4,3 % para 69,6 %**: a conversão para velocidade (`V = A/2πf`) é muito menos confundida pela carga que o RMS de aceleração.
* WARNING fica em 0,0 % sob o protocolo estrito e 85,8 % sob o outro — graduação de severidade exige ter visto a escala daquela família, e há um só espécime por nível.

## Baseline por motor: OPCIONAL

O cadastro do motor pode conter uma medição marcada pelo técnico como referência. Quando existe, o sistema comunica a variação diretamente (*"a vibração aumentou 180 % em relação à condição normal conhecida deste motor"* — implementado em `kaist/severity.py::compare_to_baseline`). Quando não existe, opera só com o modelo e os indicadores absolutos. Deliberadamente opcional para não criar dependência operacional no fluxo de campo.

## Matriz de decisão: modelo × evidência física (IMPLEMENTADA)

`ml/kaist/decision.py`, calibrada por `ml/scripts/05_calibrate_decision.py`. Cruza a predição do modelo com uma segunda opinião derivada das **proporções adimensionais** entre indicadores normativos (`p_1x`, `p_2x`, `p_hf`), cujos protótipos são ajustados só no treino de cada fold — o que evita a circularidade de os indicadores já serem features do modelo.

Validação: a discordância **dobra a taxa de erro**. Com concordância estrita (margem 0,00, o padrão), sinaliza 34,6 % das medições, onde o erro é 2,0× maior, capturando **51 % de todos os erros**.

Margens maiores concentram mais erro no que sinalizam, mas capturam menos (42 % em 0,50): trocar sensibilidade por precisão contraria a premissa de que falso negativo de FAILURE custa mais que inspeção desnecessária.

**Dois achados a levar para a defesa:**

1. **A assinatura clássica não se confirmou.** A literatura associa desalinhamento a pico em 2×; aqui o `p_2x` do desalinhamento (0,178) é *menor* que o do normal (0,213) — o desalinhamento aparece na alta frequência. Protótipos são empíricos, não transcritos da teoria.
2. **O sinal se inverte no extremo.** A partir de margem ≈1,0 as janelas sinalizadas erram *menos* (1,0 %) que as não sinalizadas (12,0 %): afastamento físico extremo indica assinatura de referência inadequada, não erro do modelo. O parâmetro **não é monotônico** — aumentá-lo "para sinalizar menos" quebra a camada em silêncio, sem erro visível. Alterar só com nova calibração.

**Como comunicar:** score contínuo de confiança, nunca veredito. Mesmo discordando o modelo acerta 83,3 %, metade dos erros está em janelas concordantes, e a camada física confunde normal com desalinhamento.

## Próximo passo

Serializar o modelo de produção (treinado nas 45 sessões) + tabela `ml_models`, e então iniciar banco e backend (noites 6–8 do plano original).