# -*- coding: utf-8 -*-
"""Correspondentes no pais - rede credenciada do sistema financeiro."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "correspondentes"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2, f3 = st.columns([0.22, 0.36, 0.42])
    with f1:
        uf = st.selectbox("UF", UFS, index=UFS.index("SP"))
    with f2:
        contratante = st.text_input("Instituicao contratante",
                                    placeholder="Ex.: BANCO PAN")
    with f3:
        busca = st.text_input("Buscar correspondente",
                              placeholder="Nome ou CNPJ do correspondente")

    # SP sozinho passa de 30 mil vinculos; o teto evita travar a tela, mas o
    # usuario precisa saber quando o conjunto veio cortado.
    LIMITE = 50000
    with st.spinner("Consultando a rede de correspondentes de %s..." % uf):
        df, resp = bcb.correspondentes(uf, "", contratante.strip(), LIMITE, forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "correspondentes no pais"):
        return
    if df.empty:
        ui.vazio("Nenhum correspondente encontrado com esses filtros.")
        return

    ui.aviso_truncado(len(df), LIMITE,
                      "Informe a instituicao contratante para reduzir o conjunto.")

    filtrado = df.copy()
    if busca:
        alvo = busca.strip().upper()
        digitos = "".join(ch for ch in alvo if ch.isdigit())
        mascara = filtrado["NomeCorrespondente"].astype(str).str.upper().str.contains(
            alvo, na=False)
        if digitos:
            mascara = mascara | filtrado["CnpjCorrespondente"].astype(str).str.contains(
                digitos, na=False)
        filtrado = filtrado[mascara]
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_CORRESPONDENTE",
                        "UF=%s termo=%s" % (uf, busca.strip()[:80]))

    posicao = df["Posicao"].dropna().iloc[0] if "Posicao" in df and not df.empty else "-"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Vinculos encontrados", ui.inteiro(len(filtrado)))
    with c2:
        st.metric("Correspondentes distintos",
                  ui.inteiro(filtrado["CnpjCorrespondente"].nunique()))
    with c3:
        st.metric("Contratantes", ui.inteiro(filtrado["NomeContratante"].nunique()))
    with c4:
        st.metric("Posicao da base", posicao,
                  help="Data de referencia informada pelo proprio Banco Central.")

    st.write("")
    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("##### Contratantes com maior rede")
        st.bar_chart(filtrado["NomeContratante"].value_counts().head(12),
                     height=300, horizontal=True, color="#2563EB")
    with dir_:
        st.markdown("##### Municipios com mais pontos")
        st.bar_chart(filtrado["Municipio"].value_counts().head(12),
                     height=300, horizontal=True, color="#0EA5E9")

    exibir = filtrado.copy()
    for coluna in ("CnpjContratante", "CnpjCorrespondente"):
        if coluna in exibir:
            exibir[coluna] = exibir[coluna].map(ui.cnpj_formatado)
    exibir = exibir.rename(columns={
        "NomeContratante": "Contratante", "CnpjContratante": "CNPJ contratante",
        "NomeCorrespondente": "Correspondente",
        "CnpjCorrespondente": "CNPJ correspondente", "Tipo": "Tipo",
        "Municipio": "Municipio", "ServicosCorrespondentes": "Servicos autorizados",
        "Posicao": "Posicao"})
    ordem = [c for c in ("Correspondente", "CNPJ correspondente", "Contratante",
                         "CNPJ contratante", "Tipo", "Municipio", "UF",
                         "Servicos autorizados", "Posicao") if c in exibir.columns]
    ui.tabela(exibir[ordem] if ordem else exibir, "correspondentes_%s" % uf, altura=440)

    ui.nota(
        "Um mesmo CNPJ pode aparecer varias vezes: cada linha e um vinculo com uma "
        "instituicao contratante diferente. A coluna de servicos autorizados indica "
        "os incisos do normativo que o correspondente pode executar."
    )
