# Amostras para demonstracao

Sinais recortados do dataset KAIST para testar o sistema pela interface.

**Todos vem de especimes RESERVADOS**: montagens excluidas do treino do
modelo de producao. O diagnostico sobre estes arquivos mostra o
comportamento diante de um defeito inedito.

Cada arquivo tem 5 s de um canal de vibracao, amostrado a
25.600 Hz, em m/s^2.

## Como usar

Na tela **Coletar**, escolha o motor, envie o arquivo e informe:

- taxa de amostragem: **25600**
- unidade: **m/s^2**
- carga: conforme o nome do arquivo (0, 2 ou 4 Nm)

Para ver a severidade pelo criterio de variacao (mais sensivel), envie
antes o arquivo `2Nm_Normal.csv` marcado como **medicao de
referencia** — ele e a condicao saudavel do mesmo motor.

## Arquivos

| arquivo | condicao real | carga |
| :--- | :--- | ---: |
| `0Nm_BPFO_10.csv` | rolamento com defeito de 1,0 mm na pista externa | 0 Nm |
| `0Nm_Misalign_03.csv` | desalinhamento de eixo, nivel 2 de 3 | 0 Nm |
| `0Nm_Unbalance_2239mg.csv` | desbalanceamento de rotor, 2.239 mg | 0 Nm |
| `2Nm_BPFO_10.csv` | rolamento com defeito de 1,0 mm na pista externa | 2 Nm |
| `2Nm_Misalign_03.csv` | desalinhamento de eixo, nivel 2 de 3 | 2 Nm |
| `2Nm_Normal.csv` | condicao normal (saudavel) | 2 Nm |
| `2Nm_Unbalance_2239mg.csv` | desbalanceamento de rotor, 2.239 mg | 2 Nm |
| `4Nm_BPFO_10.csv` | rolamento com defeito de 1,0 mm na pista externa | 4 Nm |
| `4Nm_Misalign_03.csv` | desalinhamento de eixo, nivel 2 de 3 | 4 Nm |
| `4Nm_Unbalance_2239mg.csv` | desbalanceamento de rotor, 2.239 mg | 4 Nm |

## O que esperar

O modelo identifica o TIPO de falha; a severidade vem de criterio fisico
(ISO 10816). Sem medicao de referencia, a severidade usa a magnitude
absoluta e tende a subestimar — nesta bancada os valores sao baixos, e
mesmo um defeito severo permanece na zona B.

A condicao normal e o caso mais dificil: o modelo acerta o tipo em 77%
dos casos, e pode confundi-la com desalinhamento. Isso esta documentado
em docs/02-resultados-baseline.md.