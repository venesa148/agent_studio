# Kerangka inti Builder Agent (Agent Studio)

Kerangka logika yang menegakkan aturan: tanya sampai lengkap, tidak mengada-ada, tool lewat lifecycle, registry sebagai allowlist, egress aman.
Bukan layanan produksi: model bahasa, penyimpanan, dan HTTP produksi dipasang di sekelilingnya.

Jalankan test (Python 3.10+, hanya pustaka standar):

    python3 test_builder.py

| File | Isi |
| --- | --- |
| coverage.py | Ledger, status poin, Coverage Check, urutan pertanyaan |
| provenance.py | Validator: elemen tanpa sumber atau nilai karangan ditolak |
| egress.py | Allowlist host dan penjaga SSRF |
| tool_factory.py | Validasi spec tool, lifecycle, eksekutor HTTP aman |
| runner.py | Loop agent: registry sebagai allowlist, guardrail, limit |
| harness.py | Kasus uji dan pre-publish gate |
| test_builder.py | 27 test |
