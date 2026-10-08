# -*- coding: utf-8 -*-
"""Componentes visuais e padroes de interface do IntegraPublic.

Diretrizes de UX adotadas em todas as telas:
  - uma tela responde a uma pergunta; filtros ficam agrupados no topo;
  - todo dado exibido informa de onde veio e quando foi atualizado;
  - estado vazio e estado de erro sao explicitos, nunca uma tabela em branco;
  - toda tabela pode ser baixada em CSV e Excel sem sair da tela;
  - hierarquia tipografica constante: titulo, apoio, conteudo.
"""
import io
from contextlib import nullcontext

import altair as alt
import pandas as pd
import streamlit as st

from core.config import APP_NOME, APP_VERSAO

CSS = """
<style>
:root {
  --ip-azul: #2563EB;
  --ip-azul-escuro: #1E40AF;
  --ip-tinta: #0F172A;
  --ip-apoio: #64748B;
  --ip-borda: #E2E8F0;
  --ip-fundo: #F8FAFC;
  --ip-ok: #059669;
  --ip-alerta: #B45309;
  --ip-erro: #DC2626;
}

/* --- enxugar o cromo padrao do Streamlit --- */
#MainMenu, footer, header [data-testid="stStatusWidget"] { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }

/* --- cabecalho de pagina --- */
.ip-cabecalho { border-bottom: 1px solid var(--ip-borda); padding-bottom: .9rem;
                margin-bottom: 1.4rem; }
.ip-cabecalho h1 { font-size: 1.55rem; font-weight: 650; color: var(--ip-tinta);
                   margin: 0 0 .3rem 0; letter-spacing: -.015em; line-height: 1.25; }
.ip-cabecalho p  { font-size: .92rem; color: var(--ip-apoio); margin: 0; max-width: 90ch;
                   line-height: 1.5; }

/* --- selo de atualizacao --- */
.ip-selo { display: inline-flex; align-items: center; gap: .4rem; font-size: .78rem;
           font-weight: 500; padding: .22rem .6rem; border-radius: 999px;
           border: 1px solid transparent; white-space: nowrap; }
.ip-selo.ok      { background: #ECFDF5; color: var(--ip-ok);     border-color: #A7F3D0; }
.ip-selo.cache   { background: #EFF6FF; color: var(--ip-azul-escuro); border-color: #BFDBFE; }
.ip-selo.alerta  { background: #FFFBEB; color: var(--ip-alerta); border-color: #FDE68A; }
.ip-selo.erro    { background: #FEF2F2; color: var(--ip-erro);   border-color: #FECACA; }

/* --- cartoes de indicador --- */
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--ip-borda);
    border-radius: 12px; padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
div[data-testid="stMetricLabel"] p { font-size: .78rem !important; color: var(--ip-apoio);
    font-weight: 550; text-transform: uppercase; letter-spacing: .04em; }
div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 640;
    color: var(--ip-tinta); letter-spacing: -.02em; }

/* --- barra lateral --- */
section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--ip-borda); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
.ip-marca { display: flex; align-items: center; gap: .65rem; padding: .2rem .2rem 1rem .2rem;
            border-bottom: 1px solid var(--ip-borda); margin-bottom: .8rem; }
.ip-marca-icone { width: 38px; height: 38px; border-radius: 10px; flex: none;
    background: linear-gradient(135deg, var(--ip-azul), var(--ip-azul-escuro));
    color: #FFF; display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 1rem; }
.ip-marca-nome { font-weight: 660; font-size: 1.02rem; color: var(--ip-tinta); line-height: 1.1; }
.ip-marca-sub  { font-size: .7rem; color: var(--ip-apoio); letter-spacing: .03em; }

.ip-usuario { background: var(--ip-fundo); border: 1px solid var(--ip-borda);
              border-radius: 10px; padding: .65rem .75rem; margin: .3rem 0 .7rem 0; }
.ip-usuario .nome { font-weight: 600; font-size: .88rem; color: var(--ip-tinta); }
.ip-usuario .papel { font-size: .74rem; color: var(--ip-apoio); }

/* --- tela de acesso --- */
.ip-login-marca { text-align: center; margin-bottom: 1.6rem; }
.ip-login-marca .icone { width: 60px; height: 60px; border-radius: 16px; margin: 0 auto .9rem;
    background: linear-gradient(135deg, var(--ip-azul), var(--ip-azul-escuro)); color: #FFF;
    display: flex; align-items: center; justify-content: center; font-size: 1.5rem;
    font-weight: 700; box-shadow: 0 8px 20px rgba(37,99,235,.22); }
.ip-login-marca h2 { margin: 0; font-size: 1.4rem; font-weight: 660; color: var(--ip-tinta); }
.ip-login-marca p  { margin: .3rem 0 0; font-size: .87rem; color: var(--ip-apoio); }

/* --- rodape --- */
.ip-rodape { font-size: .72rem; color: var(--ip-apoio); text-align: center;
             padding-top: .8rem; border-top: 1px solid var(--ip-borda); margin-top: .6rem;
             line-height: 1.5; }

/* --- ajustes gerais --- */
.stButton > button { border-radius: 8px; font-weight: 550; }
div[data-testid="stDataFrame"] { border: 1px solid var(--ip-borda); border-radius: 10px; }
div[data-testid="stExpander"] { border: 1px solid var(--ip-borda); border-radius: 10px; }
.ip-nota { font-size: .8rem; color: var(--ip-apoio); background: var(--ip-fundo);
           border-left: 3px solid var(--ip-azul); padding: .6rem .8rem; border-radius: 6px;
           margin: .2rem 0 1rem 0; line-height: 1.5; }
</style>
"""


def injetar_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def cabecalho(titulo: str, descricao: str = "", resposta=None, acao_atualizar=None,
              destino=None) -> None:
    """Cabecalho padrao: titulo, apoio, selo de atualizacao e botao de refresh.

    'destino' e um container criado no inicio da pagina. Ele permite que o
    cabecalho apareca acima dos filtros mesmo sendo preenchido depois - o selo
    de atualizacao so pode ser desenhado quando ja se sabe de onde veio o dado,
    e isso acontece apos a consulta.
    """
    alvo = destino if destino is not None else nullcontext()
    with alvo:
        esq, dir_ = st.columns([0.78, 0.22], vertical_alignment="bottom")
        with esq:
            st.markdown(
                '<div class="ip-cabecalho"><h1>%s</h1><p>%s</p></div>'
                % (titulo, descricao), unsafe_allow_html=True,
            )
        with dir_:
            if resposta is not None:
                selo(resposta)
            if acao_atualizar is not None:
                if st.button("Atualizar agora", use_container_width=True,
                             key="atualizar_%s" % titulo, icon=":material/refresh:"):
                    acao_atualizar()


def controle_atualizacao(chave: str):
    """Par (forcar, acao) usado por todas as paginas.

    'forcar' indica que esta execucao deve ignorar o cache e ir ate a fonte.
    'acao' e o callback do botao Atualizar agora: limpa o cache em memoria,
    marca o forcar para a proxima execucao e recarrega a tela.
    """
    marca = "forcar_%s" % chave
    forcar = bool(st.session_state.pop(marca, False))

    def acao():
        st.cache_data.clear()
        st.session_state[marca] = True
        st.rerun()

    return forcar, acao


def selo(resposta) -> None:
    """Chip de procedencia do dado."""
    classe = {"rede": "ok", "cache": "cache", "cache_defasado": "alerta"}.get(
        getattr(resposta, "origem", "erro"), "erro"
    )
    texto = resposta.selo() if hasattr(resposta, "selo") else "Sem dados"
    if classe == "erro":
        texto = "Fonte indisponivel"
    st.markdown('<span class="ip-selo %s">%s</span>' % (classe, texto), unsafe_allow_html=True)


def nota(texto: str) -> None:
    st.markdown('<div class="ip-nota">%s</div>' % texto, unsafe_allow_html=True)


def verificar(resposta, contexto: str = "") -> bool:
    """Trata erro/defasagem de uma fonte. Devolve True se ha dado utilizavel."""
    if resposta is None or not resposta.ok:
        st.error(
            "Nao foi possivel obter os dados%s e nao ha copia local para exibir.\n\n"
            "Detalhe tecnico: %s"
            % (" de %s" % contexto if contexto else "",
               getattr(resposta, "erro", "fonte sem resposta")),
            icon=":material/cloud_off:",
        )
        return False
    if resposta.defasado:
        st.warning(
            "A fonte oficial nao respondeu agora. Exibindo a ultima copia obtida em %s. "
            "O sistema tentara atualizar sozinho na proxima consulta."
            % resposta.obtido_em_txt,
            icon=":material/warning:",
        )
    return True


def vazio(mensagem: str = "Nenhum registro encontrado para os filtros selecionados.") -> None:
    st.info(mensagem, icon=":material/inbox:")


def aviso_truncado(quantidade: int, limite: int, sugestao: str = "") -> bool:
    """Avisa quando a consulta bateu no teto e o conjunto veio incompleto.

    Sem isso o usuario ve um numero redondo (30.000) e acredita que aquele e o
    total real - erro silencioso que compromete qualquer analise feita em cima.
    """
    if quantidade < limite:
        return False
    st.warning(
        "A fonte devolveu o maximo de %s registros por consulta, entao **este "
        "conjunto esta incompleto** - existem mais registros alem destes. "
        "Os totais abaixo valem apenas para o que foi carregado.%s"
        % (num(limite, 0), (" " + sugestao) if sugestao else ""),
        icon=":material/filter_alt:",
    )
    return True


import re as _re

# Reconhece data/hora ISO no inicio da string: 2026-09-10 ou 2026-09-10T13:09:...
_RE_ISO = _re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2})?")


def data_br(valor):
    """Converte data ISO (AAAA-MM-DD[THH:MM...]) para dd/mm/aaaa.

    Passa adiante, sem tocar, qualquer coisa que ja nao seja ISO - inclusive
    datas ja em dd/mm/aaaa (como as da NCM e as da CGU quando ela devolve BR),
    numeros, textos e vazios. Aceita tambem objetos date/datetime/Timestamp.
    """
    if valor is None:
        return valor
    if not isinstance(valor, str) and hasattr(valor, "strftime"):
        try:
            return valor.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return valor
    s = str(valor)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-" and _RE_ISO.match(s):
        return "%s/%s/%s" % (s[8:10], s[5:7], s[0:4])
    return valor


def _converter_datas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte para dd/mm/aaaa toda coluna cujo conteudo seja data ISO.

    Detecta pela AMOSTRA (primeiro valor nao-nulo) para nao varrer colunas que
    obviamente nao sao data. Colunas datetime do pandas tambem sao formatadas.
    Devolve o mesmo df se nao houver nada a converter.
    """
    saida = None
    for col in df.columns:
        serie = df[col]
        tipo = str(serie.dtype)
        try:
            if tipo.startswith("datetime"):
                if saida is None:
                    saida = df.copy()
                saida[col] = serie.dt.strftime("%d/%m/%Y")
            # texto: no pandas 3.0 strings tem dtype 'str'/'string', nao mais
            # 'object' - por isso checamos os tres.
            elif serie.dtype == object or tipo in ("str", "string") \
                    or tipo.startswith("string"):
                naonulos = serie.dropna()
                if naonulos.empty:
                    continue
                amostra = str(naonulos.iloc[0])
                if len(amostra) >= 10 and amostra[4:5] == "-" \
                        and amostra[7:8] == "-" and _RE_ISO.match(amostra):
                    if saida is None:
                        saida = df.copy()
                    saida[col] = serie.map(data_br)
        except (AttributeError, TypeError):
            continue
    return saida if saida is not None else df


def tabela(df: pd.DataFrame, nome_arquivo: str, altura: int = 460,
           config: dict | None = None, ocultar_indice: bool = True) -> None:
    """Tabela padrao com exportacao em CSV e Excel.

    Toda data ISO exibida aqui e convertida para dd/mm/aaaa automaticamente,
    de modo que qualquer tabela do sistema mostra datas no padrao brasileiro
    sem precisar formatar coluna a coluna em cada tela.
    """
    if df is None or df.empty:
        vazio()
        return
    df = _converter_datas(df)
    df = _nomes_unicos(df)
    st.dataframe(df, use_container_width=True, height=altura,
                 hide_index=ocultar_indice, column_config=config or {})
    c1, c2, c3 = st.columns([0.17, 0.17, 0.66])
    with c1:
        st.download_button(
            "CSV", df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            "%s.csv" % nome_arquivo, "text/csv", use_container_width=True,
            key="csv_%s" % nome_arquivo, icon=":material/download:",
        )
    with c2:
        st.download_button(
            "Excel", _excel(df), "%s.xlsx" % nome_arquivo,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="xls_%s" % nome_arquivo,
            icon=":material/download:",
        )
    with c3:
        st.caption("%s registro(s)" % f"{len(df):,}".replace(",", "."))


PALETA = ["#2563EB", "#DC2626", "#059669", "#B45309", "#7C3AED", "#0891B2",
          "#DB2777", "#65A30D"]


def grafico_linhas(dados: pd.DataFrame, altura: int = 300, cores=None,
                   comeca_no_zero: bool = False, titulo_y: str = None) -> None:
    """Grafico de linhas com escala honesta.

    O grafico nativo do Streamlit ancora o eixo Y no zero. Para cotacao e
    indice isso achata a curva e esconde justamente a variacao que interessa -
    um dolar entre 5,05 e 5,15 vira uma reta. Aqui o eixo se ajusta aos dados,
    salvo quando o zero for uma referencia real (volumes, contagens).
    """
    if dados is None or dados.empty:
        vazio("Sem dados para o grafico.")
        return

    largo = dados.reset_index()
    coluna_x = largo.columns[0]
    longo = (largo.melt(id_vars=[coluna_x], var_name="Serie", value_name="Valor")
             .dropna(subset=["Valor"]))
    if longo.empty:
        vazio("Sem dados para o grafico.")
        return

    series = list(dict.fromkeys(longo["Serie"].tolist()))
    escala_cor = alt.Scale(domain=series, range=(cores or PALETA)[:len(series)])
    eixo_x = alt.X("%s:T" % coluna_x, title=None,
                   axis=alt.Axis(format="%b/%y", labelAngle=0))

    grafico = (
        alt.Chart(longo)
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=eixo_x,
            y=alt.Y("Valor:Q", title=titulo_y,
                    scale=alt.Scale(zero=comeca_no_zero, nice=True)),
            color=alt.Color("Serie:N", scale=escala_cor,
                            legend=None if len(series) == 1
                            else alt.Legend(title=None, orient="top")),
            tooltip=[alt.Tooltip("%s:T" % coluna_x, title="Data",
                                 format="%d/%m/%Y"),
                     alt.Tooltip("Serie:N", title="Serie"),
                     alt.Tooltip("Valor:Q", title="Valor", format=",.4f")],
        )
        .properties(height=altura)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=True, gridColor="#EEF2F7", domainColor="#E2E8F0",
                        tickColor="#E2E8F0", labelColor="#64748B",
                        titleColor="#64748B")
    )
    st.altair_chart(grafico, use_container_width=True)


def _nomes_unicos(df: pd.DataFrame) -> pd.DataFrame:
    """Garante nomes de coluna unicos.

    Um rename descuidado pode produzir duas colunas com o mesmo nome, e a
    conversao para Arrow - usada por st.dataframe - falha com excecao,
    derrubando a tela inteira. Aqui a segunda ocorrencia vira "Nome (2)".
    """
    nomes = list(df.columns)
    if len(set(nomes)) == len(nomes):
        return df
    vistos, saida = {}, []
    for nome in nomes:
        if nome in vistos:
            vistos[nome] += 1
            saida.append("%s (%d)" % (nome, vistos[nome]))
        else:
            vistos[nome] = 1
            saida.append(nome)
    copia = df.copy()
    copia.columns = saida
    return copia


def _excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
            df.to_excel(escritor, index=False, sheet_name="Dados")
    except Exception:
        return df.to_csv(index=False, sep=";").encode("utf-8-sig")
    return buffer.getvalue()


# --- formatacao -------------------------------------------------------------
def num(valor, casas: int = 2) -> str:
    """Numero no padrao brasileiro: 1.234.567,89."""
    try:
        texto = f"{float(valor):,.{casas}f}"
        return texto.replace(",", "@").replace(".", ",").replace("@", ".")
    except (TypeError, ValueError):
        return "-"


def moeda(valor, simbolo: str = "R$", casas: int = 2) -> str:
    return "%s %s" % (simbolo, num(valor, casas))


def inteiro(valor) -> str:
    return num(valor, 0)


def cnpj_formatado(valor) -> str:
    d = "".join(ch for ch in str(valor or "") if ch.isdigit())
    if len(d) == 8:                       # raiz de CNPJ, como o BCB publica
        return "%s.%s.%s" % (d[:2], d[2:5], d[5:8])
    if len(d) == 14:
        return "%s.%s.%s/%s-%s" % (d[:2], d[2:5], d[5:8], d[8:12], d[12:])
    return str(valor or "-")


# --- barra lateral ----------------------------------------------------------
def marca_lateral() -> None:
    st.sidebar.markdown(
        '<div class="ip-marca"><div class="ip-marca-icone">IP</div>'
        '<div><div class="ip-marca-nome">%s</div>'
        '<div class="ip-marca-sub">DADOS PUBLICOS OFICIAIS</div></div></div>' % APP_NOME,
        unsafe_allow_html=True,
    )


def rodape_lateral(usuario) -> None:
    st.sidebar.markdown(
        '<div class="ip-usuario"><div class="nome">%s</div>'
        '<div class="papel">%s%s</div></div>'
        % (usuario["nome"],
           "Administrador" if usuario["is_admin"] else "Usuario",
           " - %s" % usuario["setor"] if usuario["setor"] else ""),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<div class="ip-rodape">%s v%s<br>Fontes oficiais - atualizacao automatica</div>'
        % (APP_NOME, APP_VERSAO),
        unsafe_allow_html=True,
    )
