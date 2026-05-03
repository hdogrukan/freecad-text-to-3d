# FreeCAD Text-to-3D

Türkçe veya İngilizce doğal dil açıklamalarından FreeCAD üzerinde 3D model oluşturan Flask tabanlı web uygulaması.

## Özellikler

- Türkçe / İngilizce arayüz seçimi
- OpenAI API ile FreeCAD Python kodu üretimi
- Üretilen kodu arayüzde görüntüleme ve kopyalama
- FreeCADCmd ile modeli çalıştırma ve `.FCStd` olarak kaydetme
- FreeCAD GUI'de son modeli otomatik açma
- Sohbet geçmişiyle önceki modele göre revizyon isteme

## Mimari

```text
Tarayıcı
    ↕ HTTP
Flask Backend
    ↕ OpenAI API
OpenAI Model
    → FreeCAD Python kodu üretir
Flask Backend
    ↕ subprocess
FreeCADCmd
    → latest.FCStd dosyasını kaydeder
FreeCAD GUI
    → Kaydedilen modeli açar
```

## Gereksinimler

- macOS
- Python 3.9 veya üzeri
- FreeCAD
- OpenAI API anahtarı
- İnternet bağlantısı

Bu proje şu an varsayılan olarak macOS FreeCAD yolunu kullanır:

```text
/Applications/FreeCAD.app
```

Windows veya Linux desteği eklemek için [config.py](config.py) ve [freecad_bridge.py](freecad_bridge.py) içindeki FreeCAD yollarının güncellenmesi gerekir.

## Kurulum

### 1. Projeyi İndir

GitHub'dan klonlayın:

```bash
git clone https://github.com/kullanici-adiniz/freecad_text_to_3d.git
cd freecad_text_to_3d
```

ZIP olarak indirdiyseniz klasörü açın ve terminalde proje klasörüne girin.

### 2. FreeCAD Kur

FreeCAD'i resmi siteden indirin:

```text
https://www.freecad.org/downloads.php
```

macOS için uygulamayı `Applications` klasörüne taşıyın. Kurulumdan sonra şu dosya yolu var olmalıdır:

```text
/Applications/FreeCAD.app
```

Kontrol etmek için:

```bash
ls /Applications/FreeCAD.app
```

### 3. OpenAI API Anahtarını Ayarla

OpenAI API anahtarınızı ortam değişkeni olarak verebilirsiniz:

```bash
export OPENAI_API_KEY="sk-..."
```

Daha kalıcı kullanım için proje kökünde `.env` dosyası oluşturun:

```bash
cp .env.example .env
```

Ardından `.env` dosyasını açıp kendi anahtarınızı yazın:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Önemli: `.env` dosyasını GitHub'a göndermeyin. Bu repo için `.gitignore` içine eklenmiştir.

### 4. Otomatik Başlatma

macOS için en kolay yol:

```bash
chmod +x start.sh
./start.sh
```

Bu script:

- Python kurulumunu kontrol eder
- FreeCAD'in `/Applications/FreeCAD.app` altında olup olmadığını kontrol eder
- `venv` sanal ortamını oluşturur
- Python paketlerini kurar
- Uygulamayı `http://127.0.0.1:5000` adresinde başlatır

Uygulama başladıktan sonra tarayıcı otomatik açılır.

### 5. Manuel Kurulum

Otomatik script kullanmak istemiyorsanız:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python3 app.py
```

Sonra tarayıcıda açın:

```text
http://127.0.0.1:5000
```

## Kullanım

1. Uygulamayı başlatın.
2. Tarayıcıda `http://127.0.0.1:5000` adresini açın.
3. Üst çubuktan `TR` veya `EN` dilini seçin.
4. Sağ panelde `FreeCAD Aç` butonuyla FreeCAD GUI'yi açın.
5. Chat alanına model tarifinizi yazın.
6. Model oluşturulduğunda FreeCAD dosyası otomatik kaydedilir ve FreeCAD'de açılır.

Örnek Türkçe istekler:

```text
10×10×5 cm boyutlarında üstü açık dikdörtgen kutu
5 cm çaplı, 10 cm yüksekliğinde, 2 mm et kalınlıklı içi boş silindir
Üstte 2 cm, altta 4 cm çaplı, 8 cm yüksekliğinde koni
```

Example English prompts:

```text
An open rectangular box sized 10×10×5 cm
A hollow cylinder with 5 cm diameter, 10 cm height, and 2 mm wall thickness
A cone with 2 cm top diameter, 4 cm bottom diameter, and 8 cm height
```

## Çıktılar

Oluşturulan dosyalar varsayılan olarak şu klasöre kaydedilir:

```text
~/freecad_text_to_3d_output
```

En son model:

```text
~/freecad_text_to_3d_output/latest.FCStd
```

Son çalıştırılan Python kodu:

```text
~/freecad_text_to_3d_output/current_model.py
```

Uygulama ve FreeCAD olay logları:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/open_latest_in_gui.log
```

Web arayüzünde `Konsol > Loglar` ile son olayları görüntüleyebilirsiniz.

## Yapılandırma

Temel ayarlar [config.py](config.py) dosyasındadır.

| Ayar | Varsayılan | Açıklama |
|---|---:|---|
| `OPENAI_API_KEY` | `.env` veya ortam değişkeni | OpenAI API anahtarı |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Kod üretmek için kullanılan model |
| `FREECAD_PATH` | `/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd` | FreeCADCmd yolu |
| `FREECAD_PYTHON` | `/Applications/FreeCAD.app/Contents/Resources/bin/python` | FreeCAD Python yolu |
| `FLASK_HOST` | `127.0.0.1` | Flask sunucu host değeri |
| `FLASK_PORT` | `5000` | Flask sunucu portu |
| `OUTPUT_DIR` | `~/freecad_text_to_3d_output` | Model çıktı klasörü ve local chat geçmişi |

Modeli `.env` üzerinden değiştirmek için:

```env
OPENAI_MODEL=gpt-4o-mini
```

## Dosya Yapısı

```text
freecad_text_to_3d/
├── app.py
├── config.py
├── freecad_bridge.py
├── openai_bridge.py
├── requirements.txt
├── start.sh
├── templates/
│   └── index.html
├── .env.example
├── .gitignore
└── README.md
```

## Sorun Giderme

### `OPENAI_API_KEY environment değişkeni ayarlanmamış`

`.env` dosyanızı oluşturun veya terminalde şu komutu çalıştırın:

```bash
export OPENAI_API_KEY="sk-..."
```

### `FreeCAD bulunamadı`

FreeCAD'in şu konumda olduğundan emin olun:

```text
/Applications/FreeCAD.app
```

Farklı bir konuma kurduysanız [config.py](config.py) ve [freecad_bridge.py](freecad_bridge.py) içindeki yolları güncelleyin.

### Port 5000 kullanımda

[config.py](config.py) içindeki port değerini değiştirin:

```python
FLASK_PORT = 5001
```

Sonra uygulamayı tekrar başlatın.

### Paket kurulumu hata veriyor

Sanal ortamı yeniden oluşturun:

```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## GitHub'a Public Yüklemeden Önce

Şunları kontrol edin:

- `.env` dosyası GitHub'a eklenmemeli.
- `venv/` klasörü GitHub'a eklenmemeli.
- `__pycache__/` klasörü GitHub'a eklenmemeli.
- OpenAI API anahtarınızı README, kod veya commit geçmişine yazmayın.
- FreeCAD çıktı klasörünü repo içine taşıdıysanız GitHub'a eklemeyin.

İlk kez GitHub'a göndermek için:

```bash
git init
git add .
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/kullanici-adiniz/freecad_text_to_3d.git
git push -u origin main
```

## License

Public repo için bir lisans dosyası eklemeniz önerilir. Emin değilseniz MIT License çoğu açık kaynak demo/prototip proje için pratik bir seçenektir.
