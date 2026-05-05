@echo off
set OPENBLAS_NUM_THREADS=1
python "%~dp0gws_cli.py" %*
