# Inventário e validação do dataset KAIST (Noite 1)

> Produzido por `ml/scripts/02_inventory.py`. Dados brutos: `session_inventory.csv`
> em `ml/data/interim/`. Este documento registra os achados que impactam a
> metodologia do TCC e devem ser citados na defesa.

## 1. O que o dataset realmente contém

O dataset é distribuído em três pacotes com **formatos e taxas de amostragem diferentes**:

| Modalidade | Formato | Sessões | Canais | Taxa | Unidade |
| :--- | :--- | ---: | ---: | ---: | :--- |
| Vibração | `.mat` (MATLAB v5, LMS Test.Lab) | 45 | 4 acelerômetros | 25.600,00 Hz | m/s² (MKS) |
| Corrente + temperatura | `.tdms` (NI FlexLogger) | 45 | 3 corrente + 2 termopar | 25.608,19 Hz | A / °C |
| Acústica | `.mat` | **5** | 1 microfone | — | Pa |

Consequências práticas:

* a leitura exige **duas bibliotecas distintas** (`scipy.io` e `npTDMS`) — não há
  um formato único, ao contrário do que a especificação inicial supunha;
* as duas modalidades **não compartilham a mesma taxa de amostragem** (diferença
  de 8,19 Hz). O alinhamento entre elas é feito por tempo, não por índice de amostra;
* a vibração é gravada em MKS; o fator `0,101972` (= 1/9,80665) presente no
  arquivo converte para *g*.

### Acústica fora do escopo do modelo

O pacote acústico traz **apenas 5 das 45 sessões**, todas na carga de 0 Nm.
Não há cobertura para treinar nem avaliar de forma honesta, portanto a acústica
**não é usada como feature na v1** — registrar como limitação, não como omissão.

## 2. Inconsistências encontradas nos dados

### 2.1 Nome de arquivo com erro de digitação

As cinco sessões de desbalanceamento a 2 Nm estão gravadas como `Unbalalnce`
(com "l" extra) nos arquivos de vibração, mas como `Unbalance` nos de corrente.
O parser (`ml/kaist/sessions.py`) normaliza e gera um `session_id` canônico
derivado dos metadados, garantindo o pareamento das duas modalidades.

### 2.2 Fases de corrente ausentes nas sessões BPFO

**As 9 sessões de falha de pista externa (BPFO) têm apenas 1 das 3 fases de
corrente gravada** — os canais `Mod2/ai2` e `Mod2/ai3` existem no arquivo mas
contêm zero amostras.

Impacto: usar as três fases como features eliminaria uma família inteira de
falha (pista externa) do treinamento. A corrente entra no modelo por **uma única
fase (`current_r`)**, disponível em 100% das sessões. Para um motor trifásico
equilibrado, a corrente de uma fase é representativa da condição de carga.

### 2.3 Durações heterogêneas

| Família | Sessões | Duração |
| :--- | ---: | :--- |
| Rolamento (interna e externa) | 18 | 60 s |
| Desalinhamento | 9 | 120 s |
| Desbalanceamento | 15 | 120 s |
| Normal | 3 | 120 s (2 e 4 Nm) e **300 s** (0 Nm) |

A especificação inicial supunha 120 s normal / 60 s falha uniformemente; o real
é mais irregular. Isso altera o dimensionamento do treino (seção 4).

## 3. Sanidade física — o que foi confirmado

* **Nenhum NaN** em nenhuma das 45 sessões, nas duas modalidades.
* **Corrente cresce com o torque aplicado**, como esperado:
  2,26 A (0 Nm) → 2,39 A (2 Nm) → 2,72 A (4 Nm).
* **Rotação = 50,15 Hz (3.009 rpm)**, coerente com motor de 2 polos.
* **Vibração centrada em zero** (média ~1e-5 g) em todos os canais.

## 4. Achado crítico: RMS não detecta desbalanceamento

Comparando cada família de falha com a condição normal da mesma carga:

| Família | RMS acc1 (normal → severidade máxima, 0 Nm) | Separação |
| :--- | :--- | :--- |
| Rolamento pista interna | 0,102 → 1,352 g | forte |
| Rolamento pista externa | 0,102 → 1,747 g | forte |
| Desalinhamento | 0,102 → 0,300 g | moderada |
| **Desbalanceamento** | **0,102 → 0,105 g** | **nenhuma** |

O desbalanceamento — **15 das 45 sessões, um terço do dataset** — é
estatisticamente indistinguível da condição normal no domínio do tempo. A massa
de desbalanceamento (583 a 3.318 mg) é pequena demais para alterar o RMS global,
que é dominado por ruído de banda larga.

A assinatura existe, mas **só no domínio da frequência**. A amplitude espectral
em 1× a rotação (50,15 Hz), no acelerômetro acc1, cresce de forma monotônica:

| Condição (0 Nm) | RMS acc1 (g) | Amplitude @1× |
| :--- | ---: | ---: |
| Normal | 0,102 | 0,00069 |
| 583 mg (nível 1) | 0,095 | 0,00109 |
| 1.169 mg (nível 2) | 0,099 | 0,00144 |
| 1.751 mg (nível 3) | 0,100 | 0,00172 |
| 2.239 mg (nível 4) | 0,102 | 0,00196 |
| 3.318 mg (nível 5) | 0,105 | 0,00241 |

Isso é exatamente o comportamento físico previsto: o desbalanceamento gera força
centrífuga proporcional à massa, concentrada na frequência de rotação.

> **Decisão de projeto:** as features do domínio da frequência deixam de ser
> "opcionais" e passam a ser **obrigatórias**. Um modelo treinado apenas com
> estatísticas do domínio do tempo classificaria todo o desbalanceamento como
> HEALTHY — falso negativo, exatamente o erro mais caro no contexto de
> manutenção preditiva.

## 5. Achado crítico: temperatura é fonte de vazamento

A temperatura **não** reflete a condição do motor neste dataset:

* variação **dentro** de uma sessão: ~0,27 °C;
* variação **entre** sessões: desvio de 1,82 °C — cerca de **7× maior**;
* 44 valores médios distintos para 45 sessões: a temperatura média é praticamente
  uma impressão digital da sessão de gravação.

A média por classe (HEALTHY 27,3 °C contra 29,3 °C nas falhas) é um artefato da
**ordem cronológica dos ensaios** — as sessões normais foram gravadas em
25/06/2021, as de rolamento em 28 e 30/06, com a bancada em temperaturas
ambientes diferentes. Ensaios de 60 a 120 s não aquecem o mancal o bastante para
que a temperatura carregue informação de falha.

> **Decisão de projeto:** a temperatura absoluta **não entra como feature do
> modelo v1**. Ela continua sendo registrada como variável operacional
> complementar (exibida no dashboard e no histórico do motor), coerente com o
> tratamento já dado à tensão. Documentar que, num cenário real de operação
> contínua, a temperatura seria um indicador legítimo — a limitação é do
> protocolo experimental do dataset, não do método.

## 6. Distribuição de classes

| Classe | Sessões | Segundos de sinal |
| :--- | ---: | ---: |
| HEALTHY | 3 | 540 |
| WARNING | 12 | 1.080 |
| FAILURE | 30 | 2.880 |

O desbalanceamento em **segundos** (1 : 2 : 5,3) é tratável com ponderação de
classes. O problema real é o número de **grupos**: a classe HEALTHY tem apenas
3 sessões — uma por condição de carga. Como o split é por grupo (para evitar
vazamento), qualquer partição deixa pouquíssima diversidade de HEALTHY no
treino. Esse é o ponto metodológico em aberto ao fim da Noite 1.

---

# Anexo A — Reconstrução do protocolo experimental

Os arquivos `.tdms` guardam `RunNumber` e `Date Created` do FlexLogger, o que
permite reconstruir a ordem real dos ensaios (`ml/data/interim/run_order.csv`).
Dois achados com impacto direto na metodologia.

## A.1 A unidade experimental independente é o espécime, não a sessão nem a carga

Cada defeito físico foi montado **uma única vez** e medido nas três cargas em
sequência imediata:

| Espécime | Janela p/ as 3 cargas |
| :--- | ---: |
| Rolamento externa 3,0 mm | 6 min |
| Rolamento interna 3,0 mm | 7 min |
| Rolamento externa 0,3 mm | 7 min |
| Rolamento interna 1,0 mm | 16 min |
| Desalinhamento (3 níveis) | 28–34 min |
| Desbalanceamento (5 massas) | 42–43 min |
| Normal | 88 min |

Intervalos de 6 a 7 minutos entre as três cargas do mesmo rolamento tornam
fisicamente impossível ter havido desmontagem e remontagem: **é a mesma
montagem, com o torque alterado entre as medições.**

Consequência: `0Nm_BPFI_30`, `2Nm_BPFI_30` e `4Nm_BPFI_30` não são três
experimentos independentes — são o mesmo rolamento defeituoso, na mesma
fixação, sob três torques. Um split *leave-one-load-out* portanto **deixa o
mesmo espécime físico nos dois lados da partição**.

O dataset tem **15 espécimes**: 1 normal + 14 de falha (3 pista interna,
3 pista externa, 3 desalinhamento, 5 desbalanceamento).

### Limitação estrutural intransponível

Como existe **um único espécime saudável**, nenhum esquema de split consegue
avaliar generalização para uma máquina saudável nunca vista. Se o grupo for o
espécime, a classe HEALTHY necessariamente aparece nos dois lados. Isso é
limitação do dataset — e de datasets de bancada em geral, incluindo o CWRU —
não do método. **Deve constar explicitamente na seção de limitações do TCC.**

## A.2 Divergência de rotulagem em duas sessões

Comparando a severidade declarada no nome do arquivo com o nome do log interno
gravado pelo FlexLogger, **16 das 18 sessões de rolamento conferem**. Duas
divergem, e são exatamente uma o oposto da outra:

| Arquivo | Severidade pelo nome | Log interno | Diverge |
| :--- | :--- | :--- | :--- |
| `0Nm_BPFI_03` | 0,3 mm | `LogFile_0Nm_Inner_1mm` (1,0 mm) | sim |
| `0Nm_BPFI_10` | 1,0 mm | `LogFile_0Nm_Inner_03mm` (0,3 mm) | sim |
| demais 16 | — | — | não |

Isso **cruza a fronteira do rótulo**: 0,3 mm mapeia para WARNING e 1,0 mm para
FAILURE. Se o log interno estiver correto, duas sessões estão com a classe
invertida.

**A evidência física favorece o nome do arquivo.** O RMS de acc1 é coerente
dentro de cada sufixo de arquivo através das três cargas:

| Sufixo | 0 Nm | 2 Nm | 4 Nm |
| :--- | ---: | ---: | ---: |
| `BPFI_03` | 0,953 | 1,045 | 1,117 |
| `BPFI_10` | 1,352 | 1,374 | 1,395 |
| `BPFI_30` | 0,752 | 0,782 | 0,792 |

Se `0Nm_BPFI_03` fosse de fato o defeito de 1,0 mm, seu RMS deveria alinhar-se
a 1,35–1,40 e não a 0,95. Conclusão: os dados e o nome do arquivo estão
consistentes; o campo `name` desses dois `.tdms` foi anotado trocado pelo
operador. **Recomenda-se confirmar contra a documentação oficial (Jung et al.,
2023) antes de fechar a rotulagem.**

## A.3 Severidade de rolamento não é monotônica na vibração

O defeito de 3,0 mm produz RMS **menor** que o de 1,0 mm (0,78 contra 1,37 a
2 Nm), de forma consistente nas três cargas. O comportamento é conhecido na
literatura de rolamentos: defeitos muito largos deixam de gerar impacto agudo,
pois o elemento rolante passa a descer e subir o degrau do defeito de forma mais
suave. Registrar o efeito para justificar por que a severidade física não pode
ser tratada como uma escala linear de gravidade.
