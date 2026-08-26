# Prompt Mestre v2 — Sistema de Predição de Falhas em Motores Elétricos Industriais

> Revisão incorporando: correções de metodologia de ML, segurança, banco de dados e API; decisão de ensemble (Random Forest \+ XGBoost); migração do dataset de CWRU para KAIST (vibração \+ acústica \+ temperatura \+ corrente); fluxo de coleta manual em campo por técnico; inspiração de UX no ecossistema Dynamox (DynaSens \+ DynaDetect).

Quero desenvolver um sistema completo para meu Trabalho de Conclusão de Curso (TCC), cujo tema é:

**"Desenvolvimento de um software para previsão de falhas em motores elétricos industriais utilizando Machine Learning."**

O objetivo do projeto é desenvolver uma solução de software capaz de receber medições inseridas por um técnico em campo, analisar as condições de operação do motor utilizando técnicas de Machine Learning e identificar antecipadamente possíveis condições de falha, permitindo auxiliar a equipe de manutenção na tomada de decisões. Cada medição inserida e sua respectiva previsão ficam registradas no histórico do motor.

Quero que você atue simultaneamente como:

* Arquiteto de Software;  
* Engenheiro de Machine Learning;  
* Engenheiro de Dados;  
* Desenvolvedor Backend;  
* Desenvolvedor Frontend;  
* Especialista em sistemas industriais e manutenção preditiva;  
* Orientador técnico de TCC.

## 0\. Decisões já fechadas (não reabrir sem justificativa)

* **Algoritmo:** ensemble Random Forest \+ XGBoost (Gradient Boosting), combinados via soft voting ou stacking com meta-learner simples. Ambos são baseados em árvores — compatibilidade total com SHAP TreeExplainer para explicabilidade unificada do ensemble.  
* **Dataset:** KAIST — "Vibration, Acoustic, Temperature, and Motor Current Dataset of Rotating Machine Under Varying Operating Conditions" (Jung et al., 2023, *Data in Brief*; Mendeley Data, DOI 10.17632/ztmf3m7h5x). Coleta simultânea de vibração (4 acelerômetros), acústica (1 microfone), temperatura (2 termopares) e corrente do motor (3 transformadores de corrente), amostrados a 25,6 kHz, sob três condições de carga (0, 2 e 4 Nm). Cobre falhas de rolamento (pista interna/externa, por diâmetro do defeito: 0,3 / 1,0 / 3,0 mm), desalinhamento de eixo (3 níveis) e desbalanceamento de rotor (5 níveis) — 15 condições únicas × 3 cargas \= 45 sessões de gravação (120 s em estado normal, 60 s por estado de falha).  
* **Fluxo de entrada de dados (v1):** 100% manual. Um técnico realiza a coleta em campo (ex.: com um coletor/analisador de vibração portátil) e insere os valores no sistema via formulário mobile-first. Não há integração automática com sensores/gateways na v1 — isso é trabalho futuro.  
* **Referência de UX/fluxo:** ecossistema Dynamox, especificamente os módulos **DynaSens** (inspeção/coleta manual em campo, com suporte a app) e **DynaDetect** (diagnóstico por IA a partir da leitura). O sistema NÃO reproduz o pipeline de sensores sem fio automáticos da Dynamox (DynaPredict com hardware wireless) — isso fica fora do escopo acadêmico e deve ser citado apenas como trabalho futuro.

## 1\. Variáveis disponíveis vs. variáveis ainda fora de escopo

**Atualização (dataset KAIST):** vibração, temperatura e corrente do motor passam a ser features reais de treinamento do modelo — não apenas contexto operacional exibido no dashboard, como era com o CWRU. **Tensão** continua sem uma fonte pública sincronizada com os demais sinais e permanece como variável operacional complementar na v1.

### Variáveis usadas para treinar o modelo (derivadas do dataset KAIST)

* Vibração RMS, pico, desvio padrão, curtose, crest factor (4 acelerômetros — 2 mancais × 2 eixos);  
* Temperatura (2 termopares, um por mancal);  
* Corrente do motor (3 fases, via transformadores de corrente);  
* Carga (torque: 0 / 2 / 4 Nm) — metadado da condição experimental;  
* Rotação — velocidade nominal do ensaio.

Todas essas features são extraídas dos sinais brutos via engenharia de características (janelamento do sinal \+ cálculo estatístico no domínio do tempo; opcionalmente domínio da frequência via FFT para vibração/acústica).

### Variáveis operacionais complementares (registradas pelo técnico, fora do escopo do modelo v1)

* Tensão;  
* Horas de operação;  
* Quantidade de partidas;  
* Histórico de manutenção.

Essas variáveis continuam fazendo parte do cadastro de medição e do dashboard, mas não alimentam o modelo treinado na v1. Documente no TCC que a tensão poderia futuramente ser estimada de forma indireta (ex.: P \= √3 × V × I × fator de potência, se a potência nominal do motor for conhecida) ou obtida de um dataset complementar — mas isso fica como trabalho futuro, não implementado na v1.

## 2\. Machine Learning

### Classes de saída

* **HEALTHY** — condição normal;  
* **WARNING** — degradação incipiente (nível de menor severidade dentro de cada família de falha);  
* **FAILURE** — alta probabilidade de falha (níveis intermediário/superior de severidade).

**Critério de mapeamento (obrigatório documentar no TCC) — revisado para múltiplas famílias de falha:** diferente do CWRU (uma única escala de diâmetro), o KAIST tem três famílias de falha com unidades de severidade não comparáveis entre si:

| Família de falha | Níveis de severidade | Unidade |
| :---- | :---- | :---- |
| Rolamento (pista interna/externa) | 3 (0,3 / 1,0 / 3,0 mm) | diâmetro do defeito |
| Desalinhamento de eixo | 3 níveis | deslocamento angular/paralelo |
| Desbalanceamento de rotor | 5 níveis | massa de desbalanceamento |

Como as unidades não são diretamente comparáveis, o corte HEALTHY/WARNING/FAILURE deve ser definido **separadamente por família de falha**, não por um único limiar numérico global. Critério sugerido e defensável no TCC: o nível de menor severidade de cada família → WARNING; os níveis intermediário e superior → FAILURE. Documente essa escolha explicitamente como decisão de projeto, já que ela impacta diretamente as métricas de recall por classe.

A localização/tipo do defeito (rolamento IR/OR, eixo, rotor) é preservada como metadado e usada na camada de explicabilidade ("o modelo identificou um padrão consistente com desalinhamento de eixo"), mas não determina isoladamente a classe HEALTHY/WARNING/FAILURE.

### Algoritmo

Ensemble Random Forest \+ XGBoost via soft voting (probabilidades médias) ou stacking. Justifique na análise comparativa:

* quantidade de dados do KAIST (moderada — reforça uso de modelos tree-based, que lidam bem com datasets pequenos/médios e poucas features, ao contrário de redes neurais que exigem mais dados);  
* interpretabilidade (ambos compatíveis com SHAP TreeExplainer);  
* facilidade de treinamento e implantação (sem necessidade de GPU, serialização simples via pickle/joblib ou formato nativo do XGBoost);  
* natureza multissensor dos dados (vibração \+ temperatura \+ corrente) — modelos tree-based lidam naturalmente com features de escalas e origens diferentes, sem exigir normalização tão rígida quanto redes neurais ou SVM.

Não é necessário comparar contra SVM e redes neurais no corpo principal — pode ser citado como comparação exploratória na análise de resultados, mas o ensemble RF+XGBoost é a escolha principal do projeto.

## 3\. Pipeline de Machine Learning

Dados brutos (sinais KAIST: vibração \+ acústica \+ temperatura \+ corrente)

      ↓

Validação

      ↓

Segmentação do sinal em janelas

      ↓

Extração de características (RMS, pico, curtose, crest factor, desvio padrão)

      ↓

Rotulagem (mapeamento severidade → HEALTHY/WARNING/FAILURE)

      ↓

Divisão treino/validação/teste por GRUPO (ver abaixo)

      ↓

Normalização/transformação

      ↓

Balanceamento de classes (se necessário)

      ↓

Treinamento (Random Forest \+ XGBoost)

      ↓

Validação cruzada

      ↓

Avaliação (foco em recall da classe FAILURE)

      ↓

Ensemble/combinação

      ↓

Serialização \+ registro em tabela de versionamento de modelos

      ↓

Deploy

      ↓

Predição em produção (a partir de entrada manual do técnico)

### Composição do dataset KAIST (referência para dimensionamento)

15 condições únicas (normal \+ pista interna × 3 severidades \+ pista externa × 3 \+ desalinhamento × 3 \+ desbalanceamento × 5\) × 3 cargas (0/2/4 Nm) \= **45 sessões de gravação**, cada uma captando vibração, acústica, temperatura e corrente simultaneamente a 25,6 kHz — 120 s em estado normal, 60 s por estado de falha (\~48 min de sinal bruto por canal no total).

O número final de amostras de treinamento depende do tamanho de janela escolhido na extração de features. Como referência, com janelas de 1 s sem sobreposição:

* HEALTHY: \~360 janelas (3 sessões normais × 120 janelas);  
* WARNING \+ FAILURE combinados: \~2.520 janelas (42 sessões de falha × 60 janelas), distribuídas de forma desigual entre as famílias de falha (rolamento tem mais condições que desalinhamento, por exemplo) — reforça a necessidade do balanceamento de classes já previsto no pipeline.

Janelas menores ou com sobreposição aumentam esse total proporcionalmente, mas overlap entre janelas da mesma sessão aumenta a correlação entre amostras vizinhas — reforça ainda mais a necessidade do split por grupo descrito abaixo.

### Divisão treino/validação/teste — evitando vazamento de dados

**Erro comum a evitar:** dividir aleatoriamente por *janela/amostra* faz com que janelas da mesma sessão de gravação apareçam tanto no treino quanto no teste, vazando informação e inflando artificialmente a acurácia. A divisão deve ser feita por **grupo** — ou seja, por sessão/arquivo de gravação (ex.: `2Nm_BPFI_10`, `4Nm_unbalance_03`) — garantindo que nenhuma janela da mesma sessão apareça em splits diferentes. Use `GroupKFold` ou equivalente, agrupando por identificador de sessão.

### Outros cuidados

* **Overfitting:** validação cruzada, limitar profundidade das árvores, early stopping no XGBoost;  
* **Desbalanceamento:** verificar proporção de classes após o mapeamento de severidade; usar `class_weight` ou reamostragem (SMOTE com cautela, aplicado apenas ao conjunto de treino);  
* **Threshold de decisão:** não usar 0.5 padrão para todas as classes — como o recall de FAILURE é prioritário, considere ajustar o limiar de decisão ou usar aprendizado sensível a custo, penalizando mais falsos negativos de FAILURE do que falsos positivos.

## 4\. Arquitetura geral

### Frontend

* React \+ TypeScript;  
* biblioteca de gráficos (ex.: Recharts);  
* desenho mobile-first para a tela de coleta em campo pelo técnico (inspirado no fluxo de inspeção do app Dynamox — formulário guiado, validação em tempo real, confirmação antes de enviar).

Responsabilidades: dashboard, cadastro de motores, inserção de medição em campo, histórico, gráficos, indicadores, alertas, resultado das previsões com probabilidades e explicabilidade.

### Backend

Python \+ FastAPI. Responsabilidades: API REST, autenticação, gerenciamento de motores e medições, execução **síncrona** da previsão a cada medição inserida (o técnico recebe o resultado imediatamente após enviar a medição), comunicação com banco de dados, gerenciamento de alertas, histórico.

### Machine Learning

Camada isolada responsável por: carregamento do modelo (ensemble serializado), pré-processamento das features de entrada, inferência, cálculo de probabilidades, classificação, explicabilidade (SHAP) — chamada de forma síncrona pelo endpoint de medições.

### Banco de dados

PostgreSQL. Entidades: usuários, setores, motores, medições, previsões, **modelos (ml\_models)**, alertas, inspeções, manutenções.

## 5\. Fluxo completo de uma previsão (revisado — coleta manual síncrona)

Técnico em campo

 ↓

Coleta com instrumento portátil (vibração RMS/pico, temperatura, corrente, carga — todas como

entrada real do modelo; tensão registrada apenas como contexto operacional complementar)

 ↓

Insere medição no app (mobile-first, formulário guiado)

 ↓

API recebe medição (POST /api/v1/measurements)

 ↓

Validação de range dos valores (ex.: rejeitar temperatura ou vibração fora de faixa plausível)

 ↓

Extração/organização das features usadas pelo modelo

 ↓

Inferência do ensemble (Random Forest \+ XGBoost)

 ↓

Cálculo de probabilidades por classe \+ explicabilidade (SHAP)

 ↓

Classificação (HEALTHY / WARNING / FAILURE)

 ↓

Armazenamento da medição \+ previsão associada no histórico do motor

 ↓

Resposta IMEDIATA ao técnico (mesma requisição) com classificação, probabilidades e principais

fatores

 ↓

Atualização do dashboard

 ↓

Geração de alerta, se aplicável

Exemplo de request/response:

POST /api/v1/measurements

{

  "motor\_id": "uuid",

  "vibration\_rms": 7.2,

  "vibration\_peak": 12.4,

  "rpm": 1780,

  "load\_hp": 2,

  "temperature": 87,

  "current": 42

}

{

  "measurement\_id": "uuid",

  "prediction": "WARNING",

  "probabilities": {

    "HEALTHY": 0.12,

    "WARNING": 0.76,

    "FAILURE": 0.12

  },

  "top\_factors": \[

    {"feature": "vibration\_rms", "contribution": 0.34},

    {"feature": "crest\_factor", "contribution": 0.21}

  \],

  "model\_version": "ensemble\_v1",

  "created\_at": "2026-08-15T14:30:00Z"

}

**Nota de escopo:** a inserção manual assume conectividade no momento do registro. Suporte a modo offline com sincronização posterior (como o app Dynamox oferece) é uma melhoria de trabalho futuro, não obrigatória para o MVP acadêmico.

## 6\. Dashboard (inspirado em DynaNeo/visão geral da Dynamox)

### Visão geral

* Quantidade total de motores;  
* Indicador de saúde agregado por motor e por setor (health score simplificado, sintetizando histórico recente de previsões — inspirado na visão de "saúde da planta" de ferramentas como a Dynamox);  
* Motores saudáveis / em alerta / com risco de falha;  
* Alertas ativos;  
* Últimas inspeções/medições.

### Monitoramento por motor

Última medição registrada (vibração, temperatura, corrente, RPM), estado atual, probabilidade de falha, histórico de evolução.

### Histórico

Gráficos de: vibração × tempo, temperatura × tempo, corrente × tempo, condição × tempo, probabilidade de falha × tempo.

**Enquadramento acadêmico para o TCC:** descreva o sistema como comparável ao módulo de inspeção manual \+ diagnóstico por IA de soluções comerciais de manutenção preditiva (ex.: DynaSens \+ DynaDetect da Dynamox), e não ao pipeline completo de sensoriamento automático sem fio — essa distinção deve constar na justificativa de escopo.

## 7\. Sistema de alertas

HEALTHY  → nenhuma ação

WARNING  → recomendar inspeção

FAILURE  → recomendar intervenção/manutenção

Armazenar: data, motor, tipo de alerta, severidade, medição/previsão que originou o alerta, status, ação tomada.

## 8\. Explicabilidade da IA

Use SHAP TreeExplainer, compatível com Random Forest e XGBoost. Para o ensemble, explique a metodologia de combinação escolhida: (a) média das SHAP values dos dois modelos ponderada pelo peso de cada um no voting, ou (b) explicar apenas o modelo com maior peso/confiança na predição específica. Documente a escolha e a justificativa no TCC.

Probabilidade de falha: 87%

Principais fatores:

Vibração RMS       ██████████

Crest Factor        ██████

Temperatura          ████

RPM                    ██

## 9\. Segurança

* **Senhas:** hash com bcrypt ou argon2 (nunca SHA simples ou reversível);  
* **Autenticação:** JWT com expiração curta de access token \+ refresh token; token armazenado em cookie httpOnly (evitar localStorage, vulnerável a XSS);  
* **Rate limiting** na API, especialmente nos endpoints de autenticação e de inserção de medição;  
* **Validação de range** nos valores de sensor recebidos (ex.: rejeitar temperatura negativa abaixo do plausível, vibração negativa, RPM fora da faixa do motor cadastrado);  
* **CORS** configurado explicitamente entre o domínio do frontend React e a API FastAPI;  
* **SQL Injection:** mitigado via ORM (SQLAlchemy) com queries parametrizadas — declarar explicitamente como requisito, não deixar implícito;  
* **LGPD:** nota sobre tratamento de dados pessoais de usuários (nome, e-mail) cadastrados no sistema, mesmo os dados de motores não sendo dados pessoais;  
* **Logs de auditoria** para ações sensíveis (login, alteração de motor, resolução de alerta).

Perfis de acesso:

ADMIN        → acesso total

MANUTENÇÃO   → motores \+ medições \+ previsões \+ alertas

OPERADOR     → visualização

## 10\. Banco de dados

Modelo relacional incluindo, além das entidades já previstas:

* **`ml_models`**: id, versão, algoritmo (ex. "rf\_xgb\_ensemble"), hiperparâmetros, métricas de avaliação, data de treino, caminho do artefato serializado. Toda previsão referencia o `model_version` que a gerou (rastreabilidade obrigatória para auditabilidade);  
* **Índice composto** `(motor_id, created_at)` na tabela de medições, para consultas de histórico performáticas conforme o volume cresce;  
* **Soft delete** em motores (campo `deleted_at`), preservando o histórico de medições/previsões associado mesmo se o motor for removido do cadastro ativo.

## 11\. API

Convenções gerais: prefixo `/api/v1/`, paginação (`limit`/`offset` ou cursor) em endpoints de listagem/histórico, formato de erro padronizado (ex. estilo RFC 7807 problem details).

POST   /api/v1/auth/login

GET    /api/v1/motors

POST   /api/v1/motors

GET    /api/v1/motors/{id}

PUT    /api/v1/motors/{id}

DELETE /api/v1/motors/{id}          (soft delete)

POST   /api/v1/measurements          (dispara previsão síncrona, retorna resultado na mesma resposta)

GET    /api/v1/motors/{id}/measurements   (paginado)

GET    /api/v1/motors/{id}/predictions    (paginado)

GET    /api/v1/alerts

PUT    /api/v1/alerts/{id}

GET    /api/v1/dashboard

## 12\. Containerização

Docker para: frontend, backend, PostgreSQL, serviço de ML. Avalie se o modelo deve ficar embutido no backend ou em serviço separado — para um TCC de desenvolvedor único, embutir no backend (mesmo processo Python/FastAPI) costuma ser mais simples de implantar e defender, desde que a camada de ML permaneça logicamente isolada (módulo próprio, sem lógica de API misturada).

## 13\. Corte de escopo — MVP acadêmico (importante para viabilidade do prazo)

Para a primeira entrega, o sistema deve conter apenas:

* Ensemble Random Forest \+ XGBoost (não comparação extensa com SVM/redes neurais no corpo principal — pode ficar em análise exploratória);  
* Autenticação simples (login \+ JWT), sem necessariamente refinar os 3 perfis de acesso em detalhe na v1 — pode ser um perfil único "usuário autenticado" com nota de que RBAC completo é trabalho futuro, dependendo do tempo disponível;  
* Inserção manual de dados (sem protocolos industriais reais — PLC/OPC UA/Modbus/MQTT ficam 100% como "trabalhos futuros" na documentação);  
* SHAP como técnica de explicabilidade (não é necessário implementar múltiplas técnicas);  
* Docker apenas para os serviços essenciais (frontend, backend+ML, PostgreSQL);  
* Suporte offline do formulário de campo — não obrigatório na v1.

Tudo além disso deve ser explicitamente listado na seção "Melhorias futuras" do TCC, não implementado.

## 14\. Fases de desenvolvimento

Mantidas conforme planejamento original: (1) Levantamento, (2) Arquitetura, (3) Machine Learning (dataset KAIST, extração de features multissensor, mapeamento de severidade por família de falha, split por grupo, treinamento do ensemble, avaliação), (4) Backend, (5) Frontend, (6) Integração, (7) Testes, (8) Deploy — nessa ordem, começando pelo banco de dados e backend, seguido do pipeline de ML e finalmente o frontend.

## 15\. Primeira tarefa

Antes de escrever qualquer código, faça uma análise completa do projeto incorporando todas as decisões e correções acima. Entregue nesta ordem:

1. Resumo da solução;  
2. Objetivo do sistema;  
3. Atores;  
4. Requisitos funcionais (atualizados para o fluxo de coleta manual síncrona);  
5. Requisitos não funcionais;  
6. Casos de uso;  
7. Arquitetura geral;  
8. Arquitetura do Machine Learning (incluindo estratégia de mapeamento de labels e split por grupo);  
9. Arquitetura do Backend;  
10. Arquitetura do Frontend (fluxo mobile-first de coleta em campo);  
11. Arquitetura do Banco de Dados (com `ml_models`, índices, soft delete);  
12. Fluxo dos dados;  
13. Fluxo de uma previsão (síncrono);  
14. Tecnologias recomendadas;  
15. Estrutura de diretórios;  
16. Modelo inicial do banco;  
17. Endpoints da API;  
18. Estratégia de treinamento (dataset KAIST, extração de features multissensor, mapeamento de severidade por família de falha, ensemble);  
19. Estratégia de avaliação (métricas, foco em recall de FAILURE);  
20. Estratégia de implantação;  
21. Plano de desenvolvimento por etapas;  
22. Riscos e limitações (incluindo a ausência de tensão no dataset e a heterogeneidade de escalas de severidade entre famílias de falha);  
23. Melhorias futuras (protocolos industriais, RBAC completo, modo offline, dataset real de campo, estimativa de tensão via cálculo de potência).

**IMPORTANTE:** não gere código nesta primeira etapa. Primeiro quero validar toda a arquitetura. Depois da arquitetura aprovada, iremos implementar o projeto gradualmente, começando pelo banco de dados e backend, depois o pipeline de Machine Learning e finalmente o frontend.

Durante o desenvolvimento, explique as decisões técnicas de maneira que elas possam posteriormente ser utilizadas na documentação e defesa do TCC.  
