# -*- coding: utf-8 -*-
"""Executa cada tela do sistema de ponta a ponta, sem navegador.

Usa o framework de teste do proprio Streamlit (AppTest): o script da pagina e
executado de verdade, com as chamadas reais as APIs publicas. Qualquer erro de
runtime - coluna inexistente, tipo errado, widget duplicado - aparece aqui.

Uso:  .venv\\Scripts\\python.exe scripts\\teste_paginas.py
"""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from streamlit.testing.v1 import AppTest  # noqa: E402

from core.modulos import MODULOS  # noqa: E402

MODELO = """
import sys
sys.path.insert(0, r"{raiz}")
import streamlit as st
from core import db, ui
db.inicializar()
ui.injetar_css()
st.session_state["ip_usuario_id"] = 1   # administrador criado na instalacao
from paginas import {arquivo}
{arquivo}.render()
"""

falhas = []
lentas = []

print("\nExecutando %d telas com dados reais das APIs...\n" % len(MODULOS))
print("%-34s %-10s %s" % ("TELA", "TEMPO", "RESULTADO"))
print("-" * 78)

for modulo in MODULOS:
    script = MODELO.format(raiz=str(RAIZ), arquivo=modulo["arquivo"])
    inicio = time.perf_counter()
    try:
        app = AppTest.from_string(script)
        app.run(timeout=180)
        segundos = time.perf_counter() - inicio

        if app.exception:
            detalhe = "; ".join(str(e.message)[:150] for e in app.exception)
            falhas.append((modulo["titulo"], detalhe))
            print("%-34s %-10s ERRO: %s" % (modulo["titulo"][:33],
                                            "%.1fs" % segundos, detalhe[:70]))
            continue

        # Uma tela util produz alguma coisa: metrica, tabela, grafico ou aviso.
        produziu = (len(app.metric) + len(app.dataframe) + len(app.markdown)
                    + len(app.info) + len(app.warning) + len(app.error))
        erros_visiveis = [e.value for e in app.error]
        if erros_visiveis:
            falhas.append((modulo["titulo"], "st.error na tela: %s"
                           % erros_visiveis[0][:150]))
            print("%-34s %-10s FALHA (mensagem de erro na tela)"
                  % (modulo["titulo"][:33], "%.1fs" % segundos))
        elif produziu == 0:
            falhas.append((modulo["titulo"], "a tela nao renderizou nada"))
            print("%-34s %-10s FALHA (tela vazia)"
                  % (modulo["titulo"][:33], "%.1fs" % segundos))
        else:
            if segundos > 20:
                lentas.append((modulo["titulo"], segundos))
            print("%-34s %-10s OK  (%d metricas, %d tabelas)"
                  % (modulo["titulo"][:33], "%.1fs" % segundos,
                     len(app.metric), len(app.dataframe)))
    except Exception as exc:
        segundos = time.perf_counter() - inicio
        falhas.append((modulo["titulo"], "%s: %s" % (type(exc).__name__, exc)))
        print("%-34s %-10s EXCECAO: %s" % (modulo["titulo"][:33],
                                           "%.1fs" % segundos,
                                           str(exc)[:60]))

print("-" * 78)
if lentas:
    print("\nTelas lentas na primeira carga (cache frio):")
    for titulo, seg in lentas:
        print("  %-40s %.1fs" % (titulo, seg))

if falhas:
    print("\n%d tela(s) com problema:\n" % len(falhas))
    for titulo, detalhe in falhas:
        print("  %s\n    %s\n" % (titulo, detalhe))
    sys.exit(1)

print("\nTodas as %d telas renderizaram sem erro." % len(MODULOS))
sys.exit(0)
