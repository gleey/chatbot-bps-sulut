# Chatbot BPS Sulawesi Utara

Proyek ini adalah simulasi Chatbot layanan Badan Pusat Statistik (BPS) Provinsi Sulawesi Utara. Chatbot ini dirancang untuk melayani pengaduan dan konsultasi, serta membantu pengguna menemukan data atau indikator statistik di website resmi BPS Sulut dengan dukungan model AI (Gemini) dan fallback berbasis rule-based (pencocokan kata kunci).

## Persyaratan (Requirements)

- Python 3.8 atau yang lebih baru
- Kunci API Google Gemini (Gemini API Key)

## Cara Instalasi dan Persiapan

1. **Clone repositori ini** (jika belum):
   ```bash
   git clone https://github.com/marchelrn/chatbot-bps.git
   cd chatbot-bps
   ```

2. **Buat Virtual Environment** (Opsional tapi sangat disarankan):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Untuk Linux/Mac
   # atau
   # .venv\Scripts\activate   # Untuk Windows
   ```

3. **Install Dependensi**:
   Jalankan perintah berikut untuk menginstal semua library yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi Environment Variables**:
   Buat sebuah file bernama `.env` di direktori utama proyek (jika belum ada) atau salin dari template jika tersedia. Isi file `.env` dengan variabel berikut:

   ```ini
   # Wajib diisi untuk menjalankan mode AI
   GEMINI_API_KEY=masukkan_api_key_gemini_anda_di_sini
   
   # Konfigurasi Provider WhatsApp ("meta" atau "fonnte") - opsional jika hanya simulasi terminal
   WHATSAPP_PROVIDER=meta
   
   # Konfigurasi Meta Cloud API (Opsional)
   META_ACCESS_TOKEN=token_anda
   META_PHONE_NUMBER_ID=id_nomor_anda
   META_VERIFY_TOKEN=token_verifikasi_anda
   
   # Konfigurasi Fonnte API (Opsional)
   FONNTE_TOKEN=token_fonnte_anda
   ```

## Cara Menjalankan Aplikasi

### 1. Simulasi Terminal
Untuk menguji dan menjalankan alur percakapan chatbot langsung melalui terminal (tanpa perlu terhubung ke WhatsApp asli):

```bash
python main.py
```

Saat aplikasi dijalankan, ia akan mengecek koneksi ke Google Gemini API:
- Jika koneksi sukses, mode **AI** akan otomatis digunakan.
- Jika API tidak tersedia atau tidak diatur, Anda dapat memilih untuk menggunakan mode **OFFLINE (Rule-Based)** yang menggunakan pencocokan kata kunci (fuzzy matching) ke link kategori data BPS.

**Perintah khusus di terminal simulasi:**
- `keluar`: Menghentikan simulasi.
- `reset`: Mengulang percakapan dan menghapus sesi pengguna.
- `info`: Menampilkan informasi session saat ini (nama, instansi, step, dll).
- `online`: Mencoba kembali menghubungkan chatbot ke API Gemini.

### 2. Mode Webhook (WhatsApp)
Proyek ini juga mendukung Flask untuk berjalan sebagai webhook WhatsApp (contohnya `wa_webhook.py`). Jika Anda ingin menjalankannya sebagai server API atau webhook:

```bash
# Menjalankan webhook menggunakan Flask/Python biasa
python wa_webhook.py
```
*(Pastikan port/alamat disesuaikan, atau gunakan layanan seperti ngrok/localtunnel untuk menghubungkannya dengan Webhook API eksternal).*
