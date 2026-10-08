# -*- coding: utf-8 -*-
"""Cotacoes de cambio - PTAX / Banco Central."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "cambio"

PERIODOS = {"30 dias": 30, "90 dias": 90, "6 meses": 180, "1 ano": 365, "2 anos": 730}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Carregando moedas..."):
        moedas, r_moedas = bcb.moedas_ptax(forcar)

    opcoes = ["USD", "EUR"]
    rotulos = {"USD": "USD - Dolar dos Estados Unidos", "EUR": "EUR - Euro"}
    if not moedas.empty:
        opcoes = moedas["simbolo"].tolist()
        rotulos = {r["simbolo"]: "%s - %s" % (r["simbolo"], r["nomeFormatado"])
                   for _, r in moedas.iterrows()}

    f1, f2 = st.columns([0.55, 0.45])
    with f1:
        moeda = st.selectbox(
            "Moeda", opcoes,
            index=opcoes.index("USD") if "USD" in opcoes else 0,
            format_func=lambda s: rotulos.get(s, s),
        )
    with f2:
        periodo = st.select_slider("Periodo", list(PERIODOS.keys()), value="90 dias")

    with st.spinner("Consultando a PTAX..."):
        df, resp = bcb.cotacao_periodo(moeda, PERIODOS[periodo], forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "cotacoes PTAX"):
        return
    if df.empty:
        ui.vazio("Sem boletins para a moeda e o periodo selecionados.")
        return

    fechamentos = df[df["tipoBoletim"].astype(str).str.contains(
        "Fechamento", case=False, na=False)]
    base = fechamentos if not fechamentos.empty else df

    atual = base.iloc[-1]
    anterior = base.iloc[-2] if len(base) > 1 else atual
    variacao = ((atual["cotacaoVenda"] / anterior["cotacaoVenda"]) - 1) * 100 \
        if anterior["cotacaoVenda"] else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Venda", "R$ %s" % ui.num(atual["cotacaoVenda"], 4),
                  delta="%s%%" % ui.num(variacao, 2))
    with c2:
        st.metric("Compra", "R$ %s" % ui.num(atual["cotacaoCompra"], 4))
    with c3:
        st.metric("Maxima do periodo", "R$ %s" % ui.num(base["cotacaoVenda"].max(), 4))
    with c4:
        st.metric("Minima do periodo", "R$ %s" % ui.num(base["cotacaoVenda"].min(), 4))

    st.caption("Ultimo boletim: %s (%s)."
               % (atual["dataHoraCotacao"].strftime("%d/%m/%Y as %H:%M"),
                  atual["tipoBoletim"]))

    st.write("")
    st.markdown("##### Evolucao da cotacao de venda")
    ui.grafico_linhas(
        base.set_index("dataHoraCotacao")[["cotacaoVenda"]].rename(
            columns={"cotacaoVenda": "Venda (R$)"}), altura=320, titulo_y="R$")

    with st.expander("Todos os boletins do periodo", icon=":material/table_view:"):
        exibir = df.copy()
        exibir["dataHoraCotacao"] = exibir["dataHoraCotacao"].dt.strftime(
            "%d/%m/%Y %H:%M")
        exibir = exibir.rename(columns={
            "dataHoraCotacao": "Data e hora", "tipoBoletim": "Boletim",
            "cotacaoCompra": "Compra", "cotacaoVenda": "Venda",
            "paridadeCompra": "Paridade compra", "paridadeVenda": "Paridade venda",
        }).sort_values("Data e hora", ascending=False)
        ui.tabela(exibir, "ptax_%s" % moeda, config={
            "Compra": st.column_config.NumberColumn(format="%.4f"),
            "Venda": st.column_config.NumberColumn(format="%.4f"),
        })

    ui.nota(
        "A PTAX de fechamento e divulgada por volta das 13h15. Em feriados e fins "
        "de semana nao ha boletim, por isso a serie apresenta lacunas - isso e "
        "comportamento normal da fonte, nao falha do sistema."
    )
