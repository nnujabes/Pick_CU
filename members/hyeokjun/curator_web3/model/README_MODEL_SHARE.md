# 양자화 모델 공유와 설치

`curator_web3`를 양자화 A.X로 실행하려는 팀원을 위한 안내입니다. 모델을 설치하지 않아도 web3는 규칙 파서로 동작합니다.

## 필요한 파일

| 항목 | 값 |
| --- | --- |
| 파일 | `pickcu-ax-Q5_K_M.gguf` (약 5.2GB) |
| 받는 곳 | https://huggingface.co/nnujabes/pickcu-ax-4.0-light-gguf (공개, 받는 방법은 `members/hyeokjun/huggingface/README.md`) |
| 넣는 위치 | `members/hyeokjun/curator_web3/model/ax-4.0-light/` |
| sha256 | `324e1bcb590b67df7928d72c2d13d55ecf70ef30e766bd0c48608d342fa71a6f` |

어댑터와 원본 모델은 필요 없습니다. 이 파일은 `.gitignore`로 제외되어 있으니 커밋하지 않습니다.

## 설치 순서

1. 최신 코드를 받고 Ollama를 설치합니다.
2. 모델 파일을 위 위치에 넣습니다. 같은 폴더에 `Modelfile`이 있어야 하고, 파일 이름은 바꾸지 않습니다.
3. 파일이 온전한지 확인합니다. 출력된 값이 위 sha256과 같아야 합니다. PowerShell은 대문자로 출력하지만 같은 값입니다.

   ```bash
   # WSL, Linux
   sha256sum pickcu-ax-Q5_K_M.gguf
   # Windows PowerShell
   Get-FileHash pickcu-ax-Q5_K_M.gguf
   ```

4. 그 폴더에서 Ollama에 모델을 등록합니다.

   ```bash
   cd members/hyeokjun/curator_web3/model/ax-4.0-light
   ollama create pickcu-ax:q5_k_m -f Modelfile
   ```

5. web3를 실행합니다.

   ```bash
   cd ../..
   pip install -r server/requirements.txt
   npm install
   npm start
   ```

6. http://localhost:5175 를 엽니다.

## 정상 동작 확인

| 서버 로그 | 의미 |
| --- | --- |
| `A.X 모델 로딩 완료` | 양자화 A.X로 동작 |
| `A.X를 불러오지 못해 규칙 파서를 씁니다` | 모델이 연결되지 않음. Ollama 실행 여부와 `ollama list`의 `pickcu-ax:q5_k_m`을 확인 |

## 주의할 점

- Windows와 WSL의 Ollama는 서로 별개입니다. `npm start`를 실행하는 환경의 Ollama에 등록합니다.
- WSL에서 실행할 때는 FastAPI가 설치된 Python 환경을 먼저 켜고, WSL 안에서 `npm install`을 합니다. Windows에서 설치한 `node_modules`는 WSL에서 쓸 수 없습니다.
- 등록이 끝나면 Ollama가 자체 복사본을 가지므로 받은 `.gguf` 파일은 지워도 됩니다.
- 측정 환경은 RTX 4060 8GB입니다. GPU가 없는 PC에서는 응답이 많이 느릴 수 있습니다.
