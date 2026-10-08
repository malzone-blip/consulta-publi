# -*- coding: utf-8 -*-
"""IF.data - dados contabeis e prudenciais das instituicoes financeiras."""
from datetime import date

import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "ifdata"

TIPOS = {
    1: "Tipo 1 - Conglomerados prudenciais e instituicoes independentes",
    2: "Tipo 2 - Conglomerados financeiros e instituicoes independentes",
    3: "Tipo 3 - Instituicoes individuais",
    4: "Tipo 4 - Visao consolidada",
}


def _trimestres(quantidade: int = 12):
    """Lista dos ultimos AnoMes trimestrais publicados (03, 06, 09, 12)."""
    hoje = date.today()
    saida = []
    ano, mes = hoje.year, ((hoje.month - 1) // 3) * 3
    if mes == 0:
        ano, mes = ano - 1, 12
    while len(saida) < quantidade:
        saida.append(int("%d%02d" % (ano, mes)))
        mes -= 3
        if mes <= 0:
            ano, mes = ano - 1, 12
    return saida


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    trimestres = _trimestres()
    f1, f2, f3 = st.columns(3)
    with f1:
        anomes = st.selectbox(
            "Data-base", trimestres, index=1,
            format_func=lambda v: "%s/%s" % (str(v)[4:], str(v)[:4]),
            help="O IF.data e trimestral e sai com alguns meses de defasagem. "
                 "Se o trimestre mais recente vier vazio, escolha o anterior.",
        )
    with f2:
        tipo = st.selectbox("Tipo de instituicao", list(TIPOS.keys()),
                            format_func=lambda t: TIPOS[t])

    with st.spinner("Carregando relatorios disponiveis..."):
        relatorios, r_rel = bcb.ifdata_relatorios(forcar)

    opcoes_rel = {}
    if not relatorios.empty:
        opcoes_rel = {r["NumeroRelatorio"]: r["NomeRelatorio"]
                      for _, r in relatorios.iterrows()}
    with f3:
        relatorio = st.selectbox(
            "Relatorio", list(opcoes_rel.keys()) or ["1"],
            format_func=lambda n: "%s - %s" % (n, opcoes_rel.get(n, "Resumo")),
        )

    aba_valores, aba_cadastro = st.tabs(["Valores do relatorio", "Cadastro"])

    with aba_valores:
        with st.spinner("Consultando o IF.data..."):
            df, resp = bcb.ifdata_valores(anomes, tipo, relatorio, 20000, forcar)
        ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
        if ui.verificar(resp, "IF.data"):
            _mostrar_valores(df, anomes, relatorio)

    with aba_cadastro:
        with st.spinner("Consultando cadastro..."):
            dfc, respc = bcb.ifdata_cadastro(anomes, forcar)
        if ui.verificar(respc, "cadastro IF.data"):
            _mostrar_cadastro(dfc, anomes)


def _mostrar_valores(df, anomes, relatorio):
    if df.empty:
        ui.vazio(
            "Sem dados para essa combinacao. O IF.data e publicado com defasagem: "
            "tente uma data-base anterior ou outro tipo de instituicao."
        )
        return

    instituicoes = sorted(df["CodInst"].dropna().unique().tolist())
    st.caption("%d instituicoes e %d lancamentos nesta data-base."
               % (len(instituicoes), len(df)))

    contas = sorted(df["NomeColuna"].dropna().unique().tolist())
    escolha = st.multiselect("Contas exibidas", contas, default=contas[:6])
    filtrado = df[df["NomeColuna"].isin(escolha)] if escolha else df

    pivot = filtrado.pivot_table(index="CodInst", columns="NomeColuna",
                                 values="Saldo", aggfunc="sum").reset_index()
    pivot = pivot.rename(columns={"CodInst": "Codigo da instituicao"})
    ui.tabela(pivot, "ifdata_%s_r%s" % (anomes, relatorio), altura=440)

    with st.expander("Lancamentos detalhados", icon=":material/table_view:"):
        # Atencao: a base traz uma coluna "Conta" (o numero) e outra
        # "NomeColuna" (a descricao). Renomear as duas para "Conta" gera nomes
        # duplicados e quebra a conversao da tabela.
        ui.tabela(filtrado.rename(columns={
            "CodInst": "Codigo", "AnoMes": "Data-base", "NomeRelatorio": "Relatorio",
            "Conta": "Codigo da conta", "NomeColuna": "Conta",
            "DescricaoColuna": "Composicao"}),
            "ifdata_detalhe_%s" % anomes, altura=380)


def _mostrar_cadastro(df, anomes):
    if df.empty:
        ui.vazio("Sem cadastro para essa data-base.")
        return
    busca = st.text_input("Buscar instituicao", placeholder="Nome ou codigo",
                          key="busca_cad_ifdata")
    filtrado = df
    if busca:
        alvo = busca.strip().upper()
        filtrado = df[
            df["NomeInstituicao"].astype(str).str.upper().str.contains(alvo, na=False)
            | df["CodInst"].astype(str).str.upper().str.contains(alvo, na=False)
        ]
    exibir = filtrado.rename(columns={
        "CodInst": "Codigo", "NomeInstituicao": "Instituicao", "Uf": "UF",
        "Municipio": "Municipio", "Situacao": "Situacao", "Sr": "Segmento (Sn)",
        "DataInicioAtividade": "Inicio da atividade",
        "CodConglomeradoPrudencial": "Conglomerado prudencial"})
    ordem = [c for c in ("Codigo", "Instituicao", "UF", "Municipio", "Segmento (Sn)",
                         "Situacao", "Inicio da atividade", "Conglomerado prudencial")
             if c in exibir.columns]
    ui.tabela(exibir[ordem] if ordem else exibir, "ifdata_cadastro_%s" % anomes,
              altura=440)
    ui.nota(
        "O campo Segmento (S1 a S5) e o enquadramento prudencial da instituicao: "
        "S1 sao os maiores conglomerados, S5 os menores. Ele define o rigor das "
        "exigencias de capital aplicadas pelo Banco Central."
    )
