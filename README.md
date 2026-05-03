# FreeCAD Text-to-3D

Create FreeCAD 3D models from natural-language prompts using OpenAI, Flask, and FreeCADCmd.

This project currently targets macOS and expects FreeCAD at:

```text
/Applications/FreeCAD.app
```

## Features

- Natural-language model generation in Turkish or English
- OpenAI-powered FreeCAD Python code generation
- Flask web UI with language selection
- Persistent local chat history
- Continue previous chats and revise existing models
- FreeCADCmd execution with `.FCStd` output
- FreeCAD GUI bridge for opening, styling, centering, and refreshing generated models
- Event logs for API, OpenAI, FreeCADCmd, and FreeCAD GUI steps

## Architecture

```text
Browser UI
    <-> Flask API
Flask Backend
    <-> OpenAI API
OpenAI Model
    -> FreeCAD Python code
Flask Backend
    <-> FreeCADCmd
FreeCADCmd
    -> .FCStd model file
FreeCAD GUI Bridge
    -> Opens and refreshes the generated model
```

## Requirements

- macOS
- Python 3.9+
- FreeCAD
- OpenAI API key
- Internet connection

Windows and Linux are not fully wired yet. To add support, update the FreeCAD paths in [config.py](config.py) and [freecad_bridge.py](freecad_bridge.py).

## FreeCAD Compatibility

This project is validated with FreeCAD `1.1.1` on macOS.

The local test installation reports:

```text
CFBundleVersion: 1.1.1
FreeCADCmd log: FreeCAD 1.1.1, Libs: 1.1.1R20260414
```

Older or newer FreeCAD versions may work, but the default paths and GUI bridge behavior are currently tested against FreeCAD `1.1.1`.

## Installation

### 1. Clone The Repository

```bash
git clone https://github.com/your-username/freecad-text-to-3d.git
cd freecad-text-to-3d
```

If you downloaded a ZIP, extract it and open the project folder in your terminal.

### 2. Install FreeCAD

Download FreeCAD from the official website:

```text
https://www.freecad.org/downloads.php
```

On macOS, move `FreeCAD.app` into the `Applications` folder. Verify that this path exists:

```bash
ls /Applications/FreeCAD.app
```

### 3. Configure Your OpenAI API Key

You can export the key in your terminal:

```bash
export OPENAI_API_KEY="sk-..."
```

For persistent local configuration, create a `.env` file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

Do not commit `.env`. It is already ignored by [.gitignore](.gitignore).

### 4. Quick Start

```bash
chmod +x start.sh
./start.sh
```

The script checks Python and FreeCAD, creates `venv`, installs dependencies, and starts the app at:

```text
http://127.0.0.1:5000
```

### 5. Manual Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

If you already created the virtual environment, use:

```bash
source venv/bin/activate
python app.py
```

## Usage

1. Start the Flask app.
2. Open `http://127.0.0.1:5000`.
3. Select `TR` or `EN` in the top bar.
4. Type a model request in the chat box.
5. Continue the same chat to revise the current model.
6. Use the sidebar to reopen previous local chats.
7. Use `Clear History` to delete local chat history.
8. Use `Console > Logs` to inspect API/OpenAI/FreeCAD events.

Example prompts:

```text
An open rectangular box sized 10x10x5 cm
A hollow cylinder with 5 cm diameter, 10 cm height, and 2 mm wall thickness
A cone with 2 cm top diameter, 4 cm bottom diameter, and 8 cm height
Draw a car
Make the car convertible
```

## Output Files

Generated files are stored in:

```text
~/freecad_text_to_3d_output
```

Important files:

```text
latest.FCStd
current_model.py
chat_history.json
events.jsonl
open_latest_in_gui.log
gui_command.json
gui_state.json
```

`latest.FCStd` is the latest generated model. Timestamped `model_*.FCStd` files are also created to avoid FreeCAD GUI caching issues.

## Configuration

Main settings live in [config.py](config.py).

| Setting | Default | Description |
|---|---:|---|
| `OPENAI_API_KEY` | `.env` or environment variable | OpenAI API key |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Model used for code generation |
| `FREECAD_PATH` | `/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd` | FreeCADCmd path |
| `FREECAD_PYTHON` | `/Applications/FreeCAD.app/Contents/Resources/bin/python` | FreeCAD Python path |
| `FREECAD_GUI` | `/Applications/FreeCAD.app/Contents/MacOS/FreeCAD` | FreeCAD GUI path |
| `FLASK_HOST` | `127.0.0.1` | Flask host |
| `FLASK_PORT` | `5000` | Flask port |
| `OUTPUT_DIR` | `~/freecad_text_to_3d_output` | Local output, logs, and chat history folder |

## Project Structure

```text
freecad-text-to-3d/
├── app.py
├── app_logger.py
├── chat_store.py
├── config.py
├── freecad_bridge.py
├── openai_bridge.py
├── requirements.txt
├── start.sh
├── templates/
│   └── index.html
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'flask'`

Activate the virtual environment first:

```bash
source venv/bin/activate
python app.py
```

### `OPENAI_API_KEY` is missing

Create `.env` or export the variable:

```bash
export OPENAI_API_KEY="sk-..."
```

### FreeCAD Is Not Found

Make sure FreeCAD exists at:

```text
/Applications/FreeCAD.app
```

If you installed it elsewhere, update [config.py](config.py) and [freecad_bridge.py](freecad_bridge.py).

### Port 5000 Is In Use

Change `FLASK_PORT` in [config.py](config.py), for example:

```python
FLASK_PORT = 5001
```

### FreeCAD GUI Does Not Refresh

Open the web console and click `Logs`. Also inspect:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/open_latest_in_gui.log
~/freecad_text_to_3d_output/gui_state.json
```

Close all FreeCAD windows and restart the Flask app if an old GUI bridge is still running.

## Contributing

Contributions are welcome.

This project is still evolving around FreeCAD automation, model revision workflows, prompt quality, UI responsiveness, logging, and cross-platform support.

Good areas to contribute:

- Improve FreeCAD model generation prompts
- Make existing-model revision workflows more reliable
- Improve FreeCAD GUI refresh, centering, and visibility handling
- Add Windows and Linux FreeCAD path support
- Improve the responsive web UI
- Add tests for chat history, code extraction, and FreeCAD execution
- Improve documentation, installation guides, and example prompts
- Add screenshots, demo GIFs, or sample generated models

### Development Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

### Good First Issues

Good first contributions include:

- Add more example prompts
- Improve README wording
- Add screenshots or demo GIFs
- Improve error messages
- Add small UI polish
- Add tests for chat history

### Pull Request Checklist

Before opening a PR, please check:

- The app starts with `python app.py`
- No API keys, `.env` files, logs, or generated `.FCStd` files are committed
- README or docs are updated if behavior changes
- FreeCAD-related changes are tested with FreeCAD when possible
- The UI still works on desktop and mobile widths

## Before Publishing Publicly

Check these before pushing to GitHub:

- Do not commit `.env`.
- Do not commit `venv/`.
- Do not commit `__pycache__/`.
- Do not commit generated `.FCStd` files.
- Do not paste your OpenAI API key into README, source code, issues, commits, or logs.
- If your API key was exposed in logs, rotate it in the OpenAI dashboard.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

---

# FreeCAD Text-to-3D

OpenAI, Flask ve FreeCADCmd kullanarak doğal dil komutlarından FreeCAD 3D modelleri oluşturan web uygulaması.

Bu proje şu anda macOS hedeflidir ve FreeCAD'in şu konumda olmasını bekler:

```text
/Applications/FreeCAD.app
```

## Özellikler

- Türkçe veya İngilizce doğal dil ile model üretimi
- OpenAI ile FreeCAD Python kodu üretimi
- Dil seçimi olan Flask web arayüzü
- Kalıcı local chat geçmişi
- Eski chatlere dönüp mevcut modeli revize etme
- FreeCADCmd ile `.FCStd` çıktısı üretme
- Oluşturulan modeli açan, renklendiren, ortalayan ve yenileyen FreeCAD GUI bridge
- API, OpenAI, FreeCADCmd ve FreeCAD GUI adımları için olay logları

## Mimari

```text
Tarayıcı Arayüzü
    <-> Flask API
Flask Backend
    <-> OpenAI API
OpenAI Model
    -> FreeCAD Python kodu
Flask Backend
    <-> FreeCADCmd
FreeCADCmd
    -> .FCStd model dosyası
FreeCAD GUI Bridge
    -> Üretilen modeli açar ve yeniler
```

## Gereksinimler

- macOS
- Python 3.9+
- FreeCAD
- OpenAI API anahtarı
- İnternet bağlantısı

Windows ve Linux desteği henüz tam bağlanmadı. Destek eklemek için [config.py](config.py) ve [freecad_bridge.py](freecad_bridge.py) içindeki FreeCAD yollarını güncelleyin.

## FreeCAD Uyumluluğu

Bu proje macOS üzerinde FreeCAD `1.1.1` ile doğrulandı.

Local test kurulumunda görülen bilgiler:

```text
CFBundleVersion: 1.1.1
FreeCADCmd log: FreeCAD 1.1.1, Libs: 1.1.1R20260414
```

Daha eski veya daha yeni FreeCAD sürümleri çalışabilir, ancak varsayılan yollar ve GUI bridge davranışı şu anda FreeCAD `1.1.1` ile test edilmiştir.

## Kurulum

### 1. Repoyu Klonlayın

```bash
git clone https://github.com/kullanici-adiniz/freecad-text-to-3d.git
cd freecad-text-to-3d
```

ZIP olarak indirdiyseniz klasörü açın ve terminalde proje klasörüne girin.

### 2. FreeCAD Kurun

FreeCAD'i resmi siteden indirin:

```text
https://www.freecad.org/downloads.php
```

macOS'te `FreeCAD.app` dosyasını `Applications` klasörüne taşıyın. Şu yolu kontrol edin:

```bash
ls /Applications/FreeCAD.app
```

### 3. OpenAI API Anahtarını Ayarlayın

Terminalde ortam değişkeni olarak verebilirsiniz:

```bash
export OPENAI_API_KEY="sk-..."
```

Kalıcı local kullanım için `.env` dosyası oluşturun:

```bash
cp .env.example .env
```

Sonra `.env` dosyasını düzenleyin:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

`.env` dosyasını commit etmeyin. [.gitignore](.gitignore) içinde ignore edilmiştir.

### 4. Hızlı Başlangıç

```bash
chmod +x start.sh
./start.sh
```

Bu script Python ve FreeCAD kontrolü yapar, `venv` oluşturur, bağımlılıkları kurar ve uygulamayı şu adreste başlatır:

```text
http://127.0.0.1:5000
```

### 5. Manuel Başlatma

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Sonra tarayıcıda açın:

```text
http://127.0.0.1:5000
```

Sanal ortam daha önce oluşturulduysa:

```bash
source venv/bin/activate
python app.py
```

## Kullanım

1. Flask uygulamasını başlatın.
2. `http://127.0.0.1:5000` adresini açın.
3. Üst bardan `TR` veya `EN` seçin.
4. Chat kutusuna model isteğinizi yazın.
5. Aynı chat içinde devam ederek mevcut modeli revize edin.
6. Sol panelden eski local chatleri açın.
7. `Geçmişi Temizle` ile local chat geçmişini silin.
8. `Konsol > Loglar` ile API/OpenAI/FreeCAD olaylarını inceleyin.

Örnek istekler:

```text
10x10x5 cm boyutlarında üstü açık dikdörtgen kutu
5 cm çaplı, 10 cm yüksekliğinde, 2 mm et kalınlıklı içi boş silindir
Üstte 2 cm, altta 4 cm çaplı, 8 cm yüksekliğinde koni
Bir araba çiz
Arabanın üstü açık olsun
```

## Çıktı Dosyaları

Üretilen dosyalar varsayılan olarak burada tutulur:

```text
~/freecad_text_to_3d_output
```

Önemli dosyalar:

```text
latest.FCStd
current_model.py
chat_history.json
events.jsonl
open_latest_in_gui.log
gui_command.json
gui_state.json
```

`latest.FCStd` en son üretilen modeldir. FreeCAD GUI cache sorunlarını azaltmak için zaman damgalı `model_*.FCStd` dosyaları da oluşturulur.

## Yapılandırma

Ana ayarlar [config.py](config.py) dosyasındadır.

| Ayar | Varsayılan | Açıklama |
|---|---:|---|
| `OPENAI_API_KEY` | `.env` veya ortam değişkeni | OpenAI API anahtarı |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Kod üretimi için kullanılan model |
| `FREECAD_PATH` | `/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd` | FreeCADCmd yolu |
| `FREECAD_PYTHON` | `/Applications/FreeCAD.app/Contents/Resources/bin/python` | FreeCAD Python yolu |
| `FREECAD_GUI` | `/Applications/FreeCAD.app/Contents/MacOS/FreeCAD` | FreeCAD GUI yolu |
| `FLASK_HOST` | `127.0.0.1` | Flask host değeri |
| `FLASK_PORT` | `5000` | Flask portu |
| `OUTPUT_DIR` | `~/freecad_text_to_3d_output` | Local çıktı, log ve chat geçmişi klasörü |

## Proje Yapısı

```text
freecad-text-to-3d/
├── app.py
├── app_logger.py
├── chat_store.py
├── config.py
├── freecad_bridge.py
├── openai_bridge.py
├── requirements.txt
├── start.sh
├── templates/
│   └── index.html
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Sorun Giderme

### `ModuleNotFoundError: No module named 'flask'`

Önce sanal ortamı aktif edin:

```bash
source venv/bin/activate
python app.py
```

### `OPENAI_API_KEY` eksik

`.env` oluşturun veya ortam değişkeni olarak verin:

```bash
export OPENAI_API_KEY="sk-..."
```

### FreeCAD bulunamadı

FreeCAD'in şu konumda olduğundan emin olun:

```text
/Applications/FreeCAD.app
```

Farklı bir konuma kurduysanız [config.py](config.py) ve [freecad_bridge.py](freecad_bridge.py) dosyalarını güncelleyin.

### Port 5000 kullanımda

[config.py](config.py) içinde `FLASK_PORT` değerini değiştirin:

```python
FLASK_PORT = 5001
```

### FreeCAD GUI yenilenmiyor

Web konsolda `Loglar` butonuna basın. Ayrıca şunları inceleyin:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/open_latest_in_gui.log
~/freecad_text_to_3d_output/gui_state.json
```

Eski bir GUI bridge hâlâ çalışıyorsa tüm FreeCAD pencerelerini kapatıp Flask uygulamasını yeniden başlatın.

## Katkı Verme

Katkılara açıktır.

Bu proje özellikle FreeCAD otomasyonu, mevcut modeli güncelleme akışı, prompt kalitesi, responsive arayüz, log sistemi ve farklı işletim sistemi desteği tarafında geliştirilmeye uygundur.

Katkı verilebilecek alanlar:

- FreeCAD model üretim promptlarını iyileştirme
- Mevcut çizim üzerinde revizyon akışını daha güvenilir hale getirme
- FreeCAD GUI yenileme, ortalama ve görünürlük davranışını iyileştirme
- Windows ve Linux FreeCAD path desteği ekleme
- Responsive web arayüzünü geliştirme
- Chat history, kod ayıklama ve FreeCAD çalıştırma için test ekleme
- Kurulum dokümantasyonu ve örnek promptları geliştirme
- Ekran görüntüleri, demo GIF'leri veya örnek üretilmiş modeller ekleme

### Geliştirme Kurulumu

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Sonra tarayıcıda açın:

```text
http://127.0.0.1:5000
```

### İlk Katkı İçin Uygun İşler

İlk katkı için uygun işler:

- Daha fazla örnek prompt ekleme
- README metnini iyileştirme
- Ekran görüntüsü veya demo GIF ekleme
- Hata mesajlarını iyileştirme
- Küçük UI düzenlemeleri yapma
- Chat history için test ekleme

### Pull Request Kontrol Listesi

PR açmadan önce kontrol edin:

- Uygulama `python app.py` ile açılıyor
- API key, `.env`, log veya üretilmiş `.FCStd` dosyaları commit edilmedi
- Davranış değiştiyse README veya dokümantasyon güncellendi
- FreeCAD tarafına dokunan değişiklikler mümkünse FreeCAD ile test edildi
- UI desktop ve mobil genişliklerde çalışıyor

## Public Yayınlamadan Önce

GitHub'a göndermeden önce şunları kontrol edin:

- `.env` commit edilmemeli.
- `venv/` commit edilmemeli.
- `__pycache__/` commit edilmemeli.
- Üretilen `.FCStd` dosyaları commit edilmemeli.
- OpenAI API anahtarınızı README, kaynak kod, issue, commit veya log içine yazmayın.
- API key loglara düştüyse OpenAI dashboard üzerinden rotate edin.

## Lisans

Bu proje MIT License ile lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.
