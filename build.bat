@echo off
echo ============================================
echo  Building Excellon RPA Executables
echo ============================================
echo.

echo [1/5] Installing PyInstaller...
uv pip install pyinstaller
echo.

echo [2/5] Building excellon-rpa (onedir mode)...
.venv\Scripts\pyinstaller.exe excellon-rpa.spec --noconfirm
if errorlevel 1 (echo ERROR: excellon-rpa build failed & pause & exit /b 1)
echo.

echo [3/5] Building run-report (onedir mode)...
.venv\Scripts\pyinstaller.exe run-report.spec --noconfirm
if errorlevel 1 (echo ERROR: run-report build failed & pause & exit /b 1)
echo.

echo [4/5] Packaging client folder...
if exist "excellon_v1.0" rmdir /s /q "excellon_v1.0"
mkdir "excellon_v1.0"
xcopy dist\excellon-rpa\* excellon_v1.0\ /E /I /Q /Y
xcopy dist\run-report\* excellon_v1.0\ /E /I /Q /Y
copy .env excellon_v1.0\
copy reports.json excellon_v1.0\
copy license.key excellon_v1.0\
echo.

echo [5/5] Creating excellon_v1.0.zip...
if exist "excellon_v1.0.zip" del /q "excellon_v1.0.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'excellon_v1.0\*' -DestinationPath 'excellon_v1.0.zip' -Force"
if errorlevel 1 (echo ERROR: zip creation failed & pause & exit /b 1)
echo.

echo ============================================
echo  Build complete!
echo ============================================
echo.
echo Ready-to-ship folder:
echo   excellon_v1.0\
echo     excellon-rpa.exe
echo     run-report.exe
echo     license.key
echo     .env
echo     reports.json
echo     assets\
echo     _internal\   (dependencies)
echo.
echo Zipped archive: excellon_v1.0.zip
echo.
echo Copy the ENTIRE excellon_v1.0 folder (or excellon_v1.0.zip) to the client PC.
echo.
pause
