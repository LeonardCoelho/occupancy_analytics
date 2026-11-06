@echo off
REM Inicia o painel na porta 8524 e reinicia se ele cair.
REM Se o painel ja estiver no ar, sai sem fazer nada (seguro rodar varias vezes).
REM Usado pela tarefa "Painel Ocupacao" do Agendador de Tarefas do Windows.

cd /d "%~dp0.."
if not exist logs mkdir logs

netstat -ano | findstr /R /C:":8524 .*LISTENING" /C:":8524 .*ESCUTANDO" >nul
if %errorlevel%==0 exit /b 0

:loop
echo [%date% %time%] Iniciando painel na porta 8524 >> logs\painel.log
".venv\Scripts\python.exe" -m streamlit run app.py >> logs\painel.log 2>&1
echo [%date% %time%] Painel parou. Reiniciando em 15 segundos >> logs\painel.log
ping -n 16 127.0.0.1 >nul
goto loop
