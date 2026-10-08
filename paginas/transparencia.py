# -*- coding: utf-8 -*-
"""Portal da Transparencia (CGU) - console completo dos 106 endpoints.

A tela nao tem um formulario fixo por endpoint: ela le o catalogo OpenAPI da
CGU e monta o formulario de cada consulta a partir dele. Assim os 17 grupos
tematicos e os 106 endpoints ficam disponiveis, e qualquer endpoint novo que a
CGU publicar aparece sozinho.
"""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import transparencia as tp

CHAVE = "transparencia"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    with st.spinner("Carregando o catalogo da CGU..."):
        grupos, resp = tp.catalogo(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)

    if not tp.tem_chave():
        st.warning(
            "O Portal da Transparencia exige uma chave gratuita para consultar. "
            "Um administrador cadastra a chave em **Administracao > Fontes de "
            "Dados > Chaves de API**. O cadastro leva um minuto em "
            "portaldatransparencia.gov.br com a conta gov.br.",
            icon=":material/key_off:")
        st.link_button("Solicitar a chave gratuita (CGU)", tp.URL_CADASTRO,
                       icon=":material/open_in_new:")
        return

    if not ui.verificar(resp, "catalogo da CGU"):
        return
    if not grupos:
        ui.vazio("O catalogo nao retornou endpoints.")
        return

    total_endpoints = sum(len(v) for v in grupos.values())
    st.caption("%d consultas disponiveis em %d grupos tematicos."
               % (total_endpoints, len(grupos)))

    f1, f2 = st.columns([0.4, 0.6])
    with f1:
        grupo = st.selectbox("Grupo tematico", list(grupos.keys()))
    with f2:
        endpoints = grupos[grupo]
        rotulos = {e["caminho"]: e["resumo"] for e in endpoints}
        caminho = st.selectbox("Consulta", list(rotulos.keys()),
                               format_func=lambda c: rotulos[c])

    endpoint = tp.endpoint_por_caminho(grupos, caminho)
    if endpoint and endpoint["descricao"]:
        st.caption(endpoint["descricao"])

    # ---- formulario montado a partir do catalogo ----
    with st.form("form_cgu_%s" % caminho.replace("/", "_")):
        valores = {}
        params = endpoint["parametros"] if endpoint else []
        # Coloca os obrigatorios primeiro
        params = sorted(params, key=lambda p: (not p["obrigatorio"], p["nome"]))
        colunas = st.columns(2)
        for i, p in enumerate(params):
            with colunas[i % 2]:
                rotulo = "%s%s" % (p["nome"], " *" if p["obrigatorio"] else "")
                ajuda = p["ajuda"] or None
                if p["nome"] == "pagina":
                    valores[p["nome"]] = st.number_input(
                        rotulo, min_value=1, value=1, step=1, help=ajuda)
                elif p["opcoes"]:
                    valores[p["nome"]] = st.selectbox(rotulo, [""] + p["opcoes"],
                                                      help=ajuda)
                elif p["tipo"] == "integer":
                    txt = st.text_input(rotulo, help=ajuda,
                                        placeholder="numero inteiro")
                    valores[p["nome"]] = txt
                else:
                    valores[p["nome"]] = st.text_input(rotulo, help=ajuda)
        enviar = st.form_submit_button("Consultar", type="primary",
                                       icon=":material/search:")

    if not enviar:
        ui.nota(
            "Preencha os campos marcados com * (obrigatorios) e clique em Consultar. "
            "As datas seguem o formato DD/MM/AAAA e os periodos, AAAAMM, conforme a "
            "ajuda de cada campo. Consultas por CPF exigem que o CPF seja informado "
            "por completo."
        )
        return

    faltando = [p["nome"] for p in params
                if p["obrigatorio"] and not str(valores.get(p["nome"], "")).strip()]
    if faltando:
        st.error("Preencha os campos obrigatorios: %s" % ", ".join(faltando),
                 icon=":material/error:")
        return

    audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_TRANSPARENCIA",
                    "endpoint=%s" % caminho)

    with st.spinner("Consultando a CGU..."):
        df, r = tp.consultar(caminho, tuple(sorted(valores.items())), forcar)

    if not ui.verificar(r, "Portal da Transparencia"):
        return
    if df.empty:
        ui.vazio("A consulta nao retornou registros. Revise os filtros - a CGU "
                 "costuma exigir combinacoes especificas (mes/ano + orgao, por ex.).")
        return

    st.metric("Registros retornados", ui.inteiro(len(df)))
    st.caption(r.selo())
    ui.tabela(df, "cgu_%s" % caminho.strip("/").replace("/", "_"), altura=440)

    ui.nota(
        "Fonte: Portal da Transparencia do Governo Federal (CGU). A API pagina os "
        "resultados - avance o campo 'pagina' para ver mais. Consultas sao "
        "registradas na auditoria do sistema."
    )
