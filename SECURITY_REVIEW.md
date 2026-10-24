# WontNote - Yerel güvenlik incelemesi

Tarih: 21 Ekim 2026

## Kapsam

Python şifreleme çekirdeği, yerel kasa depolama, PyWebView API köprüsü ve HTML not editörü incelendi. Bütün saldırı denemeleri test dizinindeki geçici kasalara uygulandı; gerçek kullanıcı kasası okunmadı, sıfırlanmadı ve parola tahmini yapılmadı.

## Doğrulanan ve düzeltilen sorunlar

1. **Kilitli kasanın üzerine şifresiz yazma:** API doğrudan çağrılınca `create_vault` mevcut kasayı değiştiriyordu. İlk regresyon testi bu davranışı yeniden üretti. Mevcut kasa kontrolü ve süreçler arasında da üzerine yazmayı engelleyen atomik, özel dosya oluşturma eklendi.
2. **Şifresiz kasa silme:** `reset_vault` yalnızca arayüzdeki onaya dayanıyordu. İlk regresyon testi kilitli test kasasını silebildi. Artık Python tarafında mevcut parola doğrulaması ve açık onay gerekir. Yanlış parola hiçbir dosyayı silmez.
3. **Sınırsız çevrimiçi deneme:** Parola ve kurtarma girişimleri ortak, süreç içi sınıra alındı. Beş başarısız denemeden sonra 5 saniyeden başlayan ve 60 saniyeye kadar artan bekleme uygulanır. Kimlik doğrulama ve kilitleme aynı kilitle sıralanır.
4. **Değiştirilmiş başlıkla kaynak tüketimi:** Dosyadaki Argon2 parametrelerinin 1 GiB bellek talep etmesi, hesaplama başlamadan köprü katmanında reddedilir. Uygulamanın normal 64 MiB / 3 tur parametreleri değişmedi.
5. **Kilit sonrası gizli arayüz verileri:** Not metni ve başlığı yanında klasörler, arama, kurtarma anahtarı, parola alanları ve sayaçlar da DOM'dan temizlenir. Başarılı giriş sonrası parola alanı temizlenir. Kaydetme/kilitleme sırasında çalışma alanı geçici olarak etkileşime kapatılır.
6. **Not içeriği ve dış kaynaklar:** HTML temizleyici script, event niteliği, iframe ve dış bağlantı öğelerini çıkarır. Sürükleyip bırakma ve yapıştırma düz metin kabul eder. Uzak font istekleri kaldırıldı. CSP nesne ve çerçeveleri engeller. PyWebView köprüsünün `new Function` ve `eval` gereksinimi nedeniyle `unsafe-eval`, mevcut HTML olayları nedeniyle `unsafe-inline` tutulur; CSP tek başına XSS koruması sayılmaz.

Tercihler, yalnızca izin verilen anahtar/değerleri kabul eden ayrı bir JSON dosyasında kalıcı tutulur. Parola ve notlar bu dosyaya yazılamaz. WebView özel modu korunur; tarayıcı oturum verilerini kalıcılaştırarak tercih saklama yoluna gidilmez.

## Denenen erişim yolları

- Boş ve yanlış parola, SQL benzeri parola metni, geçersiz kurtarma anahtarı.
- Kilitliyken not okuma, oluşturma, düzenleme, silme ve kurtarma anahtarı yenileme.
- Şifreli bloğun son baytını değiştirme.
- Mevcut kasayı yeni bir parola ile değiştirme ve doğrulamasız sıfırlama.
- Giriş ve kilitleme işlemlerini eşzamanlı çalıştırma.
- Dosya oluşturma yarışında mevcut hedefin üzerine yazma.
- Sahte not alanları ve yüksek kaynak tüketen başlık.

Yanlış parola/anahtar veya değiştirilmiş şifreli veriyle notların çözülmesi sağlanamadı. Bu, sınırlı regresyon testlerinin sonucudur; kapsamlı bağımsız penetrasyon testi veya kırılmazlık garantisi değildir.

## Sınırlar

Çevrimiçi bekleme uygulama yeniden başlatıldığında sıfırlanır; kasanın kopyası üzerinde çevrimdışı parola tahminini engellemez. Güçlü parola gereklidir. Geçerli kurtarma anahtarıyla erişim tasarlanan davranıştır. Açık oturumdaki veriler, işletim sistemi yöneticisi, bellek dökümü, zararlı yazılım veya fiziksel dosya silmeye karşı korunamaz. Python'da belleği sıfırlamak en iyi çaba düzeyindedir. Otomatik kilitleme, bekleyen notu kaydetme başarısızsa veri kaybını önlemek için kilitlemeyi tamamlamaz ve hata gösterir. Otomatik kilitleme ve küçültme olayı gerçek masaüstü ortamında ayrıca denenmelidir.

## Doğrulama

`tests/test_security_audit.py` yalıtılmış saldırı regresyonlarını, `tests/test_gui_api.py` kilit ve kalıcılık davranışlarını, `tests/test_frontend.cjs` tercih/kısayol/arayüz temizliği akışlarını kapsar. Tam test sonucu uygulama teslim mesajında raporlanır.
