import ast
import re
from openai import OpenAI
from config import Config

SYSTEM_PROMPT = """
Sen bir FreeCAD 3D modelleme uzmanısın. Kullanıcı Türkçe veya İngilizce olarak 3D model tarifler,
sen de bunu FreeCAD Python API kodu olarak üretirsin.

KURALLAR:
1. Her yanıtta iki bölüm olacak:
   - Kısa Türkçe açıklama (ne yapıldığı)
   - Tam çalışır FreeCAD Python kodu (```python ... ``` bloğu içinde)
   - Kullanıcı önceki modelle ilgili takip isteği yazarsa, önceki model kodunu
     koruyup istenen değişikliği ekleyen TAM GÜNCEL kodu üret. Sadece ek kod
     veya yama verme.

2. FreeCAD kodu doğrudan 3D shape üretmeli. Sketcher/PartDesign kullanma;
   ana yöntem `Part` API'si ile solid oluşturmak ve gerekirse boolean işlemler
   uygulamak olmalı.

3. FreeCAD kodu şu şablonu takip etmeli:
   ```python
   import FreeCAD, Part
   doc = FreeCAD.newDocument("Model")
   
   # ... model kodu buraya ...
   
   doc.recompute()
   ```

4. Ölçüler mm cinsindendir (kullanıcı cm verirse *10 yap)
5. Birden fazla nesne gerekirse hepsini aynı doc'a ekle
6. Kod FreeCADCmd/headless ortamda çalışacak; FreeCADGui, FreeCAD.Gui,
   activeDocument().activeView(), fitAll(), sendMsgToActiveView() kullanma.
   Model kaydedildikten sonra uygulama dosyayı FreeCAD GUI'de açacak.
7. Kod temiz, yorumlu ve tam çalışır olsun
8. Hata yapma — FreeCAD API'yi doğru kullan:
   - Part.makeBox(l,w,h)
   - Part.makeCylinder(r,h)
   - Part.makeSphere(r)
   - Part.makeCone(r1,r2,h)
   - Boolean: shape.cut(other), shape.fuse(other)
   - doc.addObject("Part::Feature","Name").Shape = shape
   - Konumlandırma: shape.translate(FreeCAD.Vector(x, y, z))
   - Döndürme: shape.rotate(center, axis, angle)
9. Python kodu sözdizimi hatasız olmalı:
   - for/if/try bloklarında 4 boşluk girinti kullan
   - Değişken adlarında Türkçe karakter kullanma; ASCII isimler kullan
   - Kodun sonunda her oluşturulan shape'i doc.addObject ile dokümana ekle
   - En sonda doc.recompute() çağır
   - Yanıt kodu sadece değişken tanımı veya açıklama seviyesinde kalmamalı.
     En az bir gerçek `doc.addObject(...)` çağrısı içermeli.

10. Kullanıcının istediği görsel detaylar FreeCAD'de açıkça görülebilir olmalı:
   - Pencere/cam istendiğinde bunları ayrı `Part::Feature` objeleri olarak ekle.
     Obje adlarında `Window`, `Windshield` veya `Glass` kelimelerini kullan.
   - Pencere, kapı, far, kulp, vida, logo gibi detayları gövde ile aynı yüzeye
     tam çakıştırma; z-fighting olmaması için 0.3-1.0 mm dışa taşı veya ayrı
     ince panel olarak modelle.
   - Detayları sadece açıklama metninde söyleme; mutlaka koda ve dokümana ekle.
   - Önceki modeldeki ana geometriyi koru, yeni istenen detayı da görünür şekilde
     ekleyen tam güncel modeli üret.

ÖNEMLİ: Kodu ```python ile başlat, ``` ile bitir. Başka kod bloğu kullanma.
Kullanıcı "do it", "uygula", "tamam", "yap" gibi onay cümleleri yazsa bile
önceki isteğe göre TAM GÜNCEL FreeCAD Python kodunu yeniden üret. Sadece açıklama
yazıp kodu atlama.
"""

LANGUAGE_PROMPTS = {
    "tr": "Açıklama metnini Türkçe yaz. FreeCAD Python kodu aynı kurallara uysun.",
    "en": "Write the explanation in English. Keep the FreeCAD Python code valid and follow the same rules.",
}

class OpenAIBridge:
    def __init__(self, config: Config):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model  = config.OPENAI_MODEL
        self.max_completion_tokens = 8000

    def chat(self, history: list, user_message: str, language: str = "tr") -> tuple[str, str]:
        """
        history: [{"role": "user"/"assistant", "content": "..."}]
        returns: (açıklama_metni, freecad_python_kodu)
        """
        language = language if language in LANGUAGE_PROMPTS else "tr"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": LANGUAGE_PROMPTS[language]},
        ]
        messages += history
        if history:
            messages.append({
                "role": "system",
                "content": (
                    "Bu konuşmada önceki bir FreeCAD modeli var. Kullanıcının "
                    "yeni isteğini mevcut modeli revize etme isteği olarak yorumla. "
                    "Önceki modelin ana geometrisini koru ve yanıtında çalıştırılabilir "
                    "tam güncel Python kodunu tek parça halinde ver."
                ),
            })
        messages.append({"role": "user", "content": user_message})

        request_args = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            self._token_limit_param(): self.max_completion_tokens,
        }

        full_text = self._complete(request_args)
        code = self._extract_code(full_text)
        if not self._is_complete_freecad_code(code):
            retry_messages = messages + [
                {"role": "assistant", "content": full_text},
                {
                    "role": "user",
                    "content": (
                        "Your previous answer did not include a complete runnable FreeCAD script. "
                        "Return the complete updated FreeCAD Python script now. It must include "
                        "doc.addObject(...) calls for the main model and every requested visible "
                        "detail, and it must end with doc.recompute(). Include exactly one "
                        "```python ... ``` block."
                    ),
                },
            ]
            retry_args = {**request_args, "messages": retry_messages}
            full_text = self._complete(retry_args)
            code = self._extract_code(full_text)
            if not self._is_complete_freecad_code(code):
                raise RuntimeError(
                    "OpenAI yanıtı tam çalıştırılabilir FreeCAD kodu içermedi. "
                    "Lütfen isteği biraz daha açık yazın veya tekrar deneyin."
                )
        
        # Açıklama metninden kod bloğunu çıkar
        description = re.sub(r"```python.*?```", "", full_text, flags=re.DOTALL).strip()
        description = re.sub(r"```.*?```", "", description, flags=re.DOTALL).strip()
        
        return description, code

    def _complete(self, request_args: dict) -> str:
        response = self.client.chat.completions.create(**request_args)
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError(
                "OpenAI yanıtı token limitine takıldı ve kod yarım kaldı. "
                "Lütfen isteği daha kısa parçalara bölün veya token limitini artırın."
            )
        return choice.message.content.strip()

    def _token_limit_param(self) -> str:
        model = self.model.lower()
        if model.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    def _extract_code(self, text: str) -> str:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```python\s*(.*)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Alternatif: sadece ``` bloğu
        match = re.search(r"```\s*(import FreeCAD.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _is_complete_freecad_code(self, code: str) -> bool:
        if not code:
            return False
        try:
            ast_tree = ast.parse(code)
        except SyntaxError:
            return False

        has_add_object = False
        has_recompute = False
        for node in ast.walk(ast_tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr == "addObject":
                    has_add_object = True
                if func.attr == "recompute":
                    has_recompute = True
        return has_add_object and has_recompute
