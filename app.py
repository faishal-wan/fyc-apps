import streamlit as st
import pandas as pd
import os

# Menyuntikkan CSS untuk membuat tampilan setara zoom 80%
st.set_page_config(page_title="FYC Creator Rapor", layout="wide")
st.markdown("""
    <style>
        html, body, [class*="css"] {
            font-size: 14px;
        }
        .stApp {
            zoom: 0.8; 
        }
    </style>
""", unsafe_allow_html=True)

if not os.path.exists("database"):
    os.makedirs("database")

st.sidebar.title("FYC Tools")
menu = st.sidebar.radio("Navigasi", ["Database Admin", "Generate Rapor"])

# ==========================================
# HALAMAN 1: DATABASE ADMIN
# ==========================================
if menu == "Database Admin":
    st.header("⚙️ Update Data Master Creator")
    st.write("Unggah file 'Total creator data' terbaru di sini.")
    master_file = st.file_uploader("Pilih file Excel Master", type=["xlsx"])
    
    if master_file:
        df_master = pd.read_excel(master_file, sheet_name=0)
        df_master.to_csv("database/master_data.csv", index=False)
        st.success("✅ Data Master berhasil diperbarui dan tersimpan di sistem!")

# ==========================================
# HALAMAN 2: GENERATE RAPOR CREATOR
# ==========================================
elif menu == "Generate Rapor":
    st.header("📊 Rapor Performa Creator")
    
    if not os.path.exists("database/master_data.csv"):
        st.warning("⚠️ Data Master belum tersedia. Silakan unggah di menu 'Database Admin' terlebih dahulu.")
    else:
        creator_file = st.file_uploader("Unggah file performa 1 Creator (Excel)", type=["xlsx"])
        
        if creator_file:
            # 1. BUKA DATA & BERSIHKAN FORMAT TANGGAL AWAL
            df_creator = pd.read_excel(creator_file, sheet_name="Data")
            df_master = pd.read_csv("database/master_data.csv")
            
            df_creator['Post date'] = pd.to_datetime(df_creator['Post date'].astype(str), format='%Y%m%d')
            
            # --- FILTER DATE RANGE ---
            st.write("---")
            min_date = df_creator['Post date'].min().date()
            max_date = df_creator['Post date'].max().date()
            
            date_filter = st.date_input(
                "Pilih Periode Analisis:", 
                value=(min_date, max_date),
                min_value=min_date, 
                max_value=max_date
            )
            
            # Terapkan filter jika tanggal awal dan akhir sudah dipilih
            if len(date_filter) == 2:
                start_dt, end_dt = date_filter
                df_creator = df_creator[(df_creator['Post date'].dt.date >= start_dt) & (df_creator['Post date'].dt.date <= end_dt)]
            
            # Jika data kosong setelah difilter
            if df_creator.empty:
                st.warning("Tidak ada post pada rentang tanggal tersebut.")
            else:
                # Pastikan angka terbaca benar
                df_creator['Sales value'] = pd.to_numeric(df_creator['Sales value'], errors='coerce').fillna(0)
                df_creator['Orders'] = pd.to_numeric(df_creator['Orders'], errors='coerce').fillna(0)
                df_creator['Redemption amount'] = pd.to_numeric(df_creator['Redemption amount'], errors='coerce').fillna(0)
                df_creator['Video views'] = pd.to_numeric(df_creator['Video views'], errors='coerce').fillna(0)
                
                # Pemetaan Industri
                def map_industry(ind):
                    if pd.isna(ind): return 'Lainnya'
                    if ind == 'Dining': return 'Dining'
                    elif ind in ['Accommodations', 'Things to Do']: return 'Accommodation - Things to Do'
                    else: return 'Lainnya'
                df_creator['Industri Baru'] = df_creator['Location industry'].apply(map_industry)
                
                # 2. AMBIL PROFIL UMUM
                c_id = df_creator['Creator ID'].iloc[0]
                c_name = df_creator['Creator name'].iloc[0]
                c_level = df_creator['Creator level'].iloc[0]
                c_city = df_creator['Creator city'].iloc[0]
                
                # Ambil Collab Period & buang info jamnya
                master_match = df_master[df_master['Unique ID'] == c_id]
                if not master_match.empty:
                    start_str = str(master_match['Collaboration start time'].iloc[0]).split(',')[0]
                    end_str = str(master_match['Collaboration end time'].iloc[0]).split(',')[0]
                    collab_period = f"{start_str} - {end_str}"
                else:
                    collab_period = "Tidak ditemukan"
                
                # 3. FREKUENSI POSTING
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
                
                # --- TAMPILAN HEADER PROFIL ---
                st.subheader(f"{c_name} ({c_id})")
                st.markdown(f"<p style='color:gray; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Collaboration Period: {collab_period}</p>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Level", c_level)
                col2.metric("City", c_city)
                col3.metric("Industri Dominan", dominan)
                col4.metric("Frekuensi Posting", frekuensi_teks)
                
                st.divider()

                # 4. POST WITH SALES
                st.subheader("🛒 Performa Penjualan (Sales)")
                post_with_sales = len(df_creator[df_creator['Sales value'] > 0])
                persen_sales = (post_with_sales / total_post) * 100 if total_post > 0 else 0
                
                total_sales = df_creator['Sales value'].sum()
                total_orders = df_creator['Orders'].sum()
                total_redemption = df_creator['Redemption amount'].sum()
                
                # Baris 1 Penjualan
                scol1, scol2 = st.columns(2)
                scol1.metric("Post with Sales", f"{post_with_sales} dari {total_post} Post")
                scol2.metric("Persentase Sales", f"{persen_sales:.1f}%")
                
                st.write("") # Memberi jarak vertikal sedikit
                
                # Baris 2 Penjualan
                scol3, scol4, scol5 = st.columns(3)
                scol3.metric("Total Sales Value", f"Rp{int(total_sales):,}")
                scol4.metric("Total Orders", f"{int(total_orders):,}")
                scol5.metric("Total Redemption", f"Rp{int(total_redemption):,}")

                st.divider()

                # 5. PERFORMA CAMPAIGN
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
                    
                    # Style format untuk merapatkan Rp dan koma di tabel detail campaign
                    st.dataframe(
                        df_campaign[['Post date', 'Post title', 'Location name', 'Video views', 'Sales value']].style.format({
                            "Video views": "{:,.0f}",
                            "Sales value": "Rp{:,.0f}"
                        }), 
                        use_container_width=True, 
                        hide_index=True
                    )

                st.divider()

                # 6. RATA-RATA ENGAGEMENT
                st.subheader("❤️ Rata-rata Engagement")
                df_eng = df_creator.groupby('Industri Baru')[['Like rate', 'Comment rate']].mean().reset_index()
                
                cols = st.columns(len(df_eng))
                for i, row in df_eng.iterrows():
                    with cols[i]:
                        st.markdown(f"**{row['Industri Baru']}**")
                        st.markdown(f"❤️ Like rate: **{(row['Like rate'] * 100):.2f}%**")
                        st.markdown(f"💬 Comment rate: **{(row['Comment rate'] * 100):.2f}%**")
                
                st.divider()

                # 7. PERFORMA PER BRAND / MERCHANT
                st.subheader("🏢 Kinerja per Brand / Merchant")
                
                def get_clean_brand(row):
                    loc_name = str(row['Location name'])
                    # Jika Dining dan ada strip, potong teksnya
                    if row['Industri Baru'] == 'Dining' and '-' in loc_name:
                        return loc_name.split('-')[0].strip()
                    return loc_name.strip()
                    
                df_creator['Brand Bersih'] = df_creator.apply(get_clean_brand, axis=1)
                
                # Kolom untuk disortir secara kronologis (YYYY-MM)
                df_creator['Sort Bulan'] = df_creator['Post date'].dt.strftime('%Y-%m')
                df_creator['Bulan Post'] = df_creator['Post date'].dt.strftime('%B %Y')
                
                df_brand = df_creator.groupby(['Sort Bulan', 'Bulan Post', 'Industri Baru', 'Brand Bersih']).agg(
                    Jumlah_Post=('Post ID', 'count'),
                    Total_Views=('Video views', 'sum'),
                    Total_Sales=('Sales value', 'sum')
                ).reset_index()
                
                # Sortir berurutan dari bulan, lalu angka total sales, baru jumlah post
                df_brand = df_brand.sort_values(by=['Sort Bulan', 'Total_Sales', 'Jumlah_Post'], ascending=[True, False, False])
                df_brand = df_brand.drop(columns=['Sort Bulan'])
                
                # Style format supaya angka bisa disortir dengan benar tapi tetap muncul tulisan Rp di layarnya
                st.dataframe(
                    df_brand.style.format({
                        "Total_Views": "{:,.0f}",
                        "Total_Sales": "Rp{:,.0f}"
                    }), 
                    use_container_width=True, 
                    hide_index=True
                )