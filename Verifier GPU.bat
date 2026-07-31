@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo  Verification GPU (visages)
echo ================================================
echo.
echo --- 1) PyTorch voit-il le GPU ? ---
".venv\Scripts\python.exe" -c "import torch; print('torch', torch.__version__); print('CUDA dispo (torch):', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else '(aucun)')"
echo.
echo --- 2) onnxruntime : providers disponibles ---
".venv\Scripts\python.exe" -c "import torch, onnxruntime as ort; getattr(ort,'preload_dlls',lambda:None)(); print('Providers ONNX:', ort.get_available_providers())"
echo.
echo --- 3) Test reel : session InsightFace sur GPU (torch importe en 1er) ---
".venv\Scripts\python.exe" -c "import torch; import onnxruntime as ort; getattr(ort,'preload_dlls',lambda:None)(); from insightface.app import FaceAnalysis; a=FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider','CPUExecutionProvider'], allowed_modules=['detection','recognition']); a.prepare(ctx_id=0, det_size=(640,640)); print('Providers detection:', a.models['detection'].session.get_providers())"
echo.
echo ================================================
echo  Si l'etape 3 montre 'CUDAExecutionProvider' = GPU pleinement operationnel.
echo  (Il faut assez de VRAM libre a cet instant : si Ollama tourne, repli CPU normal.)
echo ================================================
echo.
pause
