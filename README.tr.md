# FreeCAD Text-to-3D

[English README](README.md)

OpenAI, Flask ve FreeCADCmd kullanarak doğal dil komutlarından FreeCAD 3D modelleri oluşturan yerel web uygulaması.

Uygulama macOS ve Windows destekler. Varsayılan FreeCAD keşfi şu yaygın kurulum konumlarını kontrol eder:

```text
macOS:   /Applications/FreeCAD.app
Windows: C:\Program Files\FreeCAD*\bin\FreeCADCmd.exe
```

## Özellikler

- Türkçe veya İngilizce doğal dil ile 3D model üretimi
- OpenAI ile FreeCAD Python API kodu üretimi
- Flask tabanlı yerel web arayüzü
- Dil seçimi: `TR` ve `EN`
- OpenAI API key ve model ayarını arayüzden değiştirme
- Üretim modları:
  - `3D`: yalnızca 3D model
  - `3D + Teknik`: 3D model ile birlikte mümkün olduğunda TechDraw teknik çizim sayfası
  - `Sketch`: parametrik sketch / PartDesign odaklı üretim
- Aynı chat içinde önceki modeli koruyarak revizyon yapma
- Yerel ve kalıcı chat geçmişi
- Eski chatleri sol panelden tekrar açma
- FreeCADCmd ile `.FCStd` model dosyası üretme
- Zaman damgalı model dosyaları ve `latest.FCStd` alias dosyası
- FreeCAD GUI bridge ile modeli otomatik açma, yenileme, ortalama ve temel renklendirme
- FreeCAD'de elle yapılan değişiklikleri `Aktif FreeCAD'i Al` ile uygulama bağlamına senkronize etme
- OpenAI çıktısı eksik veya hatalıysa otomatik kod doğrulama ve en fazla 2 onarım denemesi
- FreeCADCmd için GUI-only satırları temizleme ve bazı FreeCAD 1.1.x uyumluluk düzeltmeleri
- API, OpenAI, FreeCADCmd ve FreeCAD GUI olayları için log paneli

## Mimari

```text
Tarayıcı arayüzü
    <-> Flask API
Flask backend
    <-> OpenAI API
OpenAI modeli
    -> FreeCAD Python kodu
Flask backend
    <-> FreeCADCmd
FreeCADCmd
    -> .FCStd model dosyası
FreeCAD GUI bridge
    -> modeli FreeCAD GUI içinde açar, yeniler ve senkronize eder
```

## Gereksinimler

- macOS veya Windows
- Python 3.10+
- FreeCAD
- OpenAI API anahtarı
- İnternet bağlantısı

Özel FreeCAD kurulumları için `.env` veya shell üzerinden `FREECAD_HOME`, `FREECAD_CMD`, `FREECAD_GUI` ya da `FREECAD_PYTHON` ayarlanabilir.

## FreeCAD Uyumluluğu

Bu proje macOS üzerinde FreeCAD `1.1.1` ile doğrulandı. Windows desteği standart `C:\Program Files\FreeCAD...\bin` klasör yapısı için bağlandı.

Yerel test kurulumunda görülen bilgiler:

```text
CFBundleVersion: 1.1.1
FreeCADCmd log: FreeCAD 1.1.1, Libs: 1.1.1R20260414
```

Daha eski veya daha yeni FreeCAD sürümleri çalışabilir, ancak varsayılan yollar ve GUI bridge davranışı şu anda FreeCAD `1.1.1` üzerinde test edilmiştir.

## Kurulum

### 1. Repoyu Hazırlayın

```bash
git clone https://github.com/hdogrukan/freecad-text-to-3d.git
cd freecad-text-to-3d
```

ZIP olarak indirdiyseniz klasörü açıp terminalde proje klasörüne girin.

### 2. FreeCAD Kurun

FreeCAD'i resmi siteden indirin:

```text
https://www.freecad.org/downloads.php
```

macOS'te `FreeCAD.app` dosyasını `Applications` klasörüne taşıyın. Şu yolu kontrol edin:

```bash
ls /Applications/FreeCAD.app
```

Windows'ta FreeCAD'i varsayılan `Program Files` konumuna kurun ve şu dosyalardan birinin var olduğunu doğrulayın:

```text
C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe
C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe
```

### 3. OpenAI API Anahtarını Ayarlayın

Geçici kullanım için terminalde ortam değişkeni verebilirsiniz:

```bash
export OPENAI_API_KEY="sk-..."
```

Kalıcı yerel kullanım için `.env` dosyası oluşturun:

```bash
cp .env.example .env
```

Sonra `.env` dosyasını düzenleyin:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

`.env` dosyasını commit etmeyin. Dosya [.gitignore](.gitignore) içinde ignore edilmiştir.

## Çalıştırma

### macOS Hızlı Başlangıç

```bash
chmod +x start.sh
./start.sh
```

`start.sh` şu kontrolleri ve hazırlıkları yapar:

- Python kontrolü
- FreeCAD varlık ve sürüm kontrolü
- `venv` oluşturma
- Python bağımlılıklarını kurma
- Çıktı klasörünü oluşturma
- Flask uygulamasını başlatma

Uygulama varsayılan olarak şu adreste açılır:

```text
http://127.0.0.1:5000
```

### Windows Hızlı Başlangıç

Proje klasöründe PowerShell açın:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```

### macOS Manuel Başlatma

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Sanal ortam daha önce oluşturulduysa:

```bash
source venv/bin/activate
python app.py
```

### Windows Manuel Başlatma

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Kullanım

1. Flask uygulamasını başlatın.
2. Tarayıcıda `http://127.0.0.1:5000` adresini açın.
3. Üst bardan `TR` veya `EN` seçin.
4. Gerekirse `Ayarlar` panelinden OpenAI API key ve model değerini girin.
5. Üretim modunu seçin: `3D`, `3D + Teknik` veya `Sketch`.
6. Chat kutusuna model isteğinizi yazın.
7. Uygulama OpenAI'den FreeCAD Python kodu alır, kodu doğrular, FreeCADCmd ile çalıştırır ve modeli FreeCAD GUI içinde açar.
8. Aynı chat içinde devam ederek mevcut modeli revize edin.
9. Modeli FreeCAD içinde elle değiştirdiyseniz yeni revizyon istemeden önce `Aktif FreeCAD'i Al` butonuna basın.
10. Sol panelden eski yerel chatleri açın.
11. `Geçmişi Temizle` ile yerel chat geçmişini silin.
12. `Konsol > Loglar` ile API, OpenAI, FreeCADCmd ve FreeCAD GUI olaylarını inceleyin.

Örnek istekler:

```text
10x10x5 cm boyutlarında üstü açık dikdörtgen kutu
5 cm çaplı, 10 cm yüksekliğinde, 2 mm et kalınlıklı içi boş silindir
Üstte 2 cm, altta 4 cm çaplı, 8 cm yüksekliğinde koni
Bir araba çiz
Arabanın üstü açık olsun
Ön, üst ve sağ görünüşleri olan teknik çizim de ekle
Parametrik olarak delikli bir bağlantı plakası oluştur
```

## Üretim Modları

### 3D

Standart moddur. FreeCAD `Part` API, primitive solid'ler ve boolean operasyonları ile doğrudan 3D model üretir. Teknik çizim istenmedikçe TechDraw sayfası oluşturmaz.

### 3D + Teknik

3D modeli üretir ve mümkün olduğunda TechDraw sayfası ekler. Ön, üst, sağ ve izometrik görünüşler hedeflenir. TechDraw kurulumu hata verirse model üretiminin başarısız olmaması için çizim adımı korumalı çalıştırılır.

### Sketch

Mekanik parçalar için parametrik PartDesign Body, Sketcher constraint'leri, pad/pocket operasyonları ve üstte isimlendirilmiş ölçü değişkenleri tercih edilir. Dekoratif veya serbest formlu modellerde yine parametreli Part primitive yaklaşımı kullanılabilir.

## Otomatik Onarım ve Kod Güvenliği

Uygulama OpenAI cevabından tek bir `python` kod bloğu çıkarır ve kodun gerçekten çalıştırılabilir FreeCAD script'i olup olmadığını kontrol eder.

Temel doğrulamalar:

- Python syntax kontrolü
- En az bir `doc.addObject(...)` çağrısı
- `doc.recompute()` çağrısı
- Eksik veya yarım FreeCAD kodunu reddetme

FreeCADCmd çalıştırması hata verirse uygulama aynı bağlamı, hata mesajını ve başarısız kodu OpenAI'ye göndererek otomatik onarım ister. Varsayılan en fazla onarım denemesi: `2`.

FreeCADCmd uyumluluğu için bazı satırlar otomatik temizlenir veya dönüştürülür:

- `FreeCADGui`, `activeView()`, `fitAll()` gibi GUI-only çağrılar kaldırılır
- Sketch support ve map mode atamaları daha güvenli forma çevrilir
- FreeCAD 1.1.x ile uyumsuz `shape.scale(x, y, z)` çağrıları matrix tabanlı non-uniform scale işlemine dönüştürülür

## OpenAI Ayarları ve API Key Güvenliği

OpenAI ayarları iki şekilde verilebilir:

- `.env` dosyası veya ortam değişkeni ile global varsayılan ayar
- Web arayüzündeki `Ayarlar` paneli ile geçerli tarayıcı oturumu için ayar

Arayüzden girilen API key güvenlik için şu şekilde ele alınır:

- Tarayıcı `localStorage` veya `sessionStorage` içine yazılmaz.
- API cevaplarında kullanıcıya geri döndürülmez.
- Olay loglarına yazılmaz.
- Flask server-side session dosyasına düz metin olarak yazılmaz; session dosyasında yalnızca rastgele bir ayar kimliği tutulur.
- API key çalışan Flask process belleğinde tutulur; uygulama yeniden başlatılınca veya 8 saatlik oturum TTL'i dolunca kaybolur.
- `Temizle` butonu oturuma ait bellek içi OpenAI ayarını siler ve `.env` varsayılanlarına döner.

Bu güvenlik modeli yerel kullanım içindir. Uygulamayı başka makinelerin erişebileceği bir host üzerinde çalıştırmayın; varsayılan `127.0.0.1` ayarını koruyun.

## Aktif FreeCAD Senkronizasyonu

`Aktif FreeCAD'i Al` butonu, FreeCAD GUI bridge üzerinden açık aktif dokümanı okur ve uygulama bağlamına kaydeder.

Senkronizasyon çıktıları:

- Aktif dokümanın kopyası: `active_freecad_document.FCStd`
- Nesne özeti: `active_freecad_context.json`
- Nesne adları, label bilgileri, tipler, görünürlük ve bounding box bilgileri

Web arayüzü yeni senkronize edilmişse sonraki chat isteği bu dokümanı mevcut çizim bağlamı olarak kullanabilir. Senkronize bağlam tek kullanımlık UI durumu gibi ele alınır; böylece eski senkronize dokümanlar ilgisiz chat'lerde yanlışlıkla tekrar kullanılmaz. Bu akış, FreeCAD içinde elle yapılan değişikliklerden sonra yeni AI revizyonu istemek için kullanılır.

## Çıktı Dosyaları

Varsayılan çıktı klasörü:

```text
~/freecad_text_to_3d_output
```

Önemli dosyalar:

| Dosya | Açıklama |
|---|---|
| `latest.FCStd` | En son başarılı modelin alias dosyası |
| `model_*.FCStd` | Zaman damgalı model çıktıları |
| `current_model.py` | Son çalıştırılan, sarılmış FreeCAD Python script'i |
| `chat_history.json` | Yerel chat geçmişi |
| `events.jsonl` | API, OpenAI, FreeCADCmd ve GUI olay logları |
| `open_latest_in_gui.py` | FreeCAD GUI bridge script'i |
| `open_latest_in_gui.log` | GUI bridge log dosyası |
| `gui_command.json` | Flask -> GUI bridge komut dosyası |
| `gui_state.json` | GUI bridge durum ve heartbeat dosyası |
| `active_freecad_context.json` | Senkronize aktif FreeCAD doküman özeti |
| `active_freecad_document.FCStd` | Senkronize aktif FreeCAD doküman kopyası |

## Yapılandırma

Ana ayarlar [config.py](config.py) dosyasındadır.

| Ayar | Varsayılan | Açıklama |
|---|---|---|
| `OPENAI_API_KEY` | `.env` veya ortam değişkeni | OpenAI API anahtarı |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Kod üretimi için kullanılan model |
| `FREECAD_HOME` / `FREECAD_APP_DIR` / `FREECAD_ROOT` | otomatik algılanır | FreeCAD kurulum kökü |
| `FREECAD_CMD` / `FREECAD_PATH` | otomatik algılanır | FreeCADCmd executable yolu |
| `FREECAD_PYTHON` | otomatik algılanır | FreeCAD Python yolu |
| `FREECAD_GUI` | otomatik algılanır | FreeCAD GUI executable yolu |
| `FLASK_HOST` | `127.0.0.1` | Flask host değeri |
| `FLASK_PORT` | `5000` | Flask portu |
| `DEBUG` | `False` | Flask debug modu |
| `OUTPUT_DIR` | `~/freecad_text_to_3d_output` | Yerel çıktı, log ve chat geçmişi klasörü |
| `CHAT_HISTORY_PATH` | `OUTPUT_DIR/chat_history.json` | Chat geçmişi dosyası |
| `EVENT_LOG_PATH` | `OUTPUT_DIR/events.jsonl` | Olay log dosyası |

`.env` ile desteklenen başlıca ayarlar:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

Opsiyonel FreeCAD override değerleri:

```env
# macOS
FREECAD_APP_DIR=/Applications/FreeCAD.app

# Windows
FREECAD_HOME='C:\Program Files\FreeCAD 1.1'
FREECAD_CMD='C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe'
FREECAD_GUI='C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe'
```

## API Uçları

| Endpoint | Metot | Açıklama |
|---|---|---|
| `/` | `GET` | Web arayüzü |
| `/api/chat` | `POST` | Mesajı işler, OpenAI'den kod üretir, FreeCADCmd ile modeli çalıştırır |
| `/api/new` | `POST` | Yeni chat oluşturur |
| `/api/chats` | `GET` | Yerel chat listesini döndürür |
| `/api/chats/<chat_id>` | `GET` | Belirli chat detayını döndürür |
| `/api/chats/clear` | `POST` | Yerel chat geçmişini temizler |
| `/api/status` | `GET` | FreeCAD, model ve çıktı klasörü durumunu döndürür |
| `/api/logs` | `GET` | Son olay loglarını döndürür |
| `/api/launch` | `POST` | FreeCAD GUI'yi başlatır |
| `/api/freecad/sync` | `POST` | Aktif FreeCAD dokümanını uygulama bağlamına senkronize eder |
| `/api/settings/openai` | `GET` | Geçerli OpenAI modelini ve API key durumunu döndürür; key değerini döndürmez |
| `/api/settings/openai` | `POST` | Geçerli oturum için OpenAI API key ve model ayarını kaydeder |
| `/api/settings/openai` | `DELETE` | Geçerli oturumun OpenAI ayarlarını temizler |

`/api/chat` örnek istek gövdesi:

```json
{
  "message": "10x10x5 cm üstü açık kutu oluştur",
  "language": "tr",
  "chat_id": "optional-chat-id",
  "generation_mode": "model_only",
  "use_manual_context": false
}
```

Geçerli `generation_mode` değerleri:

```text
model_only
technical_drawing
parametric_sketch
```

## Proje Yapısı

```text
freecad_text_to_3d/
├── app.py
├── app_logger.py
├── chat_store.py
├── config.py
├── freecad_bridge.py
├── openai_bridge.py
├── requirements.txt
├── start.sh
├── start.ps1
├── templates/
│   └── index.html
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── README.tr.md
```

Dosya rolleri:

- [app.py](app.py): Flask uygulaması ve API uçları
- [openai_bridge.py](openai_bridge.py): OpenAI mesaj kurulumu, kod çıkarma, üretim modu promptları ve otomatik onarım
- [freecad_bridge.py](freecad_bridge.py): FreeCADCmd çalıştırma, kod sarmalama/sanitize, GUI bridge ve aktif doküman sync
- [chat_store.py](chat_store.py): Yerel chat geçmişi okuma/yazma
- [app_logger.py](app_logger.py): JSONL olay logları
- [config.py](config.py): Ortam değişkenleri, FreeCAD yolları ve çıktı klasörü ayarları
- [templates/index.html](templates/index.html): Web arayüzü
- [start.sh](start.sh): macOS hızlı kurulum ve başlatma script'i
- [start.ps1](start.ps1): Windows hızlı kurulum ve başlatma script'i

## Sorun Giderme

### `ModuleNotFoundError: No module named 'flask'`

Sanal ortamı aktif edip bağımlılıkları kurun:

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### `OPENAI_API_KEY` eksik

`.env` dosyası oluşturun veya terminalde ortam değişkeni verin:

```bash
export OPENAI_API_KEY="sk-..."
```

### FreeCAD bulunamadı

macOS'te FreeCAD'in şu konumda olduğundan emin olun:

```text
/Applications/FreeCAD.app
```

Windows'ta FreeCAD'in varsayılan `Program Files` konumunda olduğundan emin olun:

```text
C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe
```

Farklı konuma kurduysanız `.env` içinde şu değerlerden birini veya birkaçını ayarlayın:

```env
FREECAD_HOME='C:\Program Files\FreeCAD 1.1'
FREECAD_CMD='C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe'
FREECAD_GUI='C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe'
```

### Port 5000 kullanımda

[config.py](config.py) içinde `FLASK_PORT` değerini değiştirin:

```python
FLASK_PORT = 5001
```

### FreeCAD GUI yenilenmiyor

Web arayüzünde `Konsol > Loglar` butonuna basın. Ayrıca şu dosyaları kontrol edin:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/open_latest_in_gui.log
~/freecad_text_to_3d_output/gui_state.json
```

Eski GUI bridge hâlâ çalışıyorsa tüm FreeCAD pencerelerini kapatıp Flask uygulamasını yeniden başlatın.

### Aktif FreeCAD senkronizasyonu çalışmıyor

Önce FreeCAD GUI içinde bir doküman açın veya oluşturun. Ardından web arayüzündeki `Aktif FreeCAD'i Al` butonuna tekrar basın.

Loglarda şu dosyalar yardımcı olur:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/gui_state.json
~/freecad_text_to_3d_output/active_freecad_context.json
```

### OpenAI kodu yarım veya hatalı döndürdü

Uygulama eksik kodu otomatik reddeder ve bazı FreeCAD hatalarında onarım dener. Hata devam ederse isteği daha net ve daha küçük parçalara bölün. Teknik çizim veya parametrik sketch gibi karmaşık isteklerde önce ana modeli, sonra detayları ayrı revizyon olarak istemek daha stabil sonuç verir.

## Geliştirme

Yerel geliştirme için:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

PR veya yayın öncesi kontrol listesi:

- Uygulama `python app.py` ile açılıyor
- API key, `.env`, log veya üretilmiş `.FCStd` dosyaları commit edilmedi
- Davranış değiştiyse README veya dokümantasyon güncellendi
- FreeCAD tarafına dokunan değişiklikler mümkünse FreeCAD ile test edildi
- UI desktop ve mobil genişliklerde kullanılabilir durumda

Katkı verilebilecek alanlar:

- FreeCAD model üretim promptlarını iyileştirme
- Mevcut model revizyon akışını daha güvenilir hale getirme
- Teknik çizim ve parametrik sketch kalitesini artırma
- FreeCAD GUI yenileme, ortalama ve görünürlük davranışını iyileştirme
- Windows kurulum algılamasını genişletme ve Linux FreeCAD path desteği ekleme
- Chat history, kod çıkarma, sanitize ve FreeCAD çalıştırma için test ekleme
- Ekran görüntüleri, demo GIF'leri veya örnek üretilmiş modeller ekleme

## Public Yayınlamadan Önce

- `.env` commit edilmemeli.
- `venv/` veya `.venv/` commit edilmemeli.
- `__pycache__/` commit edilmemeli.
- Üretilen `.FCStd` dosyaları commit edilmemeli.
- OpenAI API anahtarınızı README, kaynak kod, issue, commit veya log içine yazmayın.
- API key loglara düştüyse OpenAI dashboard üzerinden rotate edin.

## Lisans

Bu proje MIT License ile lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.
