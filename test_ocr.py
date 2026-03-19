"""
test_ocr.py — Test validasi lokal tanpa perlu API call

Jalankan: python test_ocr.py
"""

import json
from ocr import validasi_nota, validasi_item

def test_kalkulasi_benar():
    """Item dengan kalkulasi benar → status ok"""
    data = {
        "tipe": "putih",
        "kas": "keluar",
        "nama": "Bakri",
        "tanggal": "15 Maret 2026",
        "no_nota": "001",
        "items": [
            {
                "no": 1,
                "jenis_kode": "T",
                "jenis_nama": "Tiger",
                "berat": 2.7,
                "ukuran": 30,
                "harga": 232000,
                "jumlah_nota": 626400,
                "jumlah_hitung": 626400,
                "status": "ok"
            }
        ],
        "es_balok": None,
        "subtotal_nota": 626400,
        "subtotal_hitung": 626400,
        "total_nota": 626400,
        "total_hitung": 626400,
        "total_status": "ok",
        "selisih": 0,
        "flags": [],
        "side_notes": ""
    }
    result = validasi_nota(data)
    # Harga 232000 × 2.7 = 626400 → ok
    assert result["total_status"] == "ok", f"Harusnya ok, dapat: {result['total_status']}"
    assert result["items"][0]["status"] == "ok"
    print("✓ test_kalkulasi_benar")

def test_kalkulasi_salah():
    """Jumlah di nota tidak cocok dengan hitung → flag mismatch"""
    data = {
        "tipe": "putih",
        "kas": "keluar",
        "nama": "Dahlan",
        "tanggal": "15 Maret 2026",
        "no_nota": "002",
        "items": [
            {
                "no": 1,
                "jenis_kode": "T",
                "jenis_nama": "Tiger",
                "berat": 3.0,
                "ukuran": 25,
                "harga": 250000,
                "jumlah_nota": 800000,   # Seharusnya 750000
                "jumlah_hitung": 750000,
                "status": "ok"
            }
        ],
        "es_balok": None,
        "subtotal_nota": 800000,
        "subtotal_hitung": 750000,
        "total_nota": 800000,
        "total_hitung": 750000,
        "total_status": "ok",
        "selisih": 0,
        "flags": [],
        "side_notes": ""
    }
    result = validasi_nota(data)
    assert result["items"][0]["status"] == "mismatch"
    assert len(result["flags"]) > 0
    print("✓ test_kalkulasi_salah — flag mismatch terdeteksi")
    print(f"  Flags: {result['flags']}")

def test_ukuran_di_luar_range():
    """Ukuran Tiger > 70 → harus di-flag"""
    item = {
        "no": 1,
        "jenis_kode": "T",
        "jenis_nama": "Tiger",
        "berat": 5.0,
        "ukuran": 80,          # Di luar range Tiger (20–70)
        "harga": 180000,
        "jumlah_nota": 900000,
        "jumlah_hitung": 900000,
        "status": "ok"
    }
    flags = validasi_item(item)
    assert any("luar range" in f for f in flags), f"Harusnya ada flag ukuran, dapat: {flags}"
    print("✓ test_ukuran_di_luar_range")
    print(f"  Flags: {flags}")

def test_es_balok():
    """Es balok harus dikurangi dari subtotal"""
    data = {
        "tipe": "putih",
        "kas": "keluar",
        "nama": "Petambak A",
        "tanggal": "15 Maret 2026",
        "no_nota": "003",
        "items": [
            {
                "no": 1,
                "jenis_kode": "W",
                "jenis_nama": "White",
                "berat": 10.0,
                "ukuran": None,
                "harga": 100000,
                "jumlah_nota": 1000000,
                "jumlah_hitung": 1000000,
                "status": "ok"
            }
        ],
        "es_balok": 50000,
        "subtotal_nota": 1000000,
        "subtotal_hitung": 1000000,
        "total_nota": 950000,
        "total_hitung": 950000,
        "total_status": "ok",
        "selisih": 0,
        "flags": [],
        "side_notes": ""
    }
    result = validasi_nota(data)
    assert result["total_hitung"] == 950000, f"Total hitung harusnya 950000, dapat: {result['total_hitung']}"
    assert result["total_status"] == "ok"
    print("✓ test_es_balok — es balok terpotong dengan benar")

def test_jenis_tidak_dikenal():
    """Kode jenis tidak valid → flag"""
    item = {
        "no": 1,
        "jenis_kode": "XYZ",
        "jenis_nama": "Unknown",
        "berat": 2.0,
        "ukuran": None,
        "harga": 100000,
        "jumlah_nota": 200000,
        "jumlah_hitung": 200000,
        "status": "ok"
    }
    flags = validasi_item(item)
    assert any("tidak dikenal" in f for f in flags)
    print("✓ test_jenis_tidak_dikenal")

if __name__ == "__main__":
    print("=" * 50)
    print("HAR OCR — Unit Test Validasi Lokal")
    print("=" * 50)
    test_kalkulasi_benar()
    test_kalkulasi_salah()
    test_ukuran_di_luar_range()
    test_es_balok()
    test_jenis_tidak_dikenal()
    print("=" * 50)
    print("✓ Semua test lulus")
