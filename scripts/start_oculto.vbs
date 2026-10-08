' IntegraPublic - lancador oculto (sem janela) para o Agendador de Tarefas.
' Sobe o servidor Streamlit com o console OCULTO e espera o retorno, para que o
' Agendador acompanhe o processo e possa reinicia-lo se ele cair.
Option Explicit
Dim sh, rc
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Sistemas Pronto\Sistema Geral Interdepartamental"
' 0 = janela oculta ; True = esperar o processo terminar (tarefa fica "Em execucao")
rc = sh.Run("""C:\Sistemas Pronto\Sistema Geral Interdepartamental\.venv\Scripts\python.exe"" -m streamlit run app.py", 0, True)
WScript.Quit(rc)
