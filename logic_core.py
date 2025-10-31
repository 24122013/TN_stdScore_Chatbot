import pandas as pd
import glob
import re
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.stats import linregress
import numpy as np
import openpyxl
import base64
# =============================================================================
# BƯỚC 1: HÀM TẢI VÀ XỬ LÝ DỮ LIỆU
# =============================================================================

def process_data_from_sheets(all_dfs, output_filename="admission_data_processed.csv"):
    """
    Nhận một DANH SÁCH các DataFrame (đã được đọc từ Google Sheets),
    gộp chúng lại và xử lý.
    """
    if not all_dfs:
        print("Không có dữ liệu nào được truyền để xử lý.")
        return False
    master_df = pd.concat(all_dfs, ignore_index=True)

    # --- SỬA LỖI QUAN TRỌNG: CHUYỂN ĐỔI CHUỖI RỖNG THÀNH NaN ---
    # Chuyển đổi tất cả các giá trị là chuỗi rỗng '' trong cột STT thành NaN
    # (hoặc pd.NA) để logic isna() hoạt động chính xác.
    master_df['STT'] = master_df['STT'].replace(r'^\s*$', np.nan, regex=True)
    # --- KẾT THÚC SỬA LỖI ---

    # 1. Tạo cột 'Trường Gốc'
    master_df['Trường Gốc'] = master_df['Tên trường'].where(master_df['STT'].notna())
    master_df['Trường Gốc'] = master_df['Trường Gốc'].ffill()
    
    # 2. LỌC BỎ "LỚP NGUỒN" NGAY BÂY GIỜ
    #    Sử dụng cột 'Tên trường' GỐC (nơi 'Lớp nguồn' tồn tại)
    is_lop_nguon = master_df['Tên trường'] == 'Lớp nguồn'
    master_df = master_df[~is_lop_nguon].copy()

    # 3. Tạo cột 'Đối tượng' (Entity) mới
    is_chuyen_subject = master_df['STT'].isna()
    
    # Mặc định 'Đối tượng' là 'Tên trường' (ví dụ: "THPT Tây Ninh")
    master_df['Đối tượng'] = master_df['Tên trường'] 
    
    # Ghi đè 'Đối tượng' cho các môn chuyên (ví dụ: "Trường chuyên Hoàng Lê Kha - Ngữ Văn")
    master_df.loc[is_chuyen_subject, 'Đối tượng'] = master_df['Trường Gốc'] + ' - ' + master_df['Tên trường']
    
    # 4. Chuyển đổi 'Điểm chuẩn' sang dạng số
    #    Thêm thay thế '' thành NaN cho cột Điểm chuẩn để đề phòng
    master_df['Điểm chuẩn'] = master_df['Điểm chuẩn'].replace(r'^\s*$', np.nan, regex=True)
    master_df['Điểm chuẩn'] = pd.to_numeric(master_df['Điểm chuẩn'], errors='coerce')
    
    # 5. Xóa các hàng không có điểm (ví dụ: hàng tiêu đề "Trường chuyên Hoàng Lê Kha")
    master_df.dropna(subset=['Điểm chuẩn'], inplace=True)
    
    # 6. Chọn các cột cuối cùng (sử dụng 'Đối tượng', bỏ 'Tên trường' gốc)
    final_cols = ['Năm học', 'Trường Gốc', 'Đối tượng', 'Điểm chuẩn', 'Chỉ tiêu', 'Ghi chú']
    existing_cols = [col for col in final_cols if col in master_df.columns]
    master_df = master_df[existing_cols]

    # Lưu file đã xử lý (dùng làm cache)
    master_df.to_csv(output_filename, index=False)
    print(f"Dữ liệu Google Sheet đã được xử lý và lưu vào file '{output_filename}'")
    
    # In ra vài dòng đầu của file đã xử lý để kiểm tra
    print("\n--- Dữ liệu đã xử lý (5 dòng đầu) ---")
    print(master_df.head())
    print("---------------------------------")
    
    return True

# =============================================================================
# BƯỚC 2: HÀM VẼ BIỂU ĐỒ (Yêu cầu 2)
# =============================================================================

def plot_admission_trends(data_file, entities, filename='trend_plot.png'):
    """
    Vẽ biểu đồ đường cho các 'Tên trường' (entities) được chỉ định từ file dữ liệu.
    """
    try:
        data = pd.read_csv(data_file)
    except FileNotFoundError:
        return f"Lỗi: Không tìm thấy file dữ liệu {data_file}"
    all_years = sorted(data['Năm học'].unique())    
    plt.figure(figsize=(12, 7))
    filtered_data = data[data['Đối tượng'].isin(entities)]
    
    if filtered_data.empty:
        plt.close()
        return f"Không tìm thấy dữ liệu cho các Tên trường: {entities}"

    filtered_data = filtered_data.sort_values('Năm học')
    
    for entity_name in entities:
        entity_data = filtered_data[filtered_data['Đối tượng'] == entity_name]
        if not entity_data.empty:
            entity_data_indexed = entity_data.set_index('Năm học')
            entity_scores = entity_data_indexed['Điểm chuẩn'].reindex(all_years)
            plt.plot(all_years, entity_scores, marker='o', label=entity_name)

    plt.xlabel('Năm học', fontsize=12)
    plt.ylabel('Điểm chuẩn', fontsize=12)
    plt.title('Xu hướng điểm chuẩn tuyển sinh qua các năm', fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', title='Tên trường')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    ax = plt.gca()
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
    plt.tight_layout(rect=[0, 0, 0.75, 1]) 
    
    plt.savefig(filename)
    plt.close()
    
    return os.path.abspath(filename)

# =============================================================================
# BƯỚC 3, 4, 5: HÀM LOGIC CỐT LÕI (TÍNH ĐIỂM, XU HƯỚNG, ĐỀ XUẤT)
# =============================================================================

def calculate_admission_scores(diem_van, diem_toan, diem_anh, diem_tb_4nam, diem_uu_tien, mon_chuyen=None, diem_mon_chuyen=None):
    """
    (Yêu cầu 3) Tính điểm xét tuyển cho cả hệ thường và hệ chuyên.
    """
    try:
        diem_thi_3mon = float(diem_van) + float(diem_toan) + float(diem_anh)
        diem_tb = float(diem_tb_4nam); uu_tien = float(diem_uu_tien)
        diem_xet_thuong = round((diem_thi_3mon * 0.7) + (diem_tb * 0.3) + uu_tien, 2)
    except ValueError: 
        diem_xet_thuong = 0.0
        
    diem_xet_chuyen = {}
    if mon_chuyen and diem_mon_chuyen is not None:
        try:
            diem_chuyen_val = float(diem_mon_chuyen)
            diem_xet_chuyen[mon_chuyen] = round(diem_thi_3mon + (diem_chuyen_val * 2), 2)
        except ValueError: 
            pass # Bỏ qua nếu điểm môn chuyên không hợp lệ
            
    return diem_xet_thuong, diem_xet_chuyen

def get_trend_slope(school_history):
    """
    Tính toán độ dốc (slope) của xu hướng điểm chuẩn dùng thuật toán hồi quy tuyến tính tích hợp sẵn.
    """
    if len(school_history) < 2: return 0
    x = np.arange(len(school_history)); y = school_history['Điểm chuẩn'].values
    if np.isnan(y).any(): return 0
    try: 
        return linregress(x, y).slope
    except ValueError: 
        return 0

def get_safety_level(diem_xet, diem_chuan_last_year, slope):
    """
    (Yêu cầu 4 - ĐÃ CẬP NHẬT: Quay lại 4 vùng gốc)
    """
    is_higher = diem_xet >= diem_chuan_last_year
    is_trending_down = slope < -0.1 

    if is_higher and is_trending_down:
        return (1, "An toàn cao (Điểm xét cao hơn, xu hướng giảm)")
    elif is_higher and not is_trending_down:
        return (2, "An toàn (Điểm xét cao hơn, xu hướng tăng/ổn định)")
    elif not is_higher and is_trending_down:
        return (3, "Nguy cơ (Điểm xét thấp hơn, nhưng xu hướng giảm)")
    else: # not is_higher and not is_trending_down
        return (4, "Nguy cơ cao (Điểm xét thấp hơn, xu hướng tăng/ổn định)")

def get_recommendations(data_file, diem_van, diem_toan, diem_anh, diem_tb_4nam, diem_uu_tien, mon_chuyen=None, diem_mon_chuyen=None):
    """
    (Yêu cầu 5 - ĐÃ CẬP NHẬT: Trả về 3 nhóm, mỗi nhóm 5 trường)
    """
    try:
        master_data = pd.read_csv(data_file)
    except FileNotFoundError:
        return {}, f"Lỗi: Không tìm thấy file dữ liệu '{data_file}'."
        
    diem_xet_thuong, diem_xet_chuyen = calculate_admission_scores(
        diem_van, diem_toan, diem_anh, diem_tb_4nam, diem_uu_tien, mon_chuyen, diem_mon_chuyen
    )
    
    master_data_sorted = master_data.sort_values('Năm học')
    all_years = master_data_sorted['Năm học'].unique()
    
    latest_year = all_years[-1]
    last_year_data = master_data[master_data['Năm học'] == latest_year].set_index('Đối tượng')['Điểm chuẩn']
    
    second_last_year_data = pd.Series(dtype=float) 
    if len(all_years) > 1:
        second_latest_year = all_years[-2]
        second_last_year_data = master_data[master_data['Năm học'] == second_latest_year].set_index('Đối tượng')['Điểm chuẩn']

    all_entities = master_data['Đối tượng'].unique()
    results = []
    
    for entity in all_entities:
        school_history = master_data[master_data['Đối tượng'] == entity].sort_values('Năm học')
        
        if entity not in last_year_data: continue 
            
        diem_chuan_last = last_year_data[entity]
        
        slope = get_trend_slope(school_history)
        slope_str = 'Giảm' if slope < -0.1 else ('Tăng' if slope > 0.1 else 'Ổn định')

        diem_chuan_second_last = second_last_year_data.get(entity)
        
        year_on_year_str = "" 
        if diem_chuan_second_last is not None:
            year_on_year_change = round(diem_chuan_last - diem_chuan_second_last, 2)
            year_on_year_str = f" ({year_on_year_change:+.2f})"
        else:
            year_on_year_str = " (Mới)"
            
        xu_huong_final = f"{slope_str}{year_on_year_str}"
            
        is_chuyen = 'Trường chuyên Hoàng Lê Kha' in entity
        diem_xet = 0
        
        if is_chuyen:
            subject = entity.split(' - ')[-1]
            if subject in diem_xet_chuyen:
                diem_xet = diem_xet_chuyen[subject]
            else: 
                continue
        else:
            diem_xet = diem_xet_thuong
            
        safety_code, safety_desc = get_safety_level(diem_xet, diem_chuan_last, slope)
        
        chenh_lech = round(diem_xet - diem_chuan_last, 2)
        chenh_lech_str = f"+{chenh_lech}" if chenh_lech >= 0 else f"{chenh_lech}"

        results.append({
            'Đối tượng': entity, 
            'Điểm chuẩn năm ngoái': diem_chuan_last,
            'Điểm xét của bạn': diem_xet,
            'Chênh lệch': chenh_lech_str,
            'Xu hướng điểm': xu_huong_final, 
            'Độ an toàn (Mã)': safety_code, 
            'Đánh giá': safety_desc
        })
        
    if not results:
        if mon_chuyen: return {}, f"Không có trường nào phù hợp với môn chuyên '{mon_chuyen}'."
        return {}, "Không thể tính toán đề xuất."
        
    df_results = pd.DataFrame(results)
    
    # Tách thành 3 nhóm (bỏ qua Mã 4)
    df_ma_1 = df_results[df_results['Độ an toàn (Mã)'] == 1]
    df_ma_2 = df_results[df_results['Độ an toàn (Mã)'] == 2]
    df_ma_3 = df_results[df_results['Độ an toàn (Mã)'] == 3]
    
    # --- THAY ĐỔI LOGIC CHÍNH THEO YÊU CẦU ---
    # Sắp xếp mỗi nhóm và lấy Top 5 
    df_ma_1 = df_ma_1.sort_values(by='Điểm chuẩn năm ngoái', ascending=False).head(5)
    df_ma_2 = df_ma_2.sort_values(by='Điểm chuẩn năm ngoái', ascending=False).head(5)
    df_ma_3 = df_ma_3.sort_values(by='Điểm chuẩn năm ngoái', ascending=False).head(5)
    # --- KẾT THÚC THAY ĐỔI ---
    for df in [df_ma_1, df_ma_2, df_ma_3]:
        if 'Đối tượng' in df.columns:
            df.rename(columns={'Đối tượng': 'Tên trường'}, inplace=True)
    
    recommendations = {
        'an_toan_cao': df_ma_1,
        'an_toan': df_ma_2,
        'nguy_co_giam': df_ma_3
    }
    
    return recommendations, """Cảm ơn bạn đã cung cấp thông tin. Dưới đây là đề xuất các trường phù hợp với mức điểm bạn có theo từng độ an toàn.
    Lưu ý:
    1.Nếu không có trường nào trong một mức độ an toàn, mục đó sẽ không được hiển thị.
    2.Đề xuất dựa trên dữ liệu lịch sử và điểm xét của bạn, không đảm bảo trúng tuyển.
    3.Bạn nên xem xét các mức độ an toàn khác nhau và xu hướng tăng giảm các trường cũng như độ lệch điểm chuẩn so với năm trước.
    4.Nếu môn chuyên bạn chọn là lịch sử, hãy tham khảo nhiều nguồn khác vì môn chuyên này mới mở lớp gần đây nên dữ liệu hiện tại không đủ để đưa ra đề xuất chính xác.
    5.Thông tin về xu hướng điểm sẽ được trình bày dưới dạng (<Xu hướng tổng quát từ 2020 tới nay> + <mức thay đổi điểm chuẩn so với năm trước>). Điều này nghĩa là xu hướng tổng quát có thể là tăng nhưng so với năm trước đó điểm đã có sự sụt giảm."""

# =============================================================================
# BƯỚC 6: HÀM TỔNG HỢP CHẠY CHATBOT (Yêu cầu 6)
# =============================================================================

def main_chatbot_function(diem_van, diem_toan, diem_anh, diem_tb_4nam, diem_uu_tien, mon_chuyen=None, diem_mon_chuyen=None):
    """
    Hàm tổng hợp, mô phỏng luồng chạy của chatbot.
    """
    DATA_FILE = "admission_data_processed.csv"
    
    print(f"--- Bắt đầu tư vấn cho học sinh ---")
    print(f"Điểm đầu vào: Văn={diem_van}, Toán={diem_toan}, Anh={diem_anh}, TB 4 năm={diem_tb_4nam}, Ưu tiên={diem_uu_tien}, Chuyên={mon_chuyen}")
    
    # 1. Lấy Top 5 đề xuất
    top_5_schools, message = get_recommendations(
        data_file=DATA_FILE,
        diem_van=diem_van, diem_toan=diem_toan, diem_anh=diem_anh,
        diem_tb_4nam=diem_tb_4nam, diem_uu_tien=diem_uu_tien,
        mon_chuyen=mon_chuyen, diem_mon_chuyen=diem_mon_chuyen
    )
    
    if top_5_schools.empty:
        print(message)
        return
        
    print("\n--- TOP 5 TRƯỜNG ĐỀ XUẤT ---")
    print(message)
    # in ra dạng bảng cho dễ đọc
    print(top_5_schools.to_markdown(index=False)) 
    
    # 2. Lấy 5 tên trường từ kết quả
    entities_to_plot = top_5_schools['Đối tượng'].tolist()
    
    # 3. Vẽ biểu đồ cho 5 trường này
    print(f"\nĐang tạo biểu đồ cho 5 trường: {entities_to_plot}...")
    plot_filename = "recommendation_plot.png"
    plot_path = plot_admission_trends(
        data_file=DATA_FILE,
        entities=entities_to_plot,
        filename=plot_filename
    )
    
    print(f"--- HOÀN THÀNH ---")
    print(f"Đã trả về Top 5 trường (ảnh trên) và biểu đồ đã được lưu tại: {plot_path}")

if "__main__" == __name__:
    # Ví dụ chạy thử
    main_chatbot_function(
        diem_van=8.0,
        diem_toan=7.5,
        diem_anh=8.5,
        diem_tb_4nam=8.0,
        diem_uu_tien=0.5,
        mon_chuyen="Toán",
        diem_mon_chuyen=9.0
    )


