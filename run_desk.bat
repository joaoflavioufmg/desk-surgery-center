@echo off
echo =========================================================
echo EXECUTANDO PIPELINE DE SIMULACAO DO CENTRO CIRURGICO
echo =========================================================

echo [1] Executando o Modelo de Simulacao (cc.py)...
desk-sim -m src/cc.py --mode single
if %errorlevel% neq 0 (
    echo [ERRO] O script de simulacao falhou. Interrompendo pipeline.
    pause
    exit /b %errorlevel%
)
@REM pause

@REM echo.
@REM echo [2/3] Executando Analise do Dashboard de Performance (cc_event_log_analysis.py)...
@REM cd results
@REM py cc_event_log_analysis.py
@REM if %errorlevel% neq 0 (
@REM     echo [ERRO] A analise do dashboard falhou. Interrompendo pipeline.
@REM     pause
@REM     exit /b %errorlevel%
@REM )

@REM echo.
@REM echo [3/3] Executando Ocupacao de Recursos em Slots de 2h (resource_2h_slots.py)...
@REM py resource_2h_slots.py
@REM if %errorlevel% neq 0 (
@REM     echo [ERRO] A analise de slots de 2h falhou. Interrompendo pipeline.
@REM     pause
@REM     exit /b %errorlevel%
@REM )

echo.
echo =========================================================
echo PIPELINE CONCLUIDO COM SUCESSO! 
echo =========================================================
@REM pause