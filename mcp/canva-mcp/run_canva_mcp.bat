@echo off
cd /d "%~dp0"
node --env-file=.env dist/server/server.js
