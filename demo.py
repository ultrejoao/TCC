"""
DEMONSTRACAO DO SISTEMA DE PREDICAO DE FALHAS EM MOTORES ELETRICOS
TCC - Joao Vitor Toledo Hass

Simula o fluxo completo: uma medicao chega do tecnico em campo, o sistema
extrai features, o modelo classifica, os indicadores normativos sao calculados
e a matriz de decisao cruza as duas evidencias.

COMO RODAR NO VSCODE
--------------------
1. Abra a pasta do projeto no VSCode
2. Abra este arquivo (demo.py)
3. Pressione F5, ou clique no botao "Run Python File" (triangulo no canto)

Ou pelo terminal integrado (Ctrl+'):
    python demo.py                      -> demonstra 4 casos representativos
    python demo.py 0Nm_BPFO_10          -> demonstra uma sessao especifica
    python demo.py --listar             -> lista todas as sessoes disponiveis
    python demo.py --metricas           -> mostra as metricas de validacao
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ml"))

from config import ARTIFACTS, DATA_INTERIM  # noqa: E402
from kaist.decision import decide  # noqa: E402
from kaist.severity import ZONE_TO_LABEL, iso_zone  # noqa: E402

W = 68
INDICATORS = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]

NOME_TIPO = {
    "bearing": "ROLAMENTO",
    "misalignment": "DESALINHAMENTO DE EIXO",
    "unbalance": "DESBALANCEAMENTO DE ROTOR",
    "normal": "SEM FALHA DETECTADA",
}
NOME_LOCAL = {
    "inner_race": "pista interna", "outer_race": "pista externa",
    "shaft": "eixo", "rotor": "rotor", "none": "-",
}


def linha(c="-"):
    print(c * W)


def titulo(txt):
    print()
    linha("=")
    print(f" {txt}")
    linha("=")


def secao(txt):
    print()
    print(f" {txt}")
    linha("-")


def campo(rotulo, valor, largura=38):
    pontos = "." * max(largura - len(rotulo), 3)
    print(f"   {rotulo} {pontos} {valor}")


def carregar_modelo():
    caminho = ARTIFACTS / "model_kaist_full_v1.joblib"
    if not caminho.exists():
        print("\n[ERRO] Modelo nao encontrado.")
        print("Rode primeiro:  python ml/scripts/09_train_profiles.py\n")
        sys.exit(1)
    return joblib.load(caminho)


def prever(bundle, linha_features):
    """Executa o ensemble nos dois alvos para uma janela."""
    X = linha_features[bundle["feature_columns"]].to_numpy(dtype=np.float32).reshape(1, -1)
    saida = {}
    for alvo, cfg in bundle["targets"].items():
        proba = (cfg["rf"].predict_proba(X) + cfg["xgb"].predict_proba(X)) / 2.0
        i = int(proba[0].argmax())
        saida[alvo] = (cfg["classes"][i], float(proba[0][i]))
    return saida


def demonstrar(bundle, df, session_id, baseline_por_carga, oof=None):
    janelas = df[df.session_id == session_id]
    if janelas.empty:
        print(f"[ERRO] sessao '{session_id}' nao encontrada. Use --listar.")
        return
    reg = janelas.iloc[len(janelas) // 2]        # janela do meio da gravacao

    titulo(f"MEDICAO RECEBIDA  -  {session_id}")
    campo("Carga aplicada", f"{int(reg.load_nm)} Nm")
    campo("Duracao da janela", "1,0 s @ 25.600 Hz")
    campo("Canais", "4 acelerometros + 1 fase de corrente")

    # Predicao HONESTA: usa o resultado out-of-fold, de um modelo que nao viu
    # este especime. O modelo de producao e treinado com todas as 45 sessoes e
    # portanto NAO pode ser demonstrado sobre os proprios dados de treino.
    linha_oof = None
    if oof is not None:
        m = oof[(oof.session_id == session_id) & (oof.window_index == reg.window_index)]
        if not m.empty:
            linha_oof = m.iloc[0]

    if linha_oof is not None:
        tipo, p_tipo = linha_oof.oof_fault_type, float(linha_oof.oof_fault_type_proba)
        sev, p_sev = linha_oof.oof_severity, float(linha_oof.oof_severity_proba)
        origem = "out-of-fold: o modelo NUNCA viu este especime"
    else:
        pred = prever(bundle, reg)
        tipo, p_tipo = pred["fault_type"]
        sev, p_sev = pred["severity"]
        origem = "AVISO: modelo de producao, treinado COM esta sessao"

    secao("DIAGNOSTICO DO MODELO (Random Forest + XGBoost)")
    campo("Tipo de falha", f"{NOME_TIPO.get(tipo, tipo):28s} {p_tipo:5.1%}")
    campo("Severidade", f"{sev:28s} {p_sev:5.1%}")
    print(f"\n   [{origem}]")

    indicadores = {k: float(reg[k]) for k in INDICATORS}
    zona = iso_zone(indicadores["iso_v_rms_mms"])

    secao("INDICADORES NORMATIVOS (ISO 10816 / 20816)")
    campo("Velocidade RMS 10-1000 Hz", f"{indicadores['iso_v_rms_mms']:7.3f} mm/s   zona {zona}")
    campo("Componente 1x  (desbalanceamento)", f"{indicadores['iso_v_1x_mms']:7.3f} mm/s")
    campo("Componente 2x  (desalinhamento)", f"{indicadores['iso_v_2x_mms']:7.3f} mm/s")
    campo("Aceleracao 1-10 kHz  (rolamento)", f"{indicadores['iso_a_hf_g']:7.3f} g")
    print(f"\n   Criterio I (magnitude absoluta): zona {zona} -> {ZONE_TO_LABEL[zona]}")

    base = baseline_por_carga.get(int(reg.load_nm))
    d = decide(tipo, p_tipo, sev, p_sev, indicadores,
               bundle["physical_signature"], baseline_change=None)

    if base is not None:
        secao("CRITERIO II - COMPARACAO COM A REFERENCIA DO MOTOR")
        print("   (baseline opcional: medicao marcada pelo tecnico como normal)")
        print()
        for k, rotulo in [("iso_v_rms_mms", "Vibracao global"),
                          ("iso_v_1x_mms", "Componente 1x"),
                          ("iso_a_hf_g", "Alta frequencia")]:
            var = (indicadores[k] / (base[k] + 1e-9) - 1) * 100
            seta = "+" if var >= 0 else ""
            campo(rotulo, f"{seta}{var:7.1f}%")

    secao("MATRIZ DE DECISAO  -  modelo x evidencia fisica")
    campo("Assinatura fisica indica", NOME_TIPO.get(d.physical_type, d.physical_type))
    campo("Proporcao 1x / global", f"{d.proportions['p_1x']:.3f}")
    campo("Proporcao alta freq. / global", f"{d.proportions['p_hf']:.3f}")
    print()
    status = "CONCORDANTES" if d.agreement else "DISCORDANTES"
    campo("Evidencias", status)
    barra = "#" * int(d.confidence * 30)
    campo("Confianca", f"{d.confidence:5.1%}  {barra}")

    secao("RECOMENDACAO")
    for pedaco in _quebrar(d.recommendation, W - 6):
        print(f"   {pedaco}")

    print()
    real_tipo = "normal" if reg.fault_family == "normal" else reg.fault_family
    ok_t = "OK" if real_tipo == tipo else "ERRO"
    ok_s = "OK" if reg.label == sev else "ERRO"
    print(f"   [conferencia] condicao real: {NOME_TIPO.get(real_tipo, real_tipo)} / "
          f"{reg.label}  ->  tipo {ok_t}, severidade {ok_s}")
    print()


def _quebrar(texto, largura):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > largura:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def mostrar_metricas():
    caminho = DATA_INTERIM / "evaluation_summary.csv"
    if not caminho.exists():
        print("[ERRO] rode antes:  python ml/scripts/04_evaluate.py")
        return
    titulo("METRICAS DE VALIDACAO")
    print(pd.read_csv(caminho).to_string(index=False))
    print()
    print(" Os dois protocolos estabelecem cenarios de dificuldade distintos")
    print(" para a generalizacao do modelo, fornecendo uma faixa de referencia")
    print(" metodologica para interpretar resultados futuros obtidos em dados")
    print(" de campo.")
    print()
    print(" Split adotado: leave-one-specimen-out. A unidade experimental")
    print(" independente e o ESPECIME (a montagem fisica), nao a janela nem a")
    print(" sessao: as 3 cargas de um mesmo defeito foram medidas com 6 a 43")
    print(" minutos de intervalo, sem desmontagem.")
    print()
    print(" Para comparacao, o mesmo modelo com split aleatorio por janela")
    print(" atinge 100,0% de acuracia - a medida exata do vazamento de dados")
    print(" que o split por especime evita.")
    print()


def main():
    args = sys.argv[1:]
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")

    if "--metricas" in args:
        mostrar_metricas()
        return

    if "--listar" in args:
        titulo("SESSOES DISPONIVEIS")
        for _, r in (df.groupby("session_id")
                       .agg(condicao=("fault_family", "first"),
                            severidade=("label", "first"),
                            carga=("load_nm", "first"))
                       .reset_index().iterrows()):
            print(f"   {r.session_id:24s} {r.condicao:14s} {r.severidade:8s} {int(r.carga)} Nm")
        print()
        return

    bundle = carregar_modelo()

    # baseline opcional: a sessao normal de cada carga faz o papel da medicao
    # de referencia que o tecnico registraria no cadastro do motor
    baseline = {}
    for carga in sorted(df.load_nm.unique()):
        nrm = df[(df.fault_family == "normal") & (df.load_nm == carga)]
        if not nrm.empty:
            baseline[int(carga)] = {k: float(nrm[k].median()) for k in INDICATORS}

    # predicoes out-of-fold: modelo que nunca viu o especime testado
    oof = None
    caminho_oof = DATA_INTERIM / "oof_predictions.parquet"
    if caminho_oof.exists():
        candidato = pd.read_parquet(caminho_oof)
        if "oof_fault_type" in candidato.columns:
            oof = candidato

    if args:
        demonstrar(bundle, df, args[0], baseline, oof)
        return

    titulo("DEMONSTRACAO - 4 CASOS REPRESENTATIVOS")
    print(" Cada caso e uma medicao real do dataset KAIST passando pelo")
    print(" sistema completo, como se viesse do formulario do tecnico.")
    if oof is None:
        print("\n [!] predicoes out-of-fold ausentes: rode antes")
        print("     python ml/scripts/07_generate_oof.py")
    # Roteiro: tres acertos e um caso que abre a discussao metodologica.
    # Todos com predicao out-of-fold — modelo que nunca viu o especime.
    roteiro = [
        ("0Nm_Normal", "motor saudavel corretamente identificado"),
        ("0Nm_Unbalance_3318mg", "desbalanceamento: tipo e severidade corretos"),
        ("0Nm_BPFO_10", "falha de rolamento em estagio avancado"),
        ("0Nm_BPFI_30", "acerta o TIPO, erra a SEVERIDADE - ver limitacao"),
    ]
    for sid, nota in roteiro:
        demonstrar(bundle, df, sid, baseline, oof)
        print(f"   >> {nota}")
        input("\n   [ENTER para o proximo caso] ")

    titulo("SOBRE O ULTIMO CASO")
    print(" O modelo acertou o tipo (rolamento, 100% das janelas) mas errou a")
    print(" severidade. Nao e um defeito de ajuste: sob leave-one-specimen-out")
    print(" o especime isolado e o UNICO exemplar daquele grau de severidade,")
    print(" entao o modelo precisa graduar uma escala que nunca viu.")
    print()
    print(" O recall de WARNING e 0,0% sob este protocolo e 85,8% quando o")
    print(" modelo ja conhece a escala da familia. A distancia entre os dois")
    print(" numeros e um resultado do trabalho, nao um constrangimento.")
    print()


if __name__ == "__main__":
    main()
