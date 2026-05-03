#!/bin/bash
# FreeCAD Text-to-3D - macOS Kurulum & Başlatma Scripti

set -e

echo ""
echo "══════════════════════════════════════════════"
echo "  FreeCAD Text-to-3D - Kurulum & Başlatma"
echo "══════════════════════════════════════════════"
echo ""

# Python kontrolü
if ! command -v python3 &>/dev/null; then
  echo "❌  python3 bulunamadı. Homebrew ile kurun: brew install python3"
  exit 1
fi

echo "✓  Python: $(python3 --version)"

# FreeCAD kontrolü
if [ -d "/Applications/FreeCAD.app" ]; then
  echo "✓  FreeCAD tespit edildi: /Applications/FreeCAD.app"
else
  echo "⚠  FreeCAD bulunamadı!"
  echo "   → https://www.freecad.org adresinden indirin"
  echo "   Yine de devam ediliyor (FreeCAD olmadan test yapabilirsiniz)…"
fi

# Venv oluştur
if [ ! -d "venv" ]; then
  echo ""
  echo "→ Sanal ortam oluşturuluyor…"
  python3 -m venv venv
fi

# Aktif et
source venv/bin/activate

# Paketleri kur
echo "→ Bağımlılıklar yükleniyor…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# API key kontrolü
if [ -z "$OPENAI_API_KEY" ]; then
  echo ""
  echo "⚠  OPENAI_API_KEY environment değişkeni ayarlanmamış!"
  echo "   Seçenek 1: export OPENAI_API_KEY='sk-...'"
  echo "   Seçenek 2: config.py dosyasını düzenleyin"
  echo ""
fi

# Çıktı dizini oluştur
mkdir -p ~/freecad_text_to_3d_output

echo ""
echo "══════════════════════════════════════════════"
echo "  Uygulama başlatılıyor → http://127.0.0.1:5000"
echo "══════════════════════════════════════════════"
echo ""

python3 app.py
