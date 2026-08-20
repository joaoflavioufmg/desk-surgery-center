@echo off
echo =========================================================
echo EXECUTANDO PIPELINE DE SIMULACAO DO CENTRO CIRURGICO
echo =========================================================

echo [1/3] Executando o Modelo de Simulacao (cc.py)...
desk-sim -m src/cc.py --mode visualization
@REM desk-sim -m src/cc.py --mode single
@REM CC-1: Aumento de 20% da demanda. De 16 -> 19 por dia
@REM desk-sim -m src/cc-1.py --mode single           
@REM CC-2: Novo redesenho de escalas e turnos
@REM desk-sim -m src/cc-2.py --mode single
@REM CC-3: Aumento médio de cirurgias nas salas 2,3,5 e 6 (2-> 6) 30 por dia
@REM desk-sim -m src/cc-3.py --mode single
@REM CC-4: Aumento médio de cirurgias (2-> 6) 30 por dia + redesenho de escalas
@REM desk-sim -m src/cc-4.py --mode single
@REM CC-5: Base + Atendimento aos sabados. 16 por dia
@REM desk-sim -m src/cc-5.py --mode single
@REM CC-6: Base + Atendimento aos sabados. 16 por dia + Nova escala
@REM desk-sim -m src/cc-6.py --mode single
@REM CC-7: Base + Atendimento aos sabados e domingos. 16 por dia
@REM desk-sim -m src/cc-7.py --mode single
@REM CC-8: Base + Atendimento aos sabados + 20% de demanda
@REM desk-sim -m src/cc-8.py --mode single
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