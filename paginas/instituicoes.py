# -*- coding: utf-8 -*-
"""Instituicoes autorizadas a funcionar no pais."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb, externas

CHAVE = "instituicoes"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2, f3 = st.columns([0.42, 0.30, 0.28])
    with f1:
        tipo = st.selectbox("Tipo de instituicao", list(bcb.TIPOS_INSTITUICAO.keys()))
    recurso = bcb.TIPOS_INSTITUICAO[tipo]

    with st.spinner("Carregando cadastro oficial..."):
        df, resp = bcb.instituicoes(recurso, forcar)

    ufs = sorted(df["UF"].dropna().unique().tolist()) if "UF" in df else []
    with f2:
        uf = st.selectbox("UF", ["(todas)"] + ufs)
    with f3:
        busca = st.text_input("Buscar", placeholder="Nome ou CNPJ")

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "cadastro de instituicoes"):
        return
    if df.empty:
        ui.vazio("A fonte nao retornou registros para este tipo.")
        return

    filtrado = df.copy()
    if uf != "(todas)":
        filtrado = filtrado[filtrado["UF"] == uf]
    if busca:
        alvo = busca.strip().upper()
        digitos = "".join(ch for ch in alvo if ch.isdigit())
        mascara = filtrado["NOME_INSTITUICAO"].astype(str).str.upper().str.contains(
            alvo, na=False)
        if digitos:
            mascara = mascara | filtrado["CNPJ"].astype(str).str.contains(digitos, na=False)
        filtrado = filtrado[mascara]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Instituicoes listadas", ui.inteiro(len(filtrado)))
    with c2:
        st.metric("Unidades da federacao",
                  ui.inteiro(filtrado["UF"].nunique()) if "UF" in filtrado else "-")
    with c3:
        if "SEGMENTO" in filtrado and not filtrado.empty:
            st.metric("Segmentos", ui.inteiro(filtrado["SEGMENTO"].nunique()))

    st.write("")
    exibir = filtrado.copy()
    if "CNPJ" in exibir:
        exibir["CNPJ"] = exibir["CNPJ"].map(ui.cnpj_formatado)
    renomear = {
        "NOME_INSTITUICAO": "Instituicao", "SEGMENTO": "Segmento",
        "MUNICIPIO": "Municipio", "SITIO_NA_INTERNET": "Site",
        "E_MAIL": "E-mail", "CARTEIRA_COMERCIAL": "Carteira comercial",
        "TELEFONE": "Telefone", "DDD": "DDD", "CEP": "CEP",
        "ENDERECO": "Endereco", "BAIRRO": "Bairro",
    }
    exibir = exibir.rename(columns=renomear)
    ordem = [c for c in ("Instituicao", "CNPJ", "Segmento", "Municipio", "UF",
                         "DDD", "Telefone", "E-mail", "Site", "Endereco",
                         "Bairro", "CEP") if c in exibir.columns]
    ui.tabela(exibir[ordem] if ordem else exibir, "instituicoes_%s" % recurso,
              altura=480, config={"Site": st.column_config.LinkColumn("Site")})

    with st.expander("Codigo COMPE e ISPB dos bancos (BrasilAPI)",
                     icon=":material/pin:"):
        st.caption(
            "O cadastro do Banco Central nao traz o codigo COMPE. Esta tabela "
            "complementar resolve a correspondencia entre nome, codigo do banco "
            "e ISPB - util para conferir dados bancarios de terceiros."
        )
        bancos_df, r_bancos = externas.bancos(forcar)
        if not bancos_df.empty:
            bancos_df = bancos_df.rename(columns={
                "code": "COMPE", "name": "Nome curto",
                "fullName": "Razao social", "ispb": "ISPB"})
            ui.tabela(bancos_df.sort_values("Nome curto"), "bancos_compe_ispb",
                      altura=320)
            st.caption(r_bancos.selo())

    ui.nota(
        "Fonte: relacao de instituicoes em funcionamento no pais, publicada pelo "
        "Banco Central. Aparecer nesta lista significa autorizacao para funcionar - "
        "e o primeiro item a conferir antes de qualquer relacionamento comercial."
    )
