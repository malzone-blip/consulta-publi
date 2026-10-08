# -*- coding: utf-8 -*-
"""Verificacao de credenciado: um CNPJ contra todas as bases de sancao."""
import pandas as pd
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import externas, transparencia as tp

CHAVE = "verificar_credenciado"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    if not tp.tem_chave():
        st.warning(
            "Esta verificacao usa o Portal da Transparencia, que exige a chave "
            "gratuita da CGU. Um administrador cadastra a chave em Administracao > "
            "Fontes de Dados > Chaves de API.", icon=":material/key_off:")
        st.link_button("Solicitar a chave gratuita (CGU)", tp.URL_CADASTRO,
                       icon=":material/open_in_new:")
        return

    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        documento = st.text_input(
            "CNPJ ou CPF do credenciado",
            placeholder="00.000.000/0000-00 ou 000.000.000-00")
    with c2:
        st.write("")
        verificar = st.button("Verificar", type="primary", use_container_width=True,
                              icon=":material/policy:")

    if not (verificar and documento.strip()):
        ui.nota(
            "Digite o CNPJ de um credenciado e o sistema consulta de uma so vez: "
            "cadastro consolidado da empresa, CEIS (inidoneas), CNEP (Lei "
            "Anticorrupcao), CEPIM (impedidas de receber recursos), acordos de "
            "leniencia e os contratos federais do CNPJ. Para CPF, verifica CEIS, "
            "CNEP e o CEAF (expulsoes)."
        )
        return

    with st.spinner("Consultando as bases de integridade..."):
        # Dados cadastrais complementares (BrasilAPI) rodam junto
        cnpj_dados, _ = externas.consultar_cnpj(documento) \
            if len("".join(c for c in documento if c.isdigit())) == 14 else (None, "")
        resultado, erro = tp.verificar_documento(documento.strip(), forcar)

    if erro:
        st.error(erro, icon=":material/error:")
        return

    audit.registrar(auth.usuario_atual()["usuario"], "VERIFICACAO_CREDENCIADO",
                    "documento=%s tipo=%s" % (resultado["documento"], resultado["tipo"]))

    # ---- cartao de identificacao ----
    if cnpj_dados:
        st.markdown("#### %s" % (cnpj_dados.get("razao_social") or "Empresa"))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Situacao cadastral",
                      str(cnpj_dados.get("descricao_situacao_cadastral", "-")).title())
        with c2:
            st.metric("Porte", str(cnpj_dados.get("porte", "-")).title())
        with c3:
            st.metric("Abertura",
                      ui.data_br(cnpj_dados.get("data_inicio_atividade")) or "-")
    else:
        st.markdown("#### Documento %s" % ui.cnpj_formatado(resultado["documento"]))

    # ---- veredito de sancoes ----
    total_sancoes = sum(f["quantidade"] for f in resultado["sancoes"])
    erros = [f for f in resultado["sancoes"] if f["erro"]]

    if total_sancoes == 0 and not erros:
        st.success(
            "**Nada consta.** Nenhum registro nas bases de sancao consultadas "
            "(CEIS, CNEP, CEPIM, leniencia%s). Isso reduz o risco, mas nao "
            "substitui a analise formal - confirme sempre o documento completo."
            % (", CEAF" if resultado["tipo"] == "cpf" else ""),
            icon=":material/verified:")
    elif total_sancoes > 0:
        st.error(
            "**Atencao: %d registro(s) de sancao encontrado(s).** Verifique cada "
            "base abaixo antes de qualquer decisao - pode haver homonimia ou "
            "sancao ja expirada." % total_sancoes,
            icon=":material/report:")

    if erros:
        st.warning("Algumas bases nao responderam agora (%s). Repita a verificacao "
                   "em instantes." % ", ".join(e["rotulo"].split(" - ")[0]
                                               for e in erros),
                   icon=":material/warning:")

    # ---- placar por base ----
    st.write("")
    placar = pd.DataFrame([{
        "Base": f["rotulo"],
        "Registros": f["quantidade"],
        "Situacao": "CONSTA" if f["quantidade"] > 0 else
                    ("indisponivel" if f["erro"] else "nada consta"),
    } for f in resultado["sancoes"]])
    st.dataframe(placar, use_container_width=True, hide_index=True, column_config={
        "Registros": st.column_config.NumberColumn(format="%d"),
    })

    # ---- detalhe das bases com registro ----
    for f in resultado["sancoes"]:
        if f["quantidade"] > 0:
            with st.expander("%s - %d registro(s)" % (f["rotulo"], f["quantidade"]),
                             icon=":material/gavel:", expanded=True):
                ui.tabela(pd.json_normalize(f["registros"]),
                          "sancao_%s" % f["caminho"].strip("/").replace("/", "_"),
                          altura=280)

    # ---- contratos federais ----
    if resultado.get("contratos"):
        st.markdown("##### Contratos federais deste CNPJ")
        ui.tabela(pd.json_normalize(resultado["contratos"]), "contratos_cnpj",
                  altura=280)

    ui.nota(
        "Fontes: Portal da Transparencia (CGU) e Receita (via BrasilAPI). Esta tela "
        "e um apoio a decisao: 'nada consta' nao e certidao negativa, e 'consta' "
        "exige conferir documento completo, vigencia e eventual homonimia. Cada "
        "verificacao fica registrada na auditoria."
    )
