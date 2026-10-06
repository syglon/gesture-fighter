# 🖐️ Gesture Fighter — ME461

Kamera el hareketlerinizi algılar (MediaPipe Hand Landmarker), siz de **OVERLORD-461** adlı boss'la savaşırsınız.

| Hareket | Oyundaki karşılığı |
|---|---|
| ✊ Yumruk | **PUNCH**: hızlı, enerji harcamaz, az hasar |
| 🖐️ Açık el | **SHIELD**: mermileri/lazerleri engeller. Mermi çarpmadan **hemen önce** açarsan **PARRY** olur ve mermi boss'a geri döner |
| ☝️ İşaret parmağı | **FIRE**: ateş topu, 18 enerji |
| ✌️ İki parmak | **SPECIAL**: altın bar doluyken dev ışın (elinle yönlendirebilirsin) |
| Eli yukarı/aşağı | Karakteri hareket ettirir (kaçmak ve nişan almak için) |

Hareketi **yeni yaptığında** saldırı hemen çıkar; hareketi tutarsan daha yavaş bir hızla tekrarlar.
Yani hızlı yumruk için eli açıp kapamak (✊→🖐️→✊) en etkili yol.

## ⚔️ İki kişilik VERSUS

Menüde **✌️ iki parmağı 1 sn tut** (veya `V` tuşu, ya da `--versus` ile başlat). İki oyuncu karşı karşıya dövüşür:

- Kamera ikiye bölünür: **görüntünün sol yarısındaki el P1 (solda, mavi), sağ yarısındaki el P2 (sağda, pembe)**.
  Yan yana durun, herkes kendi tarafında elini göstersin. Eli yukarı/aşağı oynatmak karakteri hareket ettirir.
- Aynı 4 hareket: ✊ yumruk, 🖐️ kalkan (tam zamanında açarsan **PARRY** — mermi rakibe geri döner), ☝️ ateş topu, ✌️ özel ışın.
- Karşılaşan mermiler çarpışır: ateş topu yumruğu yener, parry ile dönen mermi ikisini de yener.
- Özel ışın rakibe kilitlenmez — elinle ışını rakibin hizasına getirmen gerekir. Kalkan ışını büyük ölçüde durdurur ama enerjiyi hızla eritir.
- Her raunt 60 sn, can 150. **3 rauntta 2 kazanan** maçı alır. Süre biterse canı fazla olan raundu alır.
- Sonda iki oyuncunun istatistikleri yan yana gösterilir (hasar, isabet, parry, kombo, özel).

Klavye (kamerasız test): **P1** `1 2 3 4` (yumruk, kalkan, ateş, özel) + `W/S` — **P2** `7 8 9 0` + `↑/↓`.

## Kurulum

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python webcam_game.py
```

El modeli (`models/hand_landmarker.task`, ~7.5 MB) yoksa ilk açılışta otomatik indirilir.

### Seçenekler

```bash
.venv/bin/python webcam_game.py --difficulty easy     # easy | normal | hard
.venv/bin/python webcam_game.py --camera 1            # başka kamera
.venv/bin/python webcam_game.py --fullscreen
.venv/bin/python webcam_game.py --keyboard            # kamerasız test (1-4 hareketler, W/S hareket)
.venv/bin/python webcam_game.py --mute
.venv/bin/python webcam_game.py --versus            # doğrudan iki kişilik maç
```

Oyun içi: `ESC/P` duraklat · `F11` tam ekran · `F1` debug (FPS, ham hareket, parmak durumları) · `M` ses.
Kamera açılamazsa oyun otomatik olarak klavye moduna geçer.

## Boss

Boss'un 3 fazı var (can barındaki çizgiler). Her fazda daha hızlı ve yeni saldırılar ekleniyor:

1. **Faz 1:** tekli mermi, yelpaze atış, lazer (kırmızı uyarı şeridinden çık ya da kalkan aç)
2. **Faz 2:** seri atış, güdümlü füzeler (yumruk/ateşle vurulabilir), daha sık lazer
3. **Faz 3 — OVERDRIVE:** çift lazer, boşluklu mermi duvarı (boşluğa kaç!), oyuncuyu takip eder

Kombo yaptıkça (2.2 sn içinde art arda isabet) hasar %50'ye kadar artar. Sonunda süre/can/isabet istatistikleri ve S/A/B/C derecesi gösterilir.

## Kod yapısı

```
webcam_game.py              giriş noktası (argümanlar)
gesture_fighter/
  config.py                 TÜM denge ayarları (hasar, can, hız, zorluk) — buradan oynayın
  hand_tracker.py           kamera + MediaPipe, ayrı thread'de (oyun 60 FPS, algılama ~20-30 FPS)
  gestures.py               21 el noktasından hareket sınıflandırma + titreme filtresi
  controls.py               giriş soyutlaması: kamera eli / klavye / ikisi birden
  entities.py               Fighter (oyuncu), Boss, mermiler, lazerler, özel ışın
  game.py                   durum makinesi, çarpışmalar, arayüz
  fx.py, draw.py, sound.py  partiküller, çizim yardımcıları, sentezlenmiş sesler (dosya yok)
```

**Hareket algılama nasıl çalışıyor?** Her parmak (işaret, orta, yüzük, serçe) için
bilek→parmak ucu / bilek→orta eklem mesafe oranı ve eklemdeki bükülme açısı hesaplanıyor.
Bu iki ölçüt elin dönmesinden ve kameraya uzaklığından bağımsız. Açık parmak sayısı + hangileri açık olduğu
hareketi belirliyor. Başparmak en gürültülü parmak olduğu için kullanılmıyor. Son 4 karenin
en az 3'ünde aynı hareket görülürse kararlı kabul ediliyor (titreme önleme).

## İpuçları (demo için)

- Kameranın aydınlık bir ortamda olması algılamayı çok iyileştirir; arka ışıktan kaçının.
- Eli kameraya ~50-80 cm uzaklıkta, avuç kameraya dönük tutun.
- Hocaya gösterirken `--difficulty easy` ile başlayıp sonra `normal`'e geçebilirsiniz.
- `F1` ile debug panelini açıp hangi parmakların algılandığını (`fingers 1100` gibi) gösterebilirsiniz.
