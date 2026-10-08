# -*- coding: utf-8 -*-
"""Catalogo de modulos do sistema.

Este arquivo e o coracao do menu e do controle de permissoes.

Criterio de organizacao do menu: os modulos NAO sao agrupados por orgao que
publica o dado (BCB, IBGE, CVM...), e sim pela PERGUNTA DE NEGOCIO que o
usuario tem na cabeca quando abre o sistema. Um analista de compliance nao
pensa "quero o Olinda do Bacen", ele pensa "esse credenciado tem impedimento?".
Por isso "Compliance" reune fontes de tres servicos diferentes, e a mesma API
do BCB aparece em grupos distintos conforme o uso.

Cada modulo declara:
    chave         -> identificador usado na tabela de permissoes (nunca mudar)
    grupo         -> secao do menu lateral (organizada por pergunta de negocio)
    titulo        -> rotulo exibido
    icone         -> emoji/icone do menu
    arquivo       -> modulo Python em paginas/ que expoe a funcao render()
    descricao     -> texto de apoio, exibido no cabecalho da pagina e no admin
    fontes        -> APIs publicas consumidas (exibido na tela de Fontes de Dados)
    departamentos -> setor(es) que efetivamente consomem o modulo (lista de
                     DEPARTAMENTOS, abaixo; lista vazia = uso geral/transversal).
                     Nao afeta o menu (isso continua sendo o 'grupo'); alimenta
                     os perfis de acesso sugeridos na tela de novo usuario, para
                     que dar acesso a um setor inteiro nao dependa de vasculhar
                     o menu modulo a modulo.
    somente_admin -> nao aparece para usuario comum nem na tela de permissoes
"""

# Vocabulario fixo de setores/departamentos. Mantido em lista (nao texto
# livre) para que 'departamentos' aqui e o campo 'setor' do cadastro de
# usuario (core/db.py) sempre casem com os mesmos nomes.
DEPARTAMENTOS = [
    "Diretoria",
    "Compliance",
    "Juridico",
    "Comercial",
    "Tesouraria/Financeiro",
    "RH",
    "TI",
    "Auditoria",
    "Administrativo",
]

MODULOS = [
    # ---------------- Visao geral ----------------
    {
        "chave": "painel",
        "grupo": "Visao Geral",
        "titulo": "Painel Executivo",
        "icone": ":material/dashboard:",
        "arquivo": "painel",
        "descricao": "Indicadores do dia consolidados em uma tela: juros, inflacao, "
                     "cambio, expectativas do mercado e volume do Pix.",
        "fontes": ["BCB/SGS", "BCB/PTAX", "BCB/Expectativas", "BCB/SPI"],
        "departamentos": ["Diretoria"],
    },
    # ---------------- Indicadores e mercado ----------------
    {
        "chave": "indicadores",
        "grupo": "Indicadores e Mercado",
        "titulo": "Series Economicas",
        "icone": ":material/timeline:",
        "arquivo": "indicadores",
        "descricao": "Historico de Selic, IPCA, IGP-M, CDI, TR, cambio e demais series "
                     "do Sistema Gerenciador de Series Temporais do Banco Central.",
        "fontes": ["BCB/SGS"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "focus",
        "grupo": "Indicadores e Mercado",
        "titulo": "Expectativas (Focus)",
        "icone": ":material/insights:",
        "arquivo": "focus",
        "descricao": "Projecoes do mercado para IPCA, PIB, Selic e cambio, coletadas "
                     "semanalmente pelo Banco Central no Relatorio Focus.",
        "fontes": ["BCB/Expectativas"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "cambio",
        "grupo": "Indicadores e Mercado",
        "titulo": "Cambio (PTAX)",
        "icone": ":material/currency_exchange:",
        "arquivo": "cambio",
        "descricao": "Cotacoes oficiais de fechamento, compra e venda de todas as "
                     "moedas com boletim no Banco Central.",
        "fontes": ["BCB/PTAX"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "cvm",
        "grupo": "Indicadores e Mercado",
        "titulo": "Companhias Abertas e Fundos (CVM)",
        "icone": ":material/savings:",
        "arquivo": "cvm",
        "descricao": "Cadastro de companhias abertas e de fundos de investimento da "
                     "CVM, com cota, patrimonio liquido e captacao diaria dos fundos.",
        "fontes": ["CVM/Companhias", "CVM/Fundos"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "ifdata",
        "grupo": "Indicadores e Mercado",
        "titulo": "IF.data - Dados Contabeis",
        "icone": ":material/lab_profile:",
        "arquivo": "ifdata",
        "descricao": "Balancos e indicadores prudenciais das instituicoes financeiras, "
                     "por trimestre e por tipo de relatorio.",
        "fontes": ["BCB/IFDATA"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "imobiliario",
        "grupo": "Indicadores e Mercado",
        "titulo": "Indices e Reajuste Imobiliario",
        "icone": ":material/home_work:",
        "arquivo": "imobiliario",
        "descricao": "IGP-M e INCC para reajuste de aluguel e obra, simulador de "
                     "reajuste e geocodificacao de enderecos.",
        "fontes": ["BCB/SGS", "Nominatim/OSM"],
        "departamentos": ["Administrativo"],
    },
    # ---------------- Instituicoes e rede ----------------
    {
        "chave": "instituicoes",
        "grupo": "Instituicoes e Rede",
        "titulo": "Instituicoes do SFN",
        "icone": ":material/account_balance:",
        "arquivo": "instituicoes",
        "descricao": "Cadastro oficial de bancos, cooperativas, consorcios e demais "
                     "sociedades autorizadas a funcionar no pais.",
        "fontes": ["BCB/Instituicoes_em_funcionamento", "BrasilAPI/Bancos"],
        "departamentos": ["Compliance", "Comercial"],
    },
    {
        "chave": "rede_atendimento",
        "grupo": "Instituicoes e Rede",
        "titulo": "Agencias e Postos",
        "icone": ":material/store:",
        "arquivo": "rede_atendimento",
        "descricao": "Rede fisica de atendimento do sistema financeiro por municipio, "
                     "UF e instituicao.",
        "fontes": ["BCB/Informes_Agencias", "BCB/Informes_PostosDeAtendimento"],
        "departamentos": ["Comercial"],
    },
    {
        "chave": "correspondentes",
        "grupo": "Instituicoes e Rede",
        "titulo": "Correspondentes no Pais",
        "icone": ":material/handshake:",
        "arquivo": "correspondentes",
        "descricao": "Quem esta credenciado a atuar como correspondente bancario, "
                     "para qual contratante e com quais servicos autorizados.",
        "fontes": ["BCB/Informes_Correspondentes"],
        "departamentos": ["Comercial"],
    },
    # ---------------- Compliance ----------------
    {
        "chave": "compliance",
        "grupo": "Compliance e Integridade",
        "titulo": "Impedimentos e Penalidades",
        "icone": ":material/gavel:",
        "arquivo": "compliance",
        "descricao": "Consulta de pessoas inabilitadas e proibidas de atuar no sistema "
                     "financeiro por decisao do Banco Central.",
        "fontes": ["BCB/Gepad_QuadrosGeraisInternet"],
        "departamentos": ["Compliance"],
    },
    {
        "chave": "dominios",
        "grupo": "Compliance e Integridade",
        "titulo": "Dominios Verificados",
        "icone": ":material/verified_user:",
        "arquivo": "dominios",
        "descricao": "Enderecos de internet oficialmente declarados por cada instituicao "
                     "financeira. Use para conferir se um site e legitimo.",
        "fontes": ["BCB/Instituicoes_em_funcionamento"],
        "departamentos": ["Compliance", "TI"],
    },
    {
        "chave": "verificar_credenciado",
        "grupo": "Compliance e Integridade",
        "titulo": "Verificar Credenciado",
        "icone": ":material/fact_check:",
        "arquivo": "verificar_credenciado",
        "descricao": "Um CNPJ ou CPF contra todas as bases de sancao da CGU de uma "
                     "vez: CEIS, CNEP, CEPIM, leniencia e CEAF, mais cadastro e "
                     "contratos federais.",
        "fontes": ["CGU/Portal da Transparencia", "BrasilAPI/CNPJ"],
        "requer_chave": "cgu_api_key",
        "departamentos": ["Compliance", "Juridico"],
    },
    {
        "chave": "ouvidorias",
        "grupo": "Compliance e Integridade",
        "titulo": "Qualidade de Ouvidorias",
        "icone": ":material/support_agent:",
        "arquivo": "ouvidorias",
        "descricao": "Ranking de desempenho das ouvidorias das instituicoes no "
                     "tratamento de reclamacoes.",
        "fontes": ["BCB/RankingOuvidorias"],
        "departamentos": ["Compliance", "Comercial"],
    },
    {
        "chave": "transparencia",
        "grupo": "Compliance e Integridade",
        "titulo": "Portal da Transparencia",
        "icone": ":material/policy:",
        "arquivo": "transparencia",
        "descricao": "Console completo da API da CGU: sancoes (CEIS/CNEP/CEPIM), "
                     "servidores, despesas, licitacoes, convenios, viagens e mais - "
                     "106 consultas em 17 grupos.",
        "fontes": ["CGU/Portal da Transparencia"],
        "requer_chave": "cgu_api_key",
        "departamentos": ["Compliance", "Auditoria"],
    },
    {
        "chave": "investigacao",
        "grupo": "Compliance e Integridade",
        "titulo": "Investigacao / OSINT",
        "icone": ":material/travel_explore:",
        "arquivo": "investigacao",
        "descricao": "Due-diligence com fontes abertas: busca de username em "
                     "centenas de sites, construtor de buscas avancadas (dorks) e "
                     "integracao com SpiderFoot. Uso com finalidade declarada e "
                     "auditado.",
        "fontes": ["WhatsMyName", "Sherlock", "SpiderFoot"],
        "departamentos": ["Compliance"],
    },
    # ---------------- Pagamentos ----------------
    {
        "chave": "pix",
        "grupo": "Pagamentos",
        "titulo": "Pix e DICT",
        "icone": ":material/bolt:",
        "arquivo": "pix",
        "descricao": "Chaves cadastradas por instituicao, transacoes por perfil e "
                     "regiao, e estatisticas de fraude e devolucao (MED).",
        "fontes": ["BCB/Pix_DadosAbertos", "BrasilAPI/Pix"],
        "departamentos": ["Tesouraria/Financeiro", "Compliance"],
    },
    {
        "chave": "liquidacao",
        "grupo": "Pagamentos",
        "titulo": "SPI e STR",
        "icone": ":material/swap_horiz:",
        "arquivo": "liquidacao",
        "descricao": "Volume liquidado no Sistema de Pagamentos Instantaneos e no "
                     "Sistema de Transferencia de Reservas, e disponibilidade do SPI.",
        "fontes": ["BCB/SPI", "BCB/STR"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    {
        "chave": "meios_pagamento",
        "grupo": "Pagamentos",
        "titulo": "Meios de Pagamento",
        "icone": ":material/credit_card:",
        "arquivo": "meios_pagamento",
        "descricao": "Comparativo mensal entre Pix, TED, boleto, cheque e DOC em "
                     "quantidade e valor.",
        "fontes": ["BCB/MPV_DadosAbertos"],
        "departamentos": ["Tesouraria/Financeiro"],
    },
    # ---------------- Tarifas e produtos ----------------
    {
        "chave": "tarifas",
        "grupo": "Tarifas e Produtos",
        "titulo": "Tarifas Bancarias",
        "icone": ":material/receipt_long:",
        "arquivo": "tarifas",
        "descricao": "Quanto cada instituicao cobra por servico, e os valores minimo, "
                     "maximo e medio praticados pelo mercado.",
        "fontes": ["BCB/Informes_ListaTarifasPorInstituicaoFinanceira",
                   "BCB/Informes_ListaValoresDeServicoBancario"],
        "departamentos": ["Comercial", "Tesouraria/Financeiro"],
    },
    {
        "chave": "openfinance",
        "grupo": "Tarifas e Produtos",
        "titulo": "Open Finance",
        "icone": ":material/hub:",
        "arquivo": "openfinance",
        "descricao": "Diretorio de participantes e catalogo das APIs de dados abertos "
                     "publicadas por cada instituicao, sem necessidade de credencial.",
        "fontes": ["OpenFinance/Directory", "BCB/DASFN"],
        "departamentos": ["Comercial", "TI"],
    },
    # ---------------- Comercio exterior ----------------
    {
        "chave": "comex",
        "grupo": "Comercio Exterior",
        "titulo": "Balanca Comercial",
        "icone": ":material/local_shipping:",
        "arquivo": "comex",
        "descricao": "Exportacao e importacao brasileiras por pais, produto (NCM), "
                     "UF e bloco economico, direto do ComexStat.",
        "fontes": ["ComexStat/MDIC", "IBGE/Paises"],
        "departamentos": ["Comercial"],
    },
    {
        "chave": "ncm_tec",
        "grupo": "Comercio Exterior",
        "titulo": "NCM e Tarifa Externa (TEC)",
        "icone": ":material/inventory_2:",
        "arquivo": "ncm_tec",
        "descricao": "Nomenclatura Comum do Mercosul e Tarifa Externa Comum - "
                     "classificacao de mercadorias usada no comercio exterior e na "
                     "nota fiscal.",
        "fontes": ["Siscomex/NCM"],
        "departamentos": ["Comercial"],
    },
    # ---------------- Governo e setor publico ----------------
    {
        "chave": "contas_publicas",
        "grupo": "Governo e Setor Publico",
        "titulo": "Contas de Estados e Municipios",
        "icone": ":material/account_balance_wallet:",
        "arquivo": "contas_publicas",
        "descricao": "Execucao orcamentaria (RREO) e gestao fiscal (RGF) de qualquer "
                     "estado ou municipio, pela base do Tesouro Nacional.",
        "fontes": ["SICONFI/Tesouro"],
        "departamentos": ["Comercial", "Compliance"],
    },
    {
        "chave": "contratacoes",
        "grupo": "Governo e Setor Publico",
        "titulo": "Contratacoes Publicas",
        "icone": ":material/gavel:",
        "arquivo": "contratacoes",
        "descricao": "Contratos, atas de registro de preco e editais publicados no "
                     "Portal Nacional de Contratacoes Publicas.",
        "fontes": ["PNCP", "Compras.gov.br"],
        "departamentos": ["Comercial", "Juridico"],
    },
    # ---------------- Juridico e legislativo ----------------
    {
        "chave": "processos",
        "grupo": "Juridico e Legislativo",
        "titulo": "Processos (DataJud)",
        "icone": ":material/balance:",
        "arquivo": "processos",
        "descricao": "Metadados processuais de todos os tribunais do pais: numero, "
                     "classe, assuntos, orgao julgador e movimentos.",
        "fontes": ["DataJud/CNJ"],
        "departamentos": ["Juridico"],
    },
    {
        "chave": "legislativo",
        "grupo": "Juridico e Legislativo",
        "titulo": "Acompanhamento Legislativo",
        "icone": ":material/how_to_vote:",
        "arquivo": "legislativo",
        "descricao": "Proposicoes e parlamentares da Camara e do Senado, para seguir "
                     "projetos que afetem o setor.",
        "fontes": ["Camara/Dados Abertos", "Senado/Dados Abertos"],
        "departamentos": ["Juridico"],
    },
    {
        "chave": "diarios",
        "grupo": "Juridico e Legislativo",
        "titulo": "Diarios Oficiais",
        "icone": ":material/newspaper:",
        "arquivo": "diarios",
        "descricao": "Busca no texto dos diarios oficiais municipais - achar mencoes "
                     "a empresas, contratos e editais.",
        "fontes": ["QueridoDiario/OKBR"],
        "departamentos": ["Juridico"],
    },
    # ---------------- Recursos humanos ----------------
    {
        "chave": "rh",
        "grupo": "Recursos Humanos",
        "titulo": "Indicadores de RH",
        "icone": ":material/groups:",
        "arquivo": "rh",
        "descricao": "Salario minimo, taxa de desocupacao e rendimento medio, para "
                     "apoiar o planejamento de pessoal.",
        "fontes": ["BCB/SGS", "IBGE/PNAD"],
        "departamentos": ["RH"],
    },
    # ---------------- Territorio ----------------
    {
        "chave": "ibge",
        "grupo": "Territorio e Economia",
        "titulo": "IBGE - Territorio e Indices",
        "icone": ":material/public:",
        "arquivo": "ibge",
        "descricao": "Estados, municipios e series do IBGE para cruzar com os dados "
                     "financeiros por localidade.",
        "fontes": ["IBGE/Localidades", "IBGE/Agregados"],
        "departamentos": [],
    },
    # ---------------- Consultas rapidas ----------------
    {
        "chave": "consultas",
        "grupo": "Consultas Rapidas",
        "titulo": "Consulta Rapida",
        "icone": ":material/search:",
        "arquivo": "consultas",
        "descricao": "CNPJ, CEP, bancos por codigo COMPE/ISPB, participantes do Pix e "
                     "feriados nacionais em uma unica tela.",
        "fontes": ["BrasilAPI"],
        "departamentos": [],
    },
    {
        "chave": "cnae",
        "grupo": "Consultas Rapidas",
        "titulo": "CNAE - Classificacao de Atividades",
        "icone": ":material/category:",
        "arquivo": "cnae",
        "descricao": "Classificacao Nacional de Atividades Economicas, por secao, "
                     "divisao, grupo e classe.",
        "fontes": ["IBGE/CNAE"],
        "departamentos": ["Compliance", "Comercial"],
    },
    # ---------------- Administracao ----------------
    {
        "chave": "admin_usuarios",
        "grupo": "Administracao",
        "titulo": "Usuarios e Permissoes",
        "icone": ":material/manage_accounts:",
        "arquivo": "admin_usuarios",
        "descricao": "Criar, editar, desativar e excluir usuarios; definir a que cada "
                     "um tem acesso; redefinir senha para a padrao.",
        "fontes": [],
        "somente_admin": True,
        "departamentos": ["TI"],
    },
    {
        "chave": "admin_auditoria",
        "grupo": "Administracao",
        "titulo": "Auditoria",
        "icone": ":material/history:",
        "arquivo": "admin_auditoria",
        "descricao": "Historico de logins, alteracoes de cadastro e consultas "
                     "realizadas no sistema.",
        "fontes": [],
        "somente_admin": True,
        "departamentos": ["TI", "Auditoria"],
    },
    {
        "chave": "admin_fontes",
        "grupo": "Administracao",
        "titulo": "Fontes de Dados",
        "icone": ":material/cloud_sync:",
        "arquivo": "admin_fontes",
        "descricao": "Estado de cada API publica, horario da ultima atualizacao "
                     "bem-sucedida e limpeza de cache.",
        "fontes": [],
        "somente_admin": True,
        "departamentos": ["TI"],
    },
]

POR_CHAVE = {m["chave"]: m for m in MODULOS}

# Ordem em que os grupos aparecem no menu lateral.
ORDEM_GRUPOS = [
    "Visao Geral",
    "Indicadores e Mercado",
    "Instituicoes e Rede",
    "Compliance e Integridade",
    "Pagamentos",
    "Tarifas e Produtos",
    "Comercio Exterior",
    "Governo e Setor Publico",
    "Juridico e Legislativo",
    "Recursos Humanos",
    "Territorio e Economia",
    "Consultas Rapidas",
    "Administracao",
]


def modulos_atribuiveis():
    """Modulos que podem ser concedidos a um usuario comum na tela de admin."""
    return [m for m in MODULOS if not m.get("somente_admin")]


def grupos_atribuiveis():
    """Dict {grupo: [modulos]} preservando a ordem do menu, sem os de admin."""
    saida = {}
    for g in ORDEM_GRUPOS:
        itens = [m for m in modulos_atribuiveis() if m["grupo"] == g]
        if itens:
            saida[g] = itens
    return saida


def chaves_padrao():
    """Sugestao de acesso inicial para um usuario novo: leitura geral, sem admin."""
    return [m["chave"] for m in modulos_atribuiveis()]


def modulos_do_departamento(departamento: str):
    """Chaves dos modulos atribuiveis cujo setor dono e 'departamento'.

    Usado para sugerir automaticamente os modulos de um setor na tela de novo
    usuario, em vez de exigir que o administrador cate modulo a modulo pelo
    menu inteiro.
    """
    return [m["chave"] for m in modulos_atribuiveis()
            if departamento in m.get("departamentos", [])]
