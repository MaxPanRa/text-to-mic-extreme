# Text to Mic Fork

[Jump to Spanish / Ir a Espanol](#espanol)

This repository is a fork/customized version of the original **Text to Mic** project by Scorchsoft. Please keep the original license and attribution files when redistributing this fork.

## What's New In This Fork

This fork adds a faster writer-focused workflow and packaging improvements on top of the original app:

- Compact writer mode with a much smaller one-line layout
- Borderless compact window with right-click context menu
- Always-on-top mode
- Adjustable window opacity
- Global "Focus Writer" hotkey
- `Enter` or `Ctrl+Enter` send mode toggle
- Send confirmation sound
- Quick tone selector next to `Play`
- AI-generated tone presets saved automatically into the app
- Stronger tone prompting and tone intensity control
- Speech model switching between `gpt-4o-mini-tts`, `tts-1-hd`, and `gpt-audio-1.5`
- Voice labels for easier selection, especially on `Audio 1.5`
- Root `.env` support for GUI, CLI, and packaged EXE
- `build-exe.bat` for building the Windows executable with the included `.venv`

## About

**Text to Mic** converts written text into speech and plays it through normal audio devices or a virtual microphone such as VB-Cable. It can be used for meetings, accessibility workflows, live roleplay, streaming, or any situation where you want typed text to be spoken aloud.

The original project was created by Scorchsoft. This fork keeps the same overall purpose while changing the UX, packaging flow, and OpenAI voice workflow.

## Setup

### 1. Install VB-Cable

If you want to send the voice into another app as a microphone, install VB-Cable first:

https://vb-audio.com/Cable/

### 2. Create the root `.env`

This fork now uses **only one `.env` file in the project root**.

You do **not** need `config/.env`.

Create a file named `.env` in the same folder as:

- `text-to-mic.py`
- `text-to-mic-cli.py`
- `build-exe.bat`

You can start from `.env.example`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

For local development, the expected location is:

`text-to-mic-main/.env`

For the packaged EXE, place the `.env` next to:

`dist/text-to-mic.exe`

### 3. Use the included virtual environment

This fork is prepared to run from the local `.venv`:

```powershell
.\.venv\Scripts\python .\text-to-mic.py
```

If you want to activate it first:

```powershell
.\.venv\Scripts\Activate.ps1
python .\text-to-mic.py
```

### 4. CLI usage

The CLI also reads the same root `.env`:

```powershell
.\.venv\Scripts\python .\text-to-mic-cli.py "Hello from Text to Mic"
```

## Main Fork Features

### Compact Writer UX

- A smaller compact writing mode
- Borderless layout
- Right-click settings menu in compact mode
- One-line text input plus `Play`
- Optional always-on-top overlay behavior

### Keyboard Workflow

- Global writer focus hotkey
- `Enter` to send, or `Ctrl+Enter` to send
- `Shift+Enter` for a new line when needed
- Sound feedback when sending text from the keyboard

### Voice Workflow

- Quick tone selection near the play button
- AI tone generation from natural language requests
- Auto-save and auto-select for newly generated tones
- Tone intensity settings to make style instructions stronger
- Faster switching between `gpt-4o-mini-tts`, `tts-1-hd`, and `gpt-audio-1.5`

## Notes About Speech Models

- `gpt-4o-mini-tts`: best when tone instructions matter most
- `tts-1-hd`: clean output, but it does not support instruction-based tone control
- `gpt-audio-1.5`: more natural and expressive, but it needs stricter prompting so it repeats your text instead of replying conversationally

## Build The EXE

Run:

```powershell
.\build-exe.bat
```

What the script does:

- uses the project `.venv`
- installs `pyinstaller` into `.venv` if missing
- clears old `build/` and `dist/`
- builds from `text-to-mic.spec`

Output:

`dist/text-to-mic.exe`

The build script also copies these helper files into `dist/`:

- `LICENSE.md`
- `.env.example`

After building, create or copy your real `.env` next to the EXE if you want OpenAI voices to work in the packaged app.

## Git / Fork Notes

- `.env` is ignored and should stay private
- `.env.example` is tracked so other users know the required format
- This repo currently allows committing `.venv` if you want an all-in-one upload, but the repository size will become much larger
- Keep the original license and Scorchsoft attribution in place when publishing your fork

## License

This project remains under the original licensing terms included in [LICENSE.md](LICENSE.md).

## Espanol

Este repositorio es un fork personalizado del proyecto original **Text to Mic** de Scorchsoft. Se conservaron la licencia y la atribucion original, pero se cambiaron varias partes del flujo para hacerlo mas practico como overlay/escritor rapido y para empaquetarlo mejor.

### Cambios principales de este fork

- Modo compacto mucho mas pequeno
- Ventana compacta sin bordes
- Menu con clic derecho en modo compacto
- Opcion de `Always on Top`
- Control de opacidad
- Atajo global para enfocar el escritor
- Opcion para enviar con `Enter` o `Ctrl+Enter`
- Sonidito al enviar
- Selector rapido de tono junto a `Play`
- Generacion de tonos con IA
- Mayor intensidad de tonos
- Cambio rapido entre `gpt-4o-mini-tts`, `tts-1-hd` y `gpt-audio-1.5`
- Etiquetas utiles para las voces
- Uso de un solo `.env` en la raiz
- `build-exe.bat` para generar el `.exe`

### Como configurar el `.env`

En este fork ya no hace falta `config/.env`.

Solo usa un archivo `.env` en la raiz del proyecto, en la misma carpeta donde estan:

- `text-to-mic.py`
- `text-to-mic-cli.py`
- `build-exe.bat`

Contenido:

```env
OPENAI_API_KEY=tu_api_key_aqui
```

Tambien puedes copiar el archivo `.env.example`.

Si generas el ejecutable, el `.env` debe ir al lado de:

`dist/text-to-mic.exe`

### Como ejecutar

```powershell
.\.venv\Scripts\python .\text-to-mic.py
```

### Como compilar a EXE

```powershell
.\build-exe.bat
```

Ese script usa la `.venv` del proyecto, instala `pyinstaller` si hace falta y genera:

`dist/text-to-mic.exe`

### Nota para subirlo a Git

Puedes subir la `.venv` si quieres que el fork venga en un solo paquete, pero el repositorio va a crecer bastante. Aun asi, no conviene subir tu `.env` real con una API key valida.
