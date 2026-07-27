# Tribo-Analist

**Desktop tools for analyzing tribometer and surface profilometer data — built for CSM Instruments tribometers and Mitutoyo contact profilometers.**

*(Türkçe açıklama aşağıdadır / Turkish description below)*

---

## 🇬🇧 English

Tribo-Analist is a set of two Python/Tkinter desktop applications for post-processing the raw output files produced during pin-on-disk / ball-on-disk wear and friction testing:

| Script | Purpose | Input files |
|---|---|---|
| `tribo_plotter.py` | Plots friction coefficient (µ) vs. sliding distance from **CSM-type tribometer** test files, with moving-average smoothing, multi-file overlay, and average-µ comparison bar charts. | `.txt` tribometer output files (tab-separated, with a "Time / Distance / µ" header) |
| `roughness_analyser.py` | Loads **Mitutoyo contact profilometer** wear-track profiles, automatically detects the wear scar, lets you manually correct the selection, and calculates cross-sectional area, wear volume, and specific wear rate (Archard-type, mm³/(N·m)). | `.xls` profilometer output files (with a `DATA` sheet) |

Both tools have a dark-themed GUI, sample/file browsers, and batch-processing features (batch wear-rate analysis across multiple samples in `roughness_analyser.py`; multi-file selection and overlay plotting in `tribo_plotter.py`).

### Key features

**`tribo_plotter.py` (friction curves)**
- Reads `.txt` files exported by the CSM tribometer, auto-detecting the file encoding (UTF-16, UTF-8, Windows-1254, Latin-1) and locating the "Distance" and "µ / friction" columns from the header row.
- Handles decimal-comma formatted numbers (Turkish/European locale).
- Moving-average filter with adjustable window size.
- Single-curve view with previous/next navigation, or overlay mode to compare several tests on one plot.
- Automatic bar chart of average µ per sample for quick comparison.
- Export/save plots.

**`roughness_analyser.py` (wear-track & roughness analysis)**
- Reads Mitutoyo `.xls` files, using the filtered profile (columns E/F) by default and the unfiltered raw profile (columns C/D) for more reliable automatic wear-track detection (the roughness filter tends to flatten the wear groove).
- Automatic wear-scar detection algorithm: finds the un-worn surface baseline, flags valleys that are statistically deeper and wider than the background roughness, and reports a confidence score. Ambiguous or undetected cases are clearly flagged so you can select the two boundary points manually.
- Groups files into "samples" (based on filename prefix before the `-` character) and displays up to 4 measurements per sample in a 2×2 grid.
- Manual point-and-click area selection with live coordinate/area readout.
- Wear-rate calculator: enter counter-ball radius, sliding distance, and load to get wear volume (mm³) and specific wear rate (mm³/(N·m)), saved per sample.
- "Scan All Samples" and "Batch Analysis" modes to process an entire dataset folder at once and export a summary report/chart.

### Requirements

```
python >= 3.9
pandas
numpy
matplotlib
xlrd        # for reading legacy .xls files used by the profilometer
tkinter     # usually included with Python; on Linux you may need python3-tk
```

Install with:
```bash
pip install pandas numpy matplotlib xlrd
```

### Usage

```bash
# Main Launcher GUI (Select between CSM Tribometer & Mitutoyo Profilometer)
python main.py

# Or launch individual tools directly:
# Friction coefficient plotting (CSM tribometer .txt files)
python tribo_plotter.py

# Wear-track / roughness analysis (Mitutoyo profilometer .xls files)
python roughness_analyser.py
```

By default each tool looks for a data subfolder next to the script (`Roughness/` for the roughness analyser) or the script's own folder (for the plotter); use the **"Select Folder"** button in the GUI to point to your own data directory.

### 💻 Standalone Windows Executable (.exe)

For Windows users who do not have Python installed, a pre-compiled standalone executable is available:
- Download `Tribo-Analist.exe` from the project's **[Releases](https://github.com/gokcemay/Tribo-Analist/releases)** page, or build it yourself with `pyinstaller Tribo-Analist.spec` (produces `dist/Tribo-Analist.exe`).
- Simply double-click `Tribo-Analist.exe` to launch the unified GUI launcher without any Python dependencies or installation steps.

### ✉️ Custom Device Integration & Software Adaptation

If your laboratory uses different brands or models of tribometers or surface profilometers (e.g., **Anton Paar, Rtec, Bruker, Taylor Hobson, KLA, Nanovea**, etc.) and you require a custom data parser, automated reporting feature, or customized user interface adapted for your specific file exports:

Please feel free to contact developer **Gökçe Mehmet AY** via email:
👉 **`gmehmetay@gmail.com`**

### ⚠️ Important: file-format dependency

These two scripts were written to match the **exact export format of our own lab instruments**:
- the CSM tribometer's tab-separated `.txt` output (specific header wording, column order, and encoding quirks), and
- the Mitutoyo contact profilometer's `.xls` export (fixed sheet name `DATA`, columns C–F reserved for raw/filtered X–Y profile pairs).

If your tribometer or profilometer produces files in a **different layout, delimiter, encoding, or column order**, the parsers (`parse_tribo_file` in `tribo_plotter.py` and `parse_excel_file` in `roughness_analyser.py`) will need to be adapted, or a new parser branch can be added, so the program can recognize and import that format as well.

### Status

Personal/lab research tooling, actively used and extended. No warranty — always sanity-check the automatic wear-track detection and area calculations against the raw profile before using the results in a report.

---

## 🇹🇷 Türkçe

Tribo-Analist, pin-on-disk / ball-on-disk aşınma ve sürtünme testlerinde elde edilen ham çıktı dosyalarını işlemek için yazılmış iki Python/Tkinter masaüstü uygulamasından oluşur:

| Dosya | Amaç | Girdi dosyaları |
|---|---|---|
| `tribo_plotter.py` | **CSM tipi tribometre** test dosyalarından sürtünme katsayısını (µ) kayma mesafesine karşı çizer; hareketli ortalama (moving average) filtresi, çoklu dosya üst üste (overlay) gösterimi ve ortalama µ karşılaştırma bar grafiği sunar. | `.txt` tribometre çıktı dosyaları (sekmeyle ayrılmış, "Time / Distance / µ" başlıklı) |
| `roughness_analyser.py` | **Mitutoyo temaslı (contact) profilometre** aşınma izi profillerini yükler, aşınma izini otomatik tespit eder, gerekirse elle düzeltme imkânı verir; kesit alanı, aşınma hacmi ve özgül aşınma oranını (Archard tipi, mm³/(N·m)) hesaplar. | `.xls` profilometre çıktı dosyaları (`DATA` sayfalı) |

Her iki program da koyu temalı bir arayüze, numune/dosya tarayıcısına ve toplu işlem (batch) özelliklerine sahiptir (`roughness_analyser.py`'de birden fazla numune üzerinde toplu aşınma oranı analizi; `tribo_plotter.py`'de çoklu dosya seçimi ve üst üste çizim).

### Öne çıkan özellikler

**`tribo_plotter.py` (sürtünme eğrileri)**
- CSM tribometrenin ürettiği `.txt` dosyalarını, dosya kodlamasını (UTF-16, UTF-8, Windows-1254, Latin-1) otomatik tanıyarak okur; başlık satırından "Distance" ve "µ / friction" sütunlarını bulur.
- Türkçe/Avrupa yerel ayarındaki ondalık virgül formatını destekler.
- Ayarlanabilir pencere boyutlu hareketli ortalama filtresi.
- Tek eğri görünümü (önceki/sonraki gezinme) veya birden fazla testi aynı grafikte karşılaştırmak için overlay modu.
- Numune başına ortalama µ değerini karşılaştıran otomatik bar grafiği.
- Grafikleri dışa aktarma/kaydetme.

**`roughness_analyser.py` (aşınma izi ve pürüzlülük analizi)**
- Mitutoyo `.xls` dosyalarını okur; varsayılan olarak filtrelenmiş profili (E/F sütunları) kullanır, otomatik aşınma izi tespiti için ise ham/filtrelenmemiş profili (C/D sütunları) tercih eder — çünkü pürüzlülük filtresi aşınma izini genellikle düzleştirir.
- Otomatik aşınma izi tespit algoritması: aşınmamış yüzey referans çizgisini bulur, arka plan pürüzlülüğüne göre istatistiksel olarak daha derin ve geniş olan vadileri işaretler, bir güven skoru (confidence) raporlar. Belirsiz veya tespit edilemeyen durumlar açıkça işaretlenir; böylece iki sınır noktasını elle seçebilirsiniz.
- Dosyaları, dosya adındaki `-` işaretinden önceki kısma göre "numune" gruplarına ayırır ve her numune için en fazla 4 ölçümü 2×2 ızgarada gösterir.
- Fare ile tıklayarak elle alan seçimi; anlık koordinat/alan gösterimi.
- Aşınma oranı hesaplayıcı: karşı bilye yarıçapı, kayma mesafesi ve yük girilerek aşınma hacmi (mm³) ve özgül aşınma oranı (mm³/(N·m)) hesaplanır, numune bazında kaydedilir.
- Tüm veri klasörünü tek seferde işlemek ve özet rapor/grafik üretmek için "Scan All Samples" ve "Batch Analysis" modları.

### Gereksinimler

```
python >= 3.9
pandas
numpy
matplotlib
xlrd        # profilometrenin ürettiği eski tip .xls dosyalarını okumak için
tkinter     # genelde Python ile birlikte gelir; Linux'ta python3-tk gerekebilir
```

Kurulum:
```bash
pip install pandas numpy matplotlib xlrd
```

### Kullanım

```bash
# Ana Başlatıcı Arayüzü (CSM Tribometre ve Mitutoyo Profilometre seçimi)
python main.py

# Veya araçları doğrudan tek tek başlatmak için:
# Sürtünme katsayısı grafiği (CSM tribometre .txt dosyaları)
python tribo_plotter.py

# Aşınma izi / pürüzlülük analizi (Mitutoyo profilometre .xls dosyaları)
python roughness_analyser.py
```

Her iki araç da varsayılan olarak script'in yanındaki bir veri klasörüne bakar (`roughness_analyser.py` için `Roughness/` klasörü, `tribo_plotter.py` için script'in bulunduğu klasör); arayüzdeki **"Klasör Seç"** butonuyla kendi veri klasörünüzü seçebilirsiniz.

### 💻 Bağımsız Windows Uygulaması (.exe)

Bilgisayarında Python kurulu olmayan Windows kullanıcıları için derlenmiş hazır `.exe` uygulaması sunulmaktadır:
- Projenin **[Releases](https://github.com/gokcemay/Tribo-Analist/releases)** sayfasından `Tribo-Analist.exe` indirilebilir, ya da `pyinstaller Tribo-Analist.spec` komutuyla kendiniz derleyebilirsiniz (`dist/Tribo-Analist.exe` üretir).
- Python veya kütüphane kurulumu gerekmeden doğrudan `Tribo-Analist.exe` dosyasına çift tıklayarak ana analiz merkezini başlatabilirsiniz.

### ✉️ Özel Cihaz Entegrasyonu & Yazılım Uyarlama

Laboratuvarınızda farklı marka veya model tribometre ya da profilometre cihazları (**Anton Paar, Rtec, Bruker, Taylor Hobson, KLA, Nanovea** vb.) kullanıyorsanız ve kendi dosya çıktılarınıza özel veri ayrıştırıcı, otomatik raporlama veya arayüz geliştirmesi isterseniz:

Geliştirici **Gökçe Mehmet AY** ile e-posta üzerinden doğrudan iletişime geçebilirsiniz:
👉 **`gmehmetay@gmail.com`**

### ⚠️ Önemli: dosya formatı bağımlılığı

Bu iki program, **kendi laboratuvarımızdaki cihazların ürettiği çıktı formatına** özel olarak yazılmıştır:
- CSM tribometrenin sekmeyle ayrılmış `.txt` çıktısı (belirli başlık ifadeleri, sütun sırası ve kodlama özellikleri), ve
- Mitutoyo temaslı profilometrenin `.xls` çıktısı (sabit `DATA` sayfa adı; ham/filtrelenmiş X–Y profil çiftleri için ayrılmış C–F sütunları).

Eğer sizin tribometreniz veya profilometreniz **farklı bir düzende, ayraçla, kodlamayla veya sütun sırasıyla** dosya üretiyorsa, ayrıştırıcı (parser) fonksiyonlarının (`tribo_plotter.py` içindeki `parse_tribo_file` ve `roughness_analyser.py` içindeki `parse_excel_file`) o formata uyarlanması ya da yeni bir ayrıştırıcı dalının eklenmesi gerekir.

### Durum

Kişisel/laboratuvar araştırma aracı olarak aktif şekilde kullanılıyor ve geliştiriliyor. Herhangi bir garanti verilmemektedir — sonuçları bir rapora dahil etmeden önce otomatik aşınma izi tespiti ve alan hesaplamalarını mutlaka ham profille karşılaştırarak kontrol edin.
