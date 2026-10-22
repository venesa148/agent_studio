// Savoria Bistro - Frontend Application Logic

let currentMenuCategory = 'Semua';
let currentSearchTerm = '';
let currentSort = '';
let restaurantInfoData = null;

document.addEventListener('DOMContentLoaded', () => {
    // Set minimal tanggal reservasi adalah hari ini
    const todayStr = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('resDate');
    if (dateInput) {
        dateInput.min = todayStr;
        dateInput.value = todayStr;
    }

    // Inisialisasi data
    loadRestaurantInfo();
    loadCategories();
    loadMenu();

    // Event listener pencarian & sort
    const searchInput = document.getElementById('menuSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            currentSearchTerm = e.target.value.trim();
            loadMenu();
        }, 300));
    }

    const sortSelect = document.getElementById('menuSort');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            currentSort = e.target.value;
            loadMenu();
        });
    }

    // Form reservasi submit
    const resForm = document.getElementById('reservationForm');
    if (resForm) {
        resForm.addEventListener('submit', handleReservationSubmit);
    }

    // Cek reservasi form submit
    const trackForm = document.getElementById('trackForm');
    if (trackForm) {
        trackForm.addEventListener('submit', handleTrackReservation);
    }

    // Form tambah menu admin
    const addMenuForm = document.getElementById('addMenuForm');
    if (addMenuForm) {
        addMenuForm.addEventListener('submit', handleAddMenuItem);
    }

    // Form update info resto admin
    const updateInfoForm = document.getElementById('updateInfoForm');
    if (updateInfoForm) {
        updateInfoForm.addEventListener('submit', handleUpdateRestaurantInfo);
    }
});

// Helper debounce
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Format Rupiah
function formatRupiah(amount) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(amount);
}

// ==================== RESTAURANT INFO & HOURS ====================

async function loadRestaurantInfo() {
    try {
        const res = await fetch('/api/info');
        const json = await res.json();
        if (!json.success) return;

        const info = json.data;
        const statusNow = json.status_now;
        const hours = json.operating_hours;
        restaurantInfoData = info;

        // Update Header & Badge Buka/Tutup
        const liveBadge = document.getElementById('liveStatusBadge');
        if (liveBadge) {
            if (statusNow.is_open) {
                liveBadge.className = 'inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300';
                liveBadge.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-emerald-500 pulse-open"></span> BUKA SEKARANG (${statusNow.today_hours})`;
            } else {
                liveBadge.className = 'inline-flex items-center gap-2 px-3 py-1 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 border border-rose-300';
                liveBadge.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span> SEDANG TUTUP (Buka: ${statusNow.today_hours})`;
            }
        }

        // Update Hero Texts
        document.querySelectorAll('.resto-name').forEach(el => el.textContent = info.name);
        document.querySelectorAll('.resto-tagline').forEach(el => el.textContent = info.tagline);
        document.querySelectorAll('.resto-address').forEach(el => el.textContent = info.address);
        document.querySelectorAll('.resto-phone').forEach(el => el.textContent = info.phone);
        document.querySelectorAll('.resto-wa').forEach(el => {
            el.textContent = `+${info.whatsapp}`;
            el.href = `https://wa.me/${info.whatsapp}?text=Halo%20${encodeURIComponent(info.name)}%2C%20saya%20ingin%20tanya%20reservasi`;
        });
        document.querySelectorAll('.resto-instagram').forEach(el => el.textContent = info.instagram);

        // Update Tabel Jam Operasional
        const hoursTableBody = document.getElementById('operatingHoursBody');
        if (hoursTableBody && hours) {
            const todayIndex = new Date().getDay(); // 0 is Sunday in JS
            // Map JS Sunday(0)..Saturday(6) to Monday(0)..Sunday(6)
            const todayDayOfWeek = todayIndex === 0 ? 6 : todayIndex - 1;

            hoursTableBody.innerHTML = hours.map(h => {
                const isToday = h.day_of_week === todayDayOfWeek;
                return `
                    <tr class="${isToday ? 'bg-amber-50 font-semibold text-amber-900 border-l-4 border-amber-600' : 'border-b border-gray-100 text-gray-700'}">
                        <td class="py-2.5 px-3">
                            ${h.day_name} ${isToday ? '<span class="ml-1 text-[11px] px-1.5 py-0.5 bg-amber-200 text-amber-900 rounded font-bold">HARI INI</span>' : ''}
                        </td>
                        <td class="py-2.5 px-3 text-right">
                            ${h.is_closed ? '<span class="text-rose-600 font-medium">Tutup</span>' : `${h.open_time} - ${h.close_time} WIB`}
                        </td>
                    </tr>
                `;
            }).join('');
        }

        // Update Maps Embed
        const mapsIframe = document.getElementById('mapsIframe');
        if (mapsIframe && info.maps_embed_url) {
            mapsIframe.src = info.maps_embed_url;
        }

        // Isi form admin profil resto jika terbuka
        fillAdminInfoForm(info);

    } catch (err) {
        console.error('Gagal mengambil info resto:', err);
    }
}

// ==================== MENU & CATEGORIES ====================

async function loadCategories() {
    try {
        const res = await fetch('/api/categories');
        const json = await res.json();
        if (!json.success) return;

        const container = document.getElementById('categoryTabs');
        if (!container) return;

        const categories = ['Semua', ...json.data];
        container.innerHTML = categories.map(cat => `
            <button 
                onclick="filterCategory('${cat}')"
                class="category-btn px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    cat === currentMenuCategory
                        ? 'bg-amber-600 text-white shadow-md'
                        : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'
                }"
                data-category="${cat}">
                ${cat}
            </button>
        `).join('');

        // Isi dropdown kategori pada form tambah menu admin
        const adminCatSelect = document.getElementById('newMenuCategory');
        if (adminCatSelect) {
            adminCatSelect.innerHTML = json.data.map(c => `<option value="${c}">${c}</option>`).join('');
        }

    } catch (err) {
        console.error('Gagal memuat kategori:', err);
    }
}

function filterCategory(cat) {
    currentMenuCategory = cat;
    // Update button styling
    document.querySelectorAll('.category-btn').forEach(btn => {
        if (btn.dataset.category === cat) {
            btn.className = 'category-btn px-4 py-2 rounded-full text-sm font-medium transition-all bg-amber-600 text-white shadow-md';
        } else {
            btn.className = 'category-btn px-4 py-2 rounded-full text-sm font-medium transition-all bg-white text-gray-700 hover:bg-gray-100 border border-gray-200';
        }
    });
    loadMenu();
}

async function loadMenu() {
    const grid = document.getElementById('menuGrid');
    if (!grid) return;

    grid.innerHTML = `
        <div class="col-span-full py-16 text-center text-gray-500">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600 mb-3"></div>
            <p>Memuat menu lezat...</p>
        </div>
    `;

    try {
        let url = `/api/menu?category=${encodeURIComponent(currentMenuCategory)}`;
        if (currentSearchTerm) {
            url += `&search=${encodeURIComponent(currentSearchTerm)}`;
        }
        if (currentSort) {
            url += `&sort=${encodeURIComponent(currentSort)}`;
        }

        const res = await fetch(url);
        const json = await res.json();

        if (!json.success || json.data.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full py-16 text-center text-gray-500 bg-white rounded-2xl border border-dashed border-gray-300">
                    <span class="text-4xl mb-3 block">🍽️</span>
                    <p class="text-lg font-medium text-gray-800">Menu tidak ditemukan</p>
                    <p class="text-sm text-gray-500 mt-1">Coba kata kunci lain atau pilih kategori berbeda.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = json.data.map(item => {
            const spicyIcons = item.spicy_level > 0 ? '🌶️'.repeat(item.spicy_level) : '';
            const isAvailable = item.is_available === 1;

            return `
                <div class="food-card bg-white rounded-2xl overflow-hidden border border-gray-100 flex flex-col justify-between ${!isAvailable ? 'opacity-70 grayscale-[30%]' : ''}">
                    <div>
                        <div class="relative h-48 w-full overflow-hidden bg-gray-100">
                            <img 
                                src="${item.image_url || 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80'}" 
                                alt="${item.name}" 
                                class="w-full h-full object-cover transition-transform duration-500 hover:scale-105"
                                onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80'"
                            />
                            ${item.is_favorite ? `
                                <span class="absolute top-3 left-3 bg-amber-500 text-white text-[11px] font-bold px-2.5 py-1 rounded-full shadow-md flex items-center gap-1">
                                    ⭐ Favorit
                                </span>
                            ` : ''}
                            ${!isAvailable ? `
                                <span class="absolute top-3 right-3 bg-rose-600 text-white text-[11px] font-bold px-2.5 py-1 rounded-full shadow-md">
                                    Stok Habis
                                </span>
                            ` : ''}
                        </div>
                        <div class="p-5">
                            <div class="flex items-center justify-between text-xs text-amber-700 font-semibold mb-1">
                                <span>${item.category}</span>
                                <span>${spicyIcons}</span>
                            </div>
                            <h3 class="text-base font-bold text-gray-900 mb-1.5 leading-snug">${item.name}</h3>
                            <p class="text-xs text-gray-500 line-clamp-2 mb-3">${item.description || '-'}</p>
                            ${item.tags ? `
                                <div class="flex flex-wrap gap-1 mb-2">
                                    ${item.tags.split(',').map(t => `<span class="text-[10px] bg-amber-50 text-amber-800 px-2 py-0.5 rounded">${t.trim()}</span>`).join('')}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="px-5 pb-5 pt-0 flex items-center justify-between border-t border-gray-50 mt-auto">
                        <div>
                            <span class="text-[11px] text-gray-400 block font-medium">Harga</span>
                            <span class="text-base font-extrabold text-amber-600">${formatRupiah(item.price)}</span>
                        </div>
                        <a href="#reservasi" class="px-3 py-1.5 bg-amber-50 text-amber-700 hover:bg-amber-600 hover:text-white rounded-lg text-xs font-semibold transition-all">
                            Reservasi Meja
                        </a>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.error('Gagal memuat menu:', err);
        grid.innerHTML = '<p class="col-span-full text-center text-rose-500">Terjadi kesalahan saat memuat menu.</p>';
    }
}

// ==================== RESERVASI MEJA ====================

async function handleReservationSubmit(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('btnSubmitReservation');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
        <span class="inline-block animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></span>
        Memproses Reservasi...
    `;

    const payload = {
        customer_name: document.getElementById('resName').value.trim(),
        phone: document.getElementById('resPhone').value.trim(),
        email: document.getElementById('resEmail').value.trim() || null,
        reservation_date: document.getElementById('resDate').value,
        reservation_time: document.getElementById('resTime').value,
        guest_count: parseInt(document.getElementById('resGuests').value, 10),
        table_area: document.getElementById('resArea').value,
        special_notes: document.getElementById('resNotes').value.trim() || null
    };

    try {
        const res = await fetch('/api/reservations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const json = await res.json();

        if (!res.ok || !json.success) {
            throw new Error(json.detail || 'Gagal membuat reservasi.');
        }

        // Tampilkan modal tiket sukses
        showTicketModal(json.data);

        // Update database inspector & stats
        loadDbStatusInspector();
        loadAdminStats();

        // Reset form
        document.getElementById('reservationForm').reset();
        document.getElementById('resDate').value = new Date().toISOString().split('T')[0];

    } catch (err) {
        alert('Gagal membuat reservasi: ' + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

function showTicketModal(data) {
    const modal = document.getElementById('ticketModal');
    if (!modal) return;

    document.getElementById('ticketBookingCode').textContent = data.booking_code;
    document.getElementById('ticketCustomerName').textContent = data.customer_name;
    document.getElementById('ticketPhone').textContent = data.phone;
    document.getElementById('ticketDate').textContent = data.reservation_date;
    document.getElementById('ticketTime').textContent = data.reservation_time + ' WIB';
    document.getElementById('ticketGuests').textContent = `${data.guest_count} Orang`;
    document.getElementById('ticketArea').textContent = data.table_area;
    document.getElementById('ticketNotes').textContent = data.special_notes || '-';
    document.getElementById('ticketStatus').textContent = data.status;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeTicketModal() {
    const modal = document.getElementById('ticketModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function copyBookingCode() {
    const code = document.getElementById('ticketBookingCode').textContent;
    navigator.clipboard.writeText(code).then(() => {
        alert('Kode booking berhasil disalin: ' + code);
    });
}

// ==================== CEK STATUS RESERVASI ====================

async function handleTrackReservation(e) {
    e.preventDefault();
    const query = document.getElementById('trackInput').value.trim();
    if (!query) return;

    const resultDiv = document.getElementById('trackResult');
    resultDiv.innerHTML = `
        <div class="py-8 text-center text-gray-500">
            <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-amber-600 mb-2"></div>
            <p class="text-sm">Mencari data reservasi di database...</p>
        </div>
    `;

    try {
        const res = await fetch(`/api/reservations/${encodeURIComponent(query)}`);
        const json = await res.json();

        if (!res.ok || !json.success || json.data.length === 0) {
            resultDiv.innerHTML = `
                <div class="p-6 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-center">
                    <p class="font-bold">Data Reservasi Tidak Ditemukan</p>
                    <p class="text-xs mt-1 text-rose-600">Periksa kembali Kode Booking (contoh: <code>SB-20261015-1042</code>) atau Nomor Telepon Anda.</p>
                </div>
            `;
            return;
        }

        resultDiv.innerHTML = json.data.map(item => {
            let statusBadgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';
            if (item.status === 'Cancelled') statusBadgeClass = 'bg-rose-100 text-rose-800 border-rose-200';
            else if (item.status === 'Completed') statusBadgeClass = 'bg-blue-100 text-blue-800 border-blue-200';
            else if (item.status === 'Pending') statusBadgeClass = 'bg-amber-100 text-amber-800 border-amber-200';

            return `
                <div class="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm mb-4">
                    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3 mb-3">
                        <div>
                            <span class="text-xs text-gray-400">Kode Booking</span>
                            <p class="font-mono font-bold text-gray-900 text-base">${item.booking_code}</p>
                        </div>
                        <span class="px-3 py-1 text-xs font-bold rounded-full border ${statusBadgeClass}">
                            ● ${item.status}
                        </span>
                    </div>

                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm mb-4">
                        <div>
                            <span class="text-xs text-gray-400 block">Nama Pemesan</span>
                            <span class="font-semibold text-gray-800">${item.customer_name}</span>
                        </div>
                        <div>
                            <span class="text-xs text-gray-400 block">Tanggal</span>
                            <span class="font-semibold text-gray-800">${item.reservation_date}</span>
                        </div>
                        <div>
                            <span class="text-xs text-gray-400 block">Jam Kedatangan</span>
                            <span class="font-semibold text-gray-800">${item.reservation_time} WIB</span>
                        </div>
                        <div>
                            <span class="text-xs text-gray-400 block">Area & Jumlah Tamu</span>
                            <span class="font-semibold text-gray-800">${item.table_area} (${item.guest_count} Orang)</span>
                        </div>
                    </div>

                    ${item.special_notes ? `
                        <div class="text-xs bg-gray-50 p-2.5 rounded-lg text-gray-600 mb-3">
                            <span class="font-bold text-gray-700">Catatan:</span> ${item.special_notes}
                        </div>
                    ` : ''}

                    ${item.status === 'Confirmed' || item.status === 'Pending' ? `
                        <div class="flex justify-end pt-2 border-t border-gray-100">
                            <button 
                                onclick="cancelReservation(${item.id})"
                                class="text-xs text-rose-600 hover:text-rose-800 font-semibold px-3 py-1.5 rounded hover:bg-rose-50 transition-all">
                                ✕ Batalkan Reservasi Ini
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

    } catch (err) {
        resultDiv.innerHTML = '<p class="text-rose-500 text-center">Gagal mencari data reservasi.</p>';
    }
}

async function cancelReservation(resId) {
    if (!confirm('Apakah Anda yakin ingin membatalkan reservasi ini?')) return;

    try {
        const res = await fetch(`/api/reservations/${resId}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Cancelled' })
        });
        const json = await res.json();
        if (json.success) {
            alert('Reservasi berhasil dibatalkan.');
            // Refresh tracking
            const trackForm = document.getElementById('trackForm');
            if (trackForm) trackForm.dispatchEvent(new Event('submit'));
            // Refresh admin jika terbuka
            loadAdminReservations();
        }
    } catch (err) {
        alert('Gagal membatalkan reservasi: ' + err.message);
    }
}

// ==================== ADMIN DASHBOARD ====================

let dbAutoRefreshInterval = null;

function toggleAdminTab(tabName) {
    const resTab = document.getElementById('adminTabReservations');
    const dbTab = document.getElementById('adminTabDb');
    const menuTab = document.getElementById('adminTabMenu');
    const infoTab = document.getElementById('adminTabInfo');

    const btnRes = document.getElementById('adminBtnReservations');
    const btnDb = document.getElementById('adminBtnDb');
    const btnMenu = document.getElementById('adminBtnMenu');
    const btnInfo = document.getElementById('adminBtnInfo');

    [resTab, dbTab, menuTab, infoTab].forEach(t => t?.classList.add('hidden'));
    [btnRes, btnDb, btnMenu, btnInfo].forEach(b => {
        b?.classList.remove('bg-amber-600', 'text-white');
        b?.classList.add('bg-stone-100', 'text-stone-700');
    });

    if (tabName === 'reservations') {
        resTab?.classList.remove('hidden');
        btnRes?.classList.add('bg-amber-600', 'text-white');
        loadAdminReservations();
    } else if (tabName === 'db') {
        dbTab?.classList.remove('hidden');
        btnDb?.classList.add('bg-amber-600', 'text-white');
        loadDbStatusInspector();
    } else if (tabName === 'menu') {
        menuTab?.classList.remove('hidden');
        btnMenu?.classList.add('bg-amber-600', 'text-white');
        loadAdminMenu();
    } else if (tabName === 'info') {
        infoTab?.classList.remove('hidden');
        btnInfo?.classList.add('bg-amber-600', 'text-white');
    }
}

async function loadDbStatusInspector() {
    try {
        const res = await fetch('/api/db-status');
        const json = await res.json();
        if (!json.success) return;

        const db = json.database;
        const recent = json.recent_records;

        document.getElementById('dbFileName').textContent = db.file_name;
        document.getElementById('dbFilePath').textContent = db.file_path;
        document.getElementById('dbFileSize').textContent = db.size_readable;
        document.getElementById('dbLastModified').textContent = db.last_modified;
        document.getElementById('dbTotalReservations').textContent = `${db.total_reservations} Baris Data`;
        document.getElementById('dbTotalMenus').textContent = `${db.total_menus} Menu`;

        // Render Recent Records
        const tbody = document.getElementById('dbRecentTableBody');
        if (tbody) {
            if (recent.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="py-4 text-center text-stone-400">Belum ada transaksi di database.</td></tr>';
            } else {
                tbody.innerHTML = recent.map(r => `
                    <tr class="border-b border-stone-100 hover:bg-stone-50 font-mono text-[11px]">
                        <td class="py-2 px-3 font-bold text-amber-700">#${r.id}</td>
                        <td class="py-2 px-3 font-bold text-stone-900">${r.booking_code}</td>
                        <td class="py-2 px-3 font-sans font-semibold">${r.customer_name}</td>
                        <td class="py-2 px-3">${r.phone}</td>
                        <td class="py-2 px-3 font-sans">${r.reservation_date} ${r.reservation_time} (${r.guest_count}pax)</td>
                        <td class="py-2 px-3 font-sans">${r.table_area}</td>
                        <td class="py-2 px-3">
                            <span class="px-2 py-0.5 rounded font-bold text-[10px] bg-emerald-100 text-emerald-800">
                                ✓ Tersimpan
                            </span>
                        </td>
                    </tr>
                `).join('');
            }
        }
    } catch (err) {
        console.error('Gagal mengambil status DB:', err);
    }
}

function toggleAutoRefreshDb(enabled) {
    if (enabled) {
        loadDbStatusInspector();
        dbAutoRefreshInterval = setInterval(loadDbStatusInspector, 3000);
    } else {
        if (dbAutoRefreshInterval) clearInterval(dbAutoRefreshInterval);
    }
}

async function loadAdminStats() {
    try {
        const res = await fetch('/api/stats');
        const json = await res.json();
        if (!json.success) return;

        const s = json.stats;
        document.getElementById('statTotalReservations').textContent = s.total_reservations;
        document.getElementById('statTodayReservations').textContent = s.reservations_today;
        document.getElementById('statConfirmed').textContent = s.total_confirmed;
        document.getElementById('statTotalMenus').textContent = s.total_menus;
    } catch (err) {
        console.error('Gagal memuat stats:', err);
    }
}

async function loadAdminReservations() {
    loadAdminStats();
    const tbody = document.getElementById('adminReservationsTableBody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-gray-400">Memuat data reservasi...</td></tr>';

    try {
        const res = await fetch('/api/reservations');
        const json = await res.json();
        if (!json.success || json.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-gray-400">Belum ada reservasi masuk.</td></tr>';
            return;
        }

        tbody.innerHTML = json.data.map(r => `
            <tr class="border-b border-gray-100 hover:bg-gray-50 text-xs">
                <td class="py-3 px-3 font-mono font-bold text-gray-800">${r.booking_code}</td>
                <td class="py-3 px-3">
                    <span class="font-bold text-gray-900 block">${r.customer_name}</span>
                    <span class="text-gray-500">${r.phone}</span>
                </td>
                <td class="py-3 px-3">
                    <span class="font-semibold block">${r.reservation_date}</span>
                    <span class="text-gray-500">${r.reservation_time} WIB</span>
                </td>
                <td class="py-3 px-3">
                    <span class="font-medium">${r.table_area}</span>
                    <span class="text-gray-400 block">(${r.guest_count} Orang)</span>
                </td>
                <td class="py-3 px-3 max-w-xs truncate text-gray-600" title="${r.special_notes || ''}">
                    ${r.special_notes || '-'}
                </td>
                <td class="py-3 px-3">
                    <select 
                        onchange="changeAdminStatus(${r.id}, this.value)"
                        class="text-xs rounded border border-gray-300 py-1 px-1.5 font-medium ${
                            r.status === 'Confirmed' ? 'text-emerald-700 bg-emerald-50' :
                            r.status === 'Cancelled' ? 'text-rose-700 bg-rose-50' :
                            r.status === 'Completed' ? 'text-blue-700 bg-blue-50' : 'text-amber-700 bg-amber-50'
                        }">
                        <option value="Confirmed" ${r.status === 'Confirmed' ? 'selected' : ''}>Confirmed</option>
                        <option value="Completed" ${r.status === 'Completed' ? 'selected' : ''}>Completed</option>
                        <option value="Cancelled" ${r.status === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
                        <option value="Pending" ${r.status === 'Pending' ? 'selected' : ''}>Pending</option>
                    </select>
                </td>
                <td class="py-3 px-3 text-right">
                    <button onclick="deleteReservationRow(${r.id})" class="text-rose-600 hover:text-rose-800 font-bold p-1">
                        🗑️
                    </button>
                </td>
            </tr>
        `).join('');

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="py-4 text-center text-rose-500">Gagal memuat reservasi.</td></tr>';
    }
}

async function changeAdminStatus(id, newStatus) {
    try {
        await fetch(`/api/reservations/${id}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        loadAdminStats();
    } catch (err) {
        alert('Gagal update status: ' + err.message);
    }
}

async function deleteReservationRow(id) {
    if (!confirm('Hapus permanen data reservasi ini?')) return;
    try {
        await fetch(`/api/reservations/${id}`, { method: 'DELETE' });
        loadAdminReservations();
    } catch (err) {
        alert('Gagal menghapus: ' + err.message);
    }
}

// ==================== ADMIN MENU CRUD ====================

async function loadAdminMenu() {
    const tbody = document.getElementById('adminMenuTableBody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="py-8 text-center text-gray-400">Memuat daftar menu...</td></tr>';

    try {
        const res = await fetch('/api/menu');
        const json = await res.json();
        if (!json.success || json.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="py-8 text-center text-gray-400">Belum ada menu di database.</td></tr>';
            return;
        }

        tbody.innerHTML = json.data.map(m => `
            <tr class="border-b border-gray-100 hover:bg-gray-50 text-xs">
                <td class="py-2.5 px-3">
                    <img src="${m.image_url}" class="w-10 h-10 rounded-lg object-cover" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=100&q=80'" />
                </td>
                <td class="py-2.5 px-3">
                    <span class="font-bold text-gray-900 block">${m.name}</span>
                    <span class="text-gray-400 text-[11px]">${m.category}</span>
                </td>
                <td class="py-2.5 px-3 font-semibold text-amber-700">
                    ${formatRupiah(m.price)}
                </td>
                <td class="py-2.5 px-3">
                    <button 
                        onclick="toggleMenuAvailability(${m.id}, ${m.is_available})"
                        class="px-2.5 py-1 rounded-full text-[11px] font-bold ${
                            m.is_available 
                                ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200' 
                                : 'bg-rose-100 text-rose-800 hover:bg-rose-200'
                        }">
                        ${m.is_available ? '● Tersedia' : '✕ Habis'}
                    </button>
                </td>
                <td class="py-2.5 px-3">
                    <button 
                        onclick="toggleMenuFavorite(${m.id}, ${m.is_favorite})"
                        class="text-base">
                        ${m.is_favorite ? '⭐' : '☆'}
                    </button>
                </td>
                <td class="py-2.5 px-3 text-right space-x-1">
                    <button onclick="editMenuPricePrompt(${m.id}, ${m.price})" class="text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50">
                        Ubah Harga
                    </button>
                    <button onclick="deleteMenuItem(${m.id})" class="text-rose-600 hover:text-rose-800 font-medium px-2 py-1 rounded hover:bg-rose-50">
                        Hapus
                    </button>
                </td>
            </tr>
        `).join('');

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-rose-500">Gagal memuat menu.</td></tr>';
    }
}

async function toggleMenuAvailability(id, currentStatus) {
    try {
        await fetch(`/api/menu/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_available: currentStatus ? 0 : 1 })
        });
        loadAdminMenu();
        loadMenu(); // Refresh tampilan pengunjung juga
    } catch (err) {
        alert('Gagal mengubah status menu');
    }
}

async function toggleMenuFavorite(id, currentFav) {
    try {
        await fetch(`/api/menu/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_favorite: currentFav ? 0 : 1 })
        });
        loadAdminMenu();
        loadMenu();
    } catch (err) {
        alert('Gagal mengubah status favorit');
    }
}

async function editMenuPricePrompt(id, currentPrice) {
    const newPriceStr = prompt('Masukkan harga baru dalam Rupiah (hanya angka):', currentPrice);
    if (!newPriceStr) return;
    const newPrice = parseInt(newPriceStr.replace(/\D/g, ''), 10);
    if (isNaN(newPrice) || newPrice <= 0) {
        alert('Harga tidak valid.');
        return;
    }

    try {
        await fetch(`/api/menu/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ price: newPrice })
        });
        loadAdminMenu();
        loadMenu();
    } catch (err) {
        alert('Gagal update harga');
    }
}

async function deleteMenuItem(id) {
    if (!confirm('Hapus item menu ini dari database?')) return;
    try {
        await fetch(`/api/menu/${id}`, { method: 'DELETE' });
        loadAdminMenu();
        loadMenu();
        loadCategories();
    } catch (err) {
        alert('Gagal menghapus menu');
    }
}

async function handleAddMenuItem(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById('newMenuName').value.trim(),
        category: document.getElementById('newMenuCategory').value,
        price: parseInt(document.getElementById('newMenuPrice').value, 10),
        description: document.getElementById('newMenuDesc').value.trim(),
        image_url: document.getElementById('newMenuImg').value.trim() || 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80',
        spicy_level: parseInt(document.getElementById('newMenuSpicy').value, 10),
        is_favorite: document.getElementById('newMenuFav').checked ? 1 : 0,
        is_available: 1
    };

    try {
        const res = await fetch('/api/menu', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
            alert('Menu baru berhasil ditambahkan!');
            document.getElementById('addMenuForm').reset();
            loadAdminMenu();
            loadMenu();
            loadCategories();
            loadAdminStats();
        }
    } catch (err) {
        alert('Gagal menambah menu: ' + err.message);
    }
}

// ==================== ADMIN INFO RESTO ====================

function fillAdminInfoForm(info) {
    if (!info) return;
    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val || '';
    };

    setVal('adminRestoName', info.name);
    setVal('adminRestoTagline', info.tagline);
    setVal('adminRestoAddress', info.address);
    setVal('adminRestoPhone', info.phone);
    setVal('adminRestoWA', info.whatsapp);
    setVal('adminRestoOpen', info.open_time);
    setVal('adminRestoClose', info.close_time);
}

async function handleUpdateRestaurantInfo(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById('adminRestoName').value.trim(),
        tagline: document.getElementById('adminRestoTagline').value.trim(),
        address: document.getElementById('adminRestoAddress').value.trim(),
        phone: document.getElementById('adminRestoPhone').value.trim(),
        whatsapp: document.getElementById('adminRestoWA').value.trim(),
        open_time: document.getElementById('adminRestoOpen').value.trim(),
        close_time: document.getElementById('adminRestoClose').value.trim()
    };

    try {
        const res = await fetch('/api/info', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
            alert('Informasi restoran & jam operasional berhasil diperbarui di database!');
            loadRestaurantInfo();
        }
    } catch (err) {
        alert('Gagal update info: ' + err.message);
    }
}
