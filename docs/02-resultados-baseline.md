# Resultados do baseline — ensemble RF + XGBoost

> Gerado por `ml/scripts/04_evaluate.py` sobre 4.500 janelas de 1 s.
>
> **Nota de leitura:** as seções 1 a 5 registram o diagnóstico feito com o
> conjunto inicial de 93 features, *antes* da inclusão dos indicadores
> normativos. Os resultados finais, com as 90 features atuais (incluindo os
> indicadores ISO), estão na **seção 9** — e são substancialmente melhores. A
> narrativa anterior é preservada porque é ela que justifica cada decisão
> tomada.

## 1. O resultado central: quanto o protocolo de avaliação muda o número

O mesmo modelo, as mesmas features, os mesmos dados — mudando **apenas** o
critério de separação entre treino e teste:

| Protocolo | Acurácia | HEALTHY | WARNING | FAILURE |
| :--- | ---: | ---: | ---: | ---: |
| Aleatório por janela (70/30 estratificado) | **100,0 %** | 100 % | 100 % | 100 % |
| Por sessão de gravação (GroupKFold) | 72,5 % | 0,0 % | 58,0 % | 91,5 % |
| Leave-one-load-out | 89,1 % | 80,4 % | 74,7 % | 96,2 % |
| **Leave-one-specimen-out (adotado)** | **50,6 %** | 4,3 % | 0,0 % | 78,3 % |

O split aleatório por janela produz **acurácia perfeita**. Não porque o modelo
seja perfeito, mas porque janelas vizinhas da mesma gravação são quase cópias
uma da outra: o modelo reconhece a gravação, não a falha. Os 100 % são o
retrato exato do vazamento que a literatura de manutenção preditiva
frequentemente reporta sem discutir.

**Esta tabela é o resultado metodológico principal do trabalho.** Ela quantifica
por que a escolha do protocolo de validação importa mais, neste problema, do que
a escolha do algoritmo.

## 2. O que o modelo consegue e o que não consegue

Sob o protocolo adotado (leave-one-specimen-out), separando as duas perguntas:

### Detectar que há algo errado — funciona

| | predito OK | predito FALHA |
| :--- | ---: | ---: |
| **realmente OK** | 23 | 517 |
| **realmente com falha** | 259 | 3.701 |

* **Sensibilidade (recall de falha): 93,5 %** — de cada 100 janelas de motor
  defeituoso, 93 são sinalizadas, mesmo sendo um defeito que o modelo nunca viu.
* **Especificidade: 4,3 %** — praticamente todo motor saudável também é
  sinalizado. O sistema, neste estado, alarma quase tudo.

### Graduar a severidade — não funciona

O recall de WARNING é **exatamente 0,0 %**. Nenhuma das 1.080 janelas de WARNING
foi classificada como WARNING. O destino delas:

* 840 (77,8 %) → FAILURE — alarme conservador, erro "seguro";
* 240 (22,2 %) → HEALTHY — falso negativo, todas do espécime `misalignment/shaft/01`.

Isso **não** é falha de ajuste de hiperparâmetro nem de features: restringir o
modelo a features invariantes à carga manteve WARNING em 0,0 %.

#### Por que WARNING é estruturalmente inaprendível aqui

A classe WARNING foi definida como "o nível de menor severidade **de cada
família**". Existem, portanto, apenas **4 espécimes WARNING**, um por família:

| Espécime WARNING | Para onde foi predito |
| :--- | :--- |
| `bearing/inner_race/03` | 100 % FAILURE |
| `bearing/outer_race/03` | 100 % FAILURE |
| `unbalance/rotor/0583` | 100 % FAILURE |
| `misalignment/shaft/01` | 66,7 % HEALTHY, 33,3 % FAILURE |

Ao isolar um espécime WARNING no teste, o modelo perde o **único** exemplo
daquela família naquele nível. Ele precisa então inferir que um defeito de
0,3 mm na pista interna é "leve" tendo visto como leve apenas um desbalanceamento
de 583 mg e um desalinhamento de nível 1 — condições fisicamente sem relação.
E tendo visto a mesma pista interna, com 1,0 e 3,0 mm, rotulada como FAILURE.

O modelo faz o que a física sugere: reconhece a assinatura de pista interna e a
classifica como FAILURE. **A fronteira WARNING/FAILURE é administrativa, não
física** — ela corta perpendicularmente à estrutura real do sinal.

## 3. A classe HEALTHY e o confundimento por carga

O recall de HEALTHY é 4,3 %. A causa é mensurável — `vib_acc1_rms` médio:

| | 0 Nm | 2 Nm | 4 Nm |
| :--- | ---: | ---: | ---: |
| Normal | 0,1023 | 0,1680 | 0,2551 |
| Desbalanceamento 583 mg | 0,0948 | 0,1677 | 0,2471 |
| Desbalanceamento 3.318 mg | 0,1047 | 0,1676 | 0,2314 |

Um motor **saudável a 4 Nm** vibra 2,4× mais que um motor com **desbalanceamento
máximo a 0 Nm**. A carga desloca a feature muito mais do que a falha.

Como existe **um único espécime saudável**, medido uma vez por carga, isolar
`0Nm_Normal` no teste deixa o treino sem qualquer referência de "saudável sob
carga zero" — e o modelo não tem como saber que 0,10 g a 0 Nm é normal.

Restringir o modelo a 56 features invariantes à escala elevou o recall de
HEALTHY de 4,3 % para 32,6 %, ao custo de reduzir a sensibilidade de 93,9 % para
87,9 %. Ajuda, mas não resolve: **o limite é a ausência de um segundo espécime
saudável**, não a engenharia de features.

## 4. Implicação para o desenho do sistema

Um diagnóstico de vibração por valor absoluto pressupõe uma referência. Na
prática industrial essa referência vem de norma (ISO 10816/20816, por classe de
máquina) ou de um **baseline da própria máquina**. O resultado acima é a
demonstração empírica dessa necessidade: sem saber o que é normal *para aquele
motor naquela carga*, o valor medido sozinho não decide.

Isso sugere que o cadastro de motor do sistema deveria incluir uma **medição de
referência em condição saudável**, e que as features do modelo deveriam ser
relativas a esse baseline — mudança de escopo a avaliar, registrada aqui como
consequência do experimento e não como decisão tomada.

## 5. O que É aprendível: tipo de falha, não grau de severidade

Trocando o alvo do modelo — mesmas features, mesmo ensemble, mesmo protocolo
leave-one-specimen-out:

| Alvo | Acurácia |
| :--- | ---: |
| Severidade (HEALTHY / WARNING / FAILURE) | 50,6 % |
| **Família de falha** (normal / rolamento / desalinhamento / desbalanceamento) | **79,6 %** |

Por classe, na predição de família:

| Família | Precisão | Recall | Suporte |
| :--- | ---: | ---: | ---: |
| Rolamento | 1,000 | **1,000** | 1.080 |
| Desbalanceamento | 0,768 | 0,980 | 1.800 |
| Desalinhamento | 0,857 | 0,667 | 1.080 |
| Normal | 0,060 | 0,031 | 540 |

**Rolamento: 1.080 de 1.080 janelas corretas**, em espécimes cujos defeitos o
modelo nunca viu. Desbalanceamento acerta 98 %. Ou seja, a assinatura *física*
do tipo de defeito generaliza entre espécimes — é o grau de severidade que não
generaliza.

Isso separa claramente as duas perguntas do diagnóstico:

* **"que tipo de problema é este?"** — o ML responde bem, e é exatamente o
  insumo que a camada de explicabilidade prevista na especificação precisa
  ("padrão consistente com desalinhamento de eixo");
* **"quão grave está?"** — o ML não responde de forma generalizável com este
  dataset, porque a resposta depende de uma referência de normalidade que o
  dataset não fornece em quantidade suficiente.

A classe `normal` continua colapsando (recall 3,1 %) em todos os cenários
testados, pela causa já descrita na seção 3: espécime saudável único e
confundimento por carga.


## 6. Como reportar a severidade (decisão de projeto)

A severidade permanece sendo prevista **pelo modelo**, e não substituída por
regra normativa. Ela é reportada sob dois protocolos, cada um medindo uma
pergunta diferente:

| Protocolo | Acurácia | Pergunta que responde |
| :--- | ---: | :--- |
| Leave-one-specimen-out | 50,6 % | O modelo gradua um defeito de **tipo e grau inéditos**? |
| Leave-one-load-out (vazamento de espécime declarado) | 89,1 % | Conhecida a escala de severidade da família, o modelo gradua sob **condição de operação nova**? |

> Os dois protocolos estabelecem cenários de dificuldade distintos para a
> generalização do modelo, fornecendo uma faixa de referência metodológica para
> interpretar resultados futuros obtidos em dados de campo.

Note-se explicitamente o que **não** se pode afirmar: que o desempenho em campo
ficará entre 50,6 % e 89,1 %. Esses valores são cenários construídos sobre este
dataset; o resultado em campo depende da distribuição real dos motores
monitorados e pode ficar fora do intervalo, para mais ou para menos.

### Justificativa de por que o piso é severo

Exigir que o modelo gradue a severidade de uma família cuja escala ele nunca viu
é uma exigência irrealista, não um teste de rigor: ver *outras severidades da
mesma família* é conhecimento de domínio legítimo, não vazamento. No KAIST,
porém, cada nível de severidade **é** um espécime distinto, de modo que não há
como separar "mesma montagem" de "mesma família, outro grau". O piso de 50,6 %
resulta dessa limitação do dataset e deve ser lido com essa ressalva.

## 7. Indicadores normativos como camada de validação física

Os indicadores derivados da ISO 10816/20816 **não substituem** a predição do
modelo: entram como camada complementar, exibida ao lado da classe prevista, e
sinalizam divergência entre o diagnóstico estatístico e o critério normativo.

Aplicados ao dataset (razão em relação à condição normal da mesma carga):

| Condição | v_ISO | v_1× | v_2× | a_HF |
| :--- | ---: | ---: | ---: | ---: |
| Normal | 1,0 | 1,0 | 1,0 | 1,0 |
| Desbalanceamento 583 mg | 1,0 | 1,4 | 1,0 | 1,0 |
| Desbalanceamento 1.751 mg | 1,2 | 2,3 | 1,0 | 0,9 |
| Desbalanceamento 3.318 mg | 1,3 | **3,1** | 1,0 | 1,0 |
| Desalinhamento nível 3 | 1,9 | 1,9 | 1,2 | **2,1** |
| Rolamento 0,3 mm | 2,4 | 2,7 | 1,9 | **6,8** |
| Rolamento 1,0 mm | 4,3 | 1,9 | 2,2 | **8,4** |
| Rolamento 3,0 mm | **8,0** | 1,5 | 2,1 | 6,4 |

Cada família tem seu indicador dominante, conforme a teoria de diagnóstico de
vibração: `v_1×` acompanha monotonicamente a massa de desbalanceamento
(1,0 → 1,4 → 2,3 → 3,1) e `a_HF` dispara em falha de rolamento (6,4 a 8,4×).

**Limitação do Critério I:** em magnitude absoluta, todas as 45 sessões caem na
zona A da ISO 10816-1 (máximo de 0,58 mm/s contra limite A/B de 0,71 mm/s),
inclusive rolamentos com defeito de 3,0 mm. A bancada é pequena e rígida, e a
integração para velocidade atenua a alta frequência onde vive a falha de
rolamento. Por isso os indicadores são usados de forma **relativa**, o que
corresponde ao Critério II da própria norma (variação sobre um valor de
referência estabelecido).

## 8. Baseline por motor — opcional

O sistema **não** exige medição de referência. Quando ela existir, registrada
pelo técnico como tal, o diagnóstico ganha uma informação adicional e diretamente
comunicável ao usuário — por exemplo: *"a vibração aumentou 180 % em relação à
condição normal conhecida deste motor"*. Quando não existir, o sistema opera
apenas com a predição do modelo e os indicadores absolutos.

Manter o baseline opcional evita criar uma dependência operacional no fluxo de
campo, que exigiria uma referência válida por motor e por faixa de carga antes
de qualquer diagnóstico.


## 9. Resultados finais — com indicadores normativos nas features

Após incorporar os quatro indicadores normativos (`iso_v_rms_mms`,
`iso_v_1x_mms`, `iso_v_2x_mms`, `iso_a_hf_g`) ao conjunto de features:

| Alvo | Protocolo | Acurácia | Recalls |
| :--- | :--- | ---: | :--- |
| Severidade | leave-one-specimen-out | **63,0 %** | FAILURE 85,3 % · HEALTHY 69,6 % · WARNING 0,0 % |
| Severidade | leave-one-load-out | **95,3 %** | FAILURE 100 % · HEALTHY 89,3 % · WARNING 85,8 % |
| Tipo de falha | leave-one-specimen-out | **88,7 %** | rolamento 100 % · desbal. 98,8 % · normal 76,3 % · desalin. 66,6 % |
| Tipo de falha | leave-one-load-out | 80,6 % | rolamento 100 % · desalin. 86,1 % · normal 77,2 % · desbal. 66,7 % |

### O que mudou e por quê

O recall de HEALTHY sob o protocolo estrito saltou de **4,3 % para 69,6 %**.

A causa é física e vale documentar: a conversão para velocidade,
`V(f) = A(f) / 2πf`, atenua a alta frequência e enfatiza a faixa onde a
condição da máquina se manifesta. O RMS de aceleração — que escalava fortemente
com o torque aplicado (0,10 g a 0 Nm contra 0,26 g a 4 Nm no mesmo motor
saudável) — deixa de dominar a decisão. Os indicadores normativos são, na
prática, **features muito menos confundidas pela carga**, que era exatamente a
origem do colapso da classe HEALTHY descrito na seção 3.

Ou seja: adotar o vocabulário da norma não melhorou apenas a comunicação do
diagnóstico ao usuário — melhorou a própria capacidade preditiva do modelo.

### Nenhum protocolo é uniformemente mais difícil

Para `fault_type`, o leave-one-load-out (80,6 %) é **pior** que o
leave-one-specimen-out (88,7 %): isolar uma condição de carga inteira remove
mais informação útil para identificar o tipo de defeito do que isolar uma
montagem. Para `severity` ocorre o inverso.

Isso reforça a leitura correta dos dois números: eles estabelecem cenários de
dificuldade distintos para a generalização do modelo, fornecendo uma faixa de
referência metodológica para interpretar resultados futuros obtidos em dados de
campo — e não um intervalo dentro do qual o desempenho em campo necessariamente
cairá.

### O que permanece em aberto

O recall de WARNING sob leave-one-specimen-out continua em **0,0 %**, contra
85,8 % sob leave-one-load-out. Confirma-se o diagnóstico da seção 2: a
graduação de severidade exige ter visto a escala daquela família de falha, e o
dataset tem um único espécime por nível.

## 10. Matriz de decisão — cruzamento entre modelo e evidência física

Implementada em `ml/kaist/decision.py`, calibrada por
`ml/scripts/05_calibrate_decision.py`.

### Motivação

O modelo tem um ponto cego conhecido (recall de WARNING = 0,0 % sob o protocolo
estrito). Um sistema que sempre crava uma classe esconde essa limitação; um que
sinaliza divergência entre evidências é honesto sobre ela e direciona a inspeção
humana para onde ela rende mais.

### Como a independência é preservada

Os indicadores normativos também são features do modelo. Perguntar apenas "o
indicador está alto?" seria circular — o modelo já viu aquele número. A segunda
opinião é construída sobre as **proporções adimensionais** entre indicadores,
que codificam a *assinatura* da falha e não sua magnitude:

| Família | `p_1×` | `p_2×` | `p_HF` |
| :--- | ---: | ---: | ---: |
| Desbalanceamento | **0,608** | 0,187 | 2,76 |
| Normal | 0,328 | 0,213 | 2,07 |
| Desalinhamento | 0,299 | 0,178 | **4,16** |
| Rolamento | 0,085 | 0,087 | **4,79** |

Os protótipos são ajustados **apenas no conjunto de treino de cada fold**.

> **A assinatura clássica não se confirmou.** A literatura associa desalinhamento
> a um pico em 2× a rotação. Neste dataset, o `p_2×` do desalinhamento (0,178) é
> **menor** que o da condição normal (0,213); o desalinhamento se manifesta na
> alta frequência (`p_HF` 4,16 contra 2,07). Os protótipos são portanto
> empíricos, e essa divergência com a teoria de referência deve ser reportada.

### Validação: a discordância prediz erro do modelo?

Sim, com força moderada. Varrendo a margem de tolerância:

| Margem | Sinalizado | Erro sinalizado | Erro não sinalizado | Ganho | Erros capturados |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **0,00** | **34,6 %** | **16,7 %** | 8,5 % | **2,0×** | **51 %** |
| 0,50 | 22,2 % | 21,5 % | 8,4 % | 2,6× | 42 % |
| 0,75 | 11,5 % | 25,4 % | 9,5 % | 2,7× | 26 % |
| 1,00 | 6,5 % | 1,0 % | 12,0 % | 0,1× | 1 % |

Adotou-se **concordância estrita (margem 0,00)**: sinaliza 34,6 % das medições,
onde a taxa de erro é 2,0× maior, capturando **51 % de todos os erros**.

### Por que a margem estrita, e não uma margem maior

Margens maiores elevam o "ganho" — a taxa de erro concentrada no que se sinaliza
— mas **capturam menos erros**: de 51 % em margem 0 para 42 % em margem 0,50.
Trocar sensibilidade por precisão contraria a premissa declarada do projeto, em
que um falso negativo de FAILURE custa mais do que uma inspeção desnecessária.
A margem estrita também elimina um parâmetro de configuração, reduzindo a
superfície de erro do sistema.

### Achado contraintuitivo — e por que ele torna o parâmetro perigoso

A partir de margem ≈1,0 **o sinal se inverte**: as janelas sinalizadas passam a
errar *menos* (1,0 %) que as não sinalizadas (12,0 %). Um afastamento físico
extremo indica que a assinatura de referência é que está inadequada — tipicamente
em rolamento, onde o modelo acerta 100 % — e não que o modelo errou. O sinal
útil vive na faixa intermediária de discordância, não no extremo.

A consequência prática é que **o parâmetro não é monotônico**: aumentá-lo com a
intenção de "sinalizar menos" quebra a camada silenciosamente, sem qualquer erro
visível. Esse é um argumento adicional para manter o padrão estrito e alterar o
valor apenas mediante nova calibração.

### Limites — comunicar como confiança, nunca como veredito

* Mesmo discordando, o modelo acerta **83,3 %** das vezes. É um priorizador de
  confiança, não um detector de erro.
* Metade dos erros ocorre com evidências **concordantes** — a camada não os vê.
* A camada física tem viés próprio: ela separa bem rolamento e desbalanceamento
  (assinaturas distintivas), mas confunde normal com desalinhamento, cujos
  quartis de `p_HF` se sobrepõem (normal até 3,59; desalinhamento a partir de
  3,60). Há casos observados em que o modelo acertou `normal` e a camada física
  gerou alarme indevido.

Por isso a saída inclui um **score contínuo de confiança**, além da sinalização
de concordância: a decisão sobre o que fazer com uma medição de baixa confiança
é operacional, não estatística, e deve permanecer visível ao usuário.
