@echo off
echo =========================================================
echo EXECUTANDO PIPELINE DE SIMULACAO DO CENTRO CIRURGICO
echo =========================================================

echo [1/3] Executando o Modelo de Simulacao (cc.py)...
@REM desk-sim -m src/cc.py --mode visualization
desk-sim -m src/cc.py --mode single
@REM desk-sim -m src/cc.py --mode replications
@REM desk-sim -m src/cc.py --mode factorial
if %errorlevel% neq 0 (
    echo [ERRO] O script de simulacao falhou. Interrompendo pipeline.
    pause
    exit /b %errorlevel%
)
pause

echo.
echo [2/3] Executando Analise do Dashboard de Performance (cc_event_log_analysis.py)...
cd results
py cc_event_log_analysis.py
if %errorlevel% neq 0 (
    echo [ERRO] A analise do dashboard falhou. Interrompendo pipeline.
    pause
    exit /b %errorlevel%
)

echo.
echo [3/3] Executando Ocupacao de Recursos em Slots de 2h (resource_2h_slots.py)...
py resource_2h_slots.py
if %errorlevel% neq 0 (
    echo [ERRO] A analise de slots de 2h falhou. Interrompendo pipeline.
    pause
    exit /b %errorlevel%
)
cd ..

echo.
echo =========================================================
echo PIPELINE CONCLUIDO COM SUCESSO! 
echo =========================================================
@REM pause