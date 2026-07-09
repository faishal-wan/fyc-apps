import streamlit as st
import pandas as pd
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe, get_as_dataframe

# Menyuntikkan CSS untuk membuat tampilan setara zoom 80% & Mode Cetak PDF
st.set_page_config(page_title="FYC Creator Rapor", layout="wide")
st.markdown("""
    <style>
        html, body, [class*="css"] { font-size: 14px; }
        .stApp { zoom: 0.8; }
        @media print {
            .stSidebar { display: none !important; }
            header { display: none !important; }
            .stApp { zoom: 1 !important; } 
        }
    </style>
""", unsafe_allow_html=True)

# Link Google Sheets Master (HARUS DIISI)
SHEET_URL = "MASUKKAN_LINK_GOOGLE_SHEETS_DI_SINI"

# Fungsi Koneksi API Google
@st.cache_resource
def get_gspread_client():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error("Gagal menghubungkan ke Google API. Pastikan Streamlit Secrets sudah disetting dengan benar.")
        st.stop()

st.sidebar.title("FYC Tools")
menu = st.sidebar.radio("Navigasi", ["Database Admin", "Generate Rapor", "Segmentasi Creator"])

# ==========================================
# HALAMAN 1: DATABASE ADMIN
# ==========================================
if menu == "Database Admin":
    st.header("⚙️ Update Data Master Creator")
    st.write("Unggah file Excel Master. Sistem akan memperbarui data secara cerdas dan mendeteksi status Rebound/Unbound.")
    
    master_file = st.file_uploader("Pilih file Excel Master", type=["xlsx"])
    
    if master_file:
        if SHEET_URL == "MASUKKAN_LINK_GOOGLE_SHEETS_DI_SINI":
            st.error("Link Google Sheets belum dimasukkan ke dalam kode `app.py`.")
        else:
            with st.spinner("Memproses sinkronisasi data ke Google Sheets..."):
                df_new = pd.read_excel(master_file, sheet_name=0)
                
                # Standarisasi ID ke string agar pencocokan akurat
                df_new['Unique ID'] = df_new['Unique ID'].astype(str).str.strip()
                
                client = get_gspread_client()
                sheet = client.open_by_url(SHEET_URL).sheet1
                
                # Ambil data eksisting di Google Sheets jika ada
                try:
                    df_existing = get_as_dataframe(sheet, evaluate_formulas=True).dropna(how='all').dropna(axis=1, how='all')
                    if not df_existing.empty and 'Unique ID' in df_existing.columns:
                        df_existing['Unique ID'] = df_existing['Unique ID'].astype(str).str.strip()
                    else:
                        df_existing = pd.DataFrame()
                except Exception:
                    df_existing = pd.DataFrame()
                
                if df_existing.empty:
                    # Jika Sheets kosong, set semua data baru sebagai Aktif
                    df_new['Status'] = 'Aktif'
                    df_final = df_new
                else:
                    if 'Status' not in df_existing.columns:
                        df_existing['Status'] = 'Aktif'
                    
                    existing_records = df_existing.set_index('Unique ID').to_dict('index')
                    updated_rows = []
                    processed_ids = set()
                    
                    # Looping data baru untuk cek perubahan periode (Rebound)
                    for _, row in df_new.iterrows():
                        uid = row['Unique ID']
                        new_start = str(row['Collaboration start time']).strip()
                        
                        if uid in existing_records:
                            old_start = str(existing_records[uid]['Collaboration start time']).strip()
                            old_status = existing_records[uid].get('Status', 'Aktif')
                            
                            # Deteksi jika tanggal mulai kolaborasi berubah jadi lebih baru
                            if new_start != old_start and old_start != 'nan' and new_start != 'nan':
                                row['Status'] = 'Rebound'
                            else:
                                row['Status'] = old_status if old_status in ['Aktif', 'Rebound'] else 'Aktif'
                        else:
                            row['Status'] = 'Aktif'
                        
                        updated_rows.append(row)
                        processed_ids.add(uid)
                    
                    df_final_new = pd.DataFrame(updated_rows)
                    
                    # Pertahankan data lama yang tidak ada di file baru (Ubah status jadi Unbound)
                    df_unbound = df_existing[~df_existing['Unique ID'].isin(processed_ids)].copy()
                    if not df_unbound.empty:
                        df_unbound['Status'] = 'Unbound'
                        df_final = pd.concat([df_final_new, df_unbound], ignore_index=True)
                    else:
                        df_final = df_final_new
                
                # Simpan kembali ke Google Sheets
                sheet.clear()
                set_with_dataframe(sheet, df_final)
                st.success("✅ Sinkronisasi berhasil! Data Master diperbarui dan riwayat status tersimpan.")

# ==========================================
# HALAMAN 2: GENERATE RAPOR CREATOR
# ==========================================
elif menu == "Generate Rapor":
    st.header("📊 Rapor Performa Creator")
    
    if SHEET_URL == "MASUKKAN_LINK_GOOGLE_SHEETS_DI_SINI":
        st.warning("⚠️ Masukkan link Google Sheets terlebih dahulu di dalam kode app.py.")
    else:
        try:
            client = get_gspread_client()
            sheet = client.open_by_url(SHEET_URL).sheet1
            df_master = get_as_dataframe(sheet, evaluate_formulas=True).dropna(how='all').dropna(axis=1, how='all')
        except Exception:
            df_master = pd.DataFrame()

        if df_master.empty:
            st.warning("⚠️ Data Master di Google Sheets masih kosong. Silakan unggah di menu 'Database Admin'.")
        else:
            creator_file = st.file_uploader("Unggah file performa 1 Creator (Excel)", type=["xlsx"])
            
            if creator_file:
                df_creator = pd.read_excel(creator_file, sheet_name="Data")
                df_creator['Post date'] = pd.to_datetime(df_creator['Post date'].astype(str), format='mixed', errors='coerce')
                
                st.write("---")
                min_date = df_creator['Post date'].min().date()
                max_date = df_creator['Post date'].max().date()
                
                date_filter = st.date_input(
                    "Pilih Periode Analisis:", 
                    value=(min_date, max_date),
                    min_value=min_date, 
                    max_value=max_date
                )
                
                if len(date_filter) == 2:
                    start_dt, end_dt = date_filter
                    df_creator = df_creator[(df_creator['Post date'].dt.date >= start_dt) & (df_creator['Post date'].dt.date <= end_dt)]
                
                if df_creator.empty:
                    st.warning("Tidak ada post pada rentang tanggal tersebut.")
                else:
                    df_creator['Sales value'] = pd.to_numeric(df_creator['Sales value'], errors='coerce').fillna(0)
                    df_creator['Orders'] = pd.to_numeric(df_creator['Orders'], errors='coerce').fillna(0)
                    df_creator['Redemption amount'] = pd.to_numeric(df_creator['Redemption amount'], errors='coerce').fillna(0)
                    df_creator['Video views'] = pd.to_numeric(df_creator['Video views'], errors='coerce').fillna(0)
                    
                    def map_industry(ind):
                        if pd.isna(ind): return 'Lainnya'
                        if ind == 'Dining': return 'Dining'
                        elif ind in ['Accommodations', 'Things to Do']: return 'Accommodation - Things to Do'
                        else: return 'Lainnya'
                    df_creator['Industri Baru'] = df_creator['Location industry'].apply(map_industry)
                    
                    c_id = df_creator['Creator ID'].iloc[0]
                    c_name = df_creator['Creator name'].iloc[0]
                    c_level = df_creator['Creator level'].iloc[0]
                    c_city = df_creator['Creator city'].iloc[0]
                    
                    # Sinkronisasi tipe data untuk pencocokan ID master
                    master_match = df_master[df_master['Unique ID'].astype(str).str.strip() == str(c_id).strip()]
                    if not master_match.empty:
                        start_str = str(master_match['Collaboration start time'].iloc[0]).split(',')[0]
                        end_str = str(master_match['Collaboration end time'].iloc[0]).split(',')[0]
                        c_status = str(master_match['Status'].iloc[0])
                        collab_period = f"{start_str} - {end_str} ({c_status})"
                    else:
                        collab_period = "Tidak ditemukan"
                    
                    total_post = len(df_creator)
                    rentang_hari = (df_creator['Post date'].max() - df_creator['Post date'].min()).days
                    rentang_hari = 1 if rentang_hari == 0 else rentang_hari
                    
                    post_per_hari = total_post / rentang_hari
                    if post_per_hari >= 1:
                        frekuensi_teks = f"{int(post_per_hari)} post/hari"
                    else:
                        hari_per_post = int(rentang_hari / total_post) if total_post > 0 else 0
                        frekuensi_teks = f"1 post/{hari_per_post} hari"
                        
                    dominan = df_creator['Industri Baru'].value_counts().idxmax()
                    
                    st.subheader(f"{c_name} ({c_id})")
                    st.markdown(f"<p style='color:gray; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Collaboration Period: {collab_period}</p>", unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Level", c_level)
                    col2.metric("City", c_city)
                    col3.metric("Industri Dominan", dominan)
                    col4.metric("Frekuensi Posting", frekuensi_teks)
                    
                    st.divider()

                    # Layout 5 Kolom Horizontal Sesuai Mockup Canva
                    st.subheader("🛒 Performa Penjualan (Sales)")
                    post_with_sales = len(df_creator[df_creator['Sales value'] > 0])
                    persen_sales = (post_with_sales / total_post) * 100 if total_post > 0 else 0
                    
                    total_sales = df_creator['Sales value'].sum()
                    total_orders = df_creator['Orders'].sum()
                    total_redemption = df_creator['Redemption amount'].sum()
                    
                    scol1, scol2, scol3, scol4, scol5 = st.columns(5)
                    scol1.metric("Post with Sales", post_with_sales)
                    scol2.metric("Total Sales Value", f"Rp{int(total_sales):,}")
                    scol3.metric("Total Redemption", f"Rp{int(total_redemption):,}")
                    scol4.metric("Total Orders", f"{int(total_orders):,}")
                    scol5.metric("Persentase Sales", f"{persen_sales:.1f}%")

                    st.divider()

                    st.subheader("🎯 Keikutsertaan Campaign (Collaboration Package)")
                    df_campaign = df_creator[df_creator['Task type'].astype(str).str.contains("collaboration package", case=False, na=False)].copy()
                    
                    if df_campaign.empty:
                        st.write("*Creator belum mengikuti campaign 'Collaboration Package' pada periode ini.*")
                    else:
                        camp_post = len(df_campaign)
                        camp_views = df_campaign['Video views'].sum()
                        camp_sales = df_campaign['Sales value'].sum()
                        
                        ccol1, ccol2, ccol3 = st.columns(3)
                        ccol1.metric("Total Post Campaign", camp_post)
                        ccol2.metric("Total Views Campaign", f"{int(camp_views):,}")
                        ccol3.metric("Total Sales Campaign", f"Rp{int(camp_sales):,}")
                        
                        st.write("**Detail Post Campaign:**")
                        df_campaign['Post date'] = df_campaign['Post date'].dt.strftime('%Y-%m-%d')
                        
                        st.dataframe(
                            df_campaign[['Post date', 'Post title', 'Location name', 'Video views', 'Sales value']].style.format({
                                "Video views": "{:,.0f}",
                                "Sales value": "Rp{:,.0f}"
                            }), 
                            use_container_width=True, 
                            hide_index=True
                        )

                    st.divider()

                    st.subheader("❤️ Rata-rata Engagement")
                    df_eng = df_creator.groupby('Industri Baru')[['Like rate', 'Comment rate']].mean().reset_index()
                    
                    cols = st.columns(len(df_eng))
                    for i, row in df_eng.iterrows():
                        with cols[i]:
                            st.markdown(f"**{row['Industri Baru']}**")
                            st.markdown(f"❤️ Like rate: **{(row['Like rate'] * 100):.2f}%**")
                            st.markdown(f"💬 Comment rate: **{(row['Comment rate'] * 100):.2f}%**")
                    
                    st.divider()

                    st.subheader("🏢 Kinerja per Brand / Merchant")
                    
                    def get_clean_brand(row):
                        loc_name = str(row['Location name'])
                        if row['Industri Baru'] == 'Dining' and '-' in loc_name:
                            return loc_name.split('-')[0].strip()
                        return loc_name.strip()
                        
                    df_creator['Brand Bersih'] = df_creator.apply(get_clean_brand, axis=1)
                    df_creator['Sort Bulan'] = df_creator['Post date'].dt.strftime('%Y-%m')
                    df_creator['Bulan Post'] = df_creator['Post date'].dt.strftime('%B %Y')
                    
                    df_brand = df_creator.groupby(['Sort Bulan', 'Bulan Post', 'Industri Baru', 'Brand Bersih']).agg(
                        Jumlah_Post=('Post ID', 'count'),
                        Total_Views=('Video views', 'sum'),
                        Total_Sales=('Sales value', 'sum')
                    ).reset_index()
                    
                    df_brand = df_brand.sort_values(by=['Sort Bulan', 'Total_Sales', 'Jumlah_Post'], ascending=[True, False, False])
                    df_brand = df_brand.drop(columns=['Sort Bulan'])
                    
                    st.dataframe(
                        df_brand.style.format({
                            "Total_Views": "{:,.0f}",
                            "Total_Sales": "Rp{:,.0f}"
                        }), 
                        use_container_width=True, 
                        hide_index=True
                    )

# ==========================================
# HALAMAN 3: SEGMENTASI CREATOR
# ==========================================
elif menu == "Segmentasi Creator":
    st.header("👥 Segmentasi Creator (Frekuensi Post)")
    st.write("Unggah file data kolektif video untuk melihat frekuensi dan konsistensi posting bulanan.")
    
    raw_file = st.file_uploader("Pilih file Raw Data Video", type=["xlsx"])
    
    if raw_file:
        df_raw = pd.read_excel(raw_file, sheet_name="Data")
        df_raw['Post date'] = pd.to_datetime(df_raw['Post date'].astype(str), format='mixed', errors='coerce')
        df_raw['Date Only'] = df_raw['Post date'].dt.date
        days_in_month = df_raw['Post date'].dt.days_in_month.max()
        
        df_seg = df_raw.groupby(['Creator ID', 'Creator name']).agg(
            Total_Post=('Post ID', 'count'),
            Hari_Aktif=('Date Only', 'nunique')
        ).reset_index()
        
        def label_kategori(total):
            if total >= 30:
                return 'Rajin Post'
            elif 15 <= total <= 29:
                return 'Sedang'
            else:
                return 'Jarang Post'
                
        df_seg['Kategori'] = df_seg['Total_Post'].apply(label_kategori)
        df_seg['Konsisten Full Sebulan'] = df_seg['Hari_Aktif'].apply(lambda x: 'Ya' if x >= days_in_month else 'Tidak')
        df_seg = df_seg.sort_values(by='Total_Post', ascending=False)
        
        st.write("---")
        col1, col2 = st.columns(2)
        col1.metric("Total Creator Dianalisis", len(df_seg))
        col2.metric("Total Konten Keseluruhan", df_seg['Total_Post'].sum())
        
        st.write("**Tabel Segmentasi:**")
        st.dataframe(
            df_seg[['Creator ID', 'Creator name', 'Total_Post', 'Hari_Aktif', 'Kategori', 'Konsisten Full Sebulan']],
            use_container_width=True,
            hide_index=True
        )
