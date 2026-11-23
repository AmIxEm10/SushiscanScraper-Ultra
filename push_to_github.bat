@echo off
chcp 65001 > nul
title Publication sur GitHub

echo ==============================================================
echo     🍣 Publication de SushiscanScraper Ultra sur GitHub
echo ==============================================================
echo.

set /p REPO_URL="Entrez l'URL de votre depot GitHub (ex: https://github.com/pseudo/repo.git) : "

if "%REPO_URL%"=="" (
    echo Aucune URL entree. Annulation.
    pause
    exit /b
)

echo.
echo Configuration du depot distant...
git -c safe.directory=* remote set-url origin %REPO_URL% 2>nul || git -c safe.directory=* remote add origin %REPO_URL%

echo.
echo Envoi du code sur GitHub (git push)...
git -c safe.directory=* push -u origin main

echo.
echo ==============================================================
if %ERRORLEVEL% equ 0 (
    echo 🎉 Publication reussie sur votre GitHub !
) else (
    echo ⚠️ Une erreur est survenue lors de l'envoi. Verifiez que vous etes connecte a GitHub dans votre terminal ou navigateur.
)
echo ==============================================================
pause
