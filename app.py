import streamlit as st
import logic_core as logic # Import file logic của bạn
import os
import unicodedata 
import re # Cần import re ở đây
from streamlit_gsheets import GSheetsConnection # Import thư viện kết nối
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# --- Cấu hình hằng số ---
DATA_FILE = "admission_data_processed.csv"
# !!! THAY BẰNG TÊN GOOGLE SHEET CỦA BẠN
GSHEET_NAME = "std_score_TayNinh_highschools" 

MON_CHUYEN_LIST = ["Ngữ Văn", "Toán", "Vật Lý", "Hóa học", "Sinh học", "Tiếng Anh", "Tin học", "Lịch sử"]

# ===================================================================
# HÀM TIỆN ÍCH CHO CHATBOT (Định nghĩa tất cả ở đây)
# ===================================================================

def normalize_text(s):
    """
    Chuẩn hóa văn bản: bỏ dấu, bỏ khoảng trắng, chuyển sang chữ thường.
    Ví dụ: "Ngữ Văn" -> "nguvan"
    """
    s = str(s).lower().replace(" ", "")
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = s.replace('đ', 'd')
    return s

# Tạo bản đồ chuẩn hóa cho môn chuyên (định nghĩa 1 lần)
MON_CHUYEN_MAP = {normalize_text(m): m for m in MON_CHUYEN_LIST}
NORMALIZED_MON_CHUYEN_LIST = MON_CHUYEN_MAP.keys()
NORMALIZED_KHO_LIST = ["khong", "ko", "0"]


@st.cache_data(ttl=3600) # Cache 1 giờ
def run_data_processing():
    """
    Kết nối Google Sheets bằng cách nạp credentials trực tiếp từ secrets,
    lấy tên sheet thật, đọc và xử lý.
    """
    try:
        # --- NẠP CREDENTIALS VÀ XÁC THỰC GSPREAD TRỰC TIẾP ---
        if not hasattr(st, 'secrets') \
           or "connections" not in st.secrets \
           or "gsheets" not in st.secrets["connections"] \
           or "service_account_info" not in st.secrets["connections"]["gsheets"]:
             raise ValueError(
                 "File secrets.toml không được tìm thấy, thiếu mục [connections.gsheets], "
                 "hoặc thiếu khóa 'service_account_info'. Vui lòng kiểm tra lại file .streamlit/secrets.toml."
             )
             


        # 4. Xác thực client gspread bằng credentials
        print("Đang xác thực với Google Sheets...")
        creds_json = json.loads(st.secrets["connections"]["gsheets"]["service_account_info"])
        # Tạo credentials từ JSON
        creds = Credentials.from_service_account_info(
            creds_json,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        # Ủy quyền truy cập Google Sheets
        gc = gspread.authorize(creds)
        print("Xác thực thành công.")
        # --- KẾT THÚC XÁC THỰC GSPREAD ---

        # 5. Mở spreadsheet bằng client đã xác thực
        print(f"Đang mở Google Sheet: '{GSHEET_NAME}'")
        spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/12cEo7NO3mvH8zrhnharFGghiVgawNRNWrn1rxGCm2SE/edit?usp=sharing")

        print(f"Đã mở Google Sheet: '{GSHEET_NAME}'")

        all_dfs = []
        # 6. Lấy danh sách worksheet object THẬT
        worksheets = spreadsheet.worksheets()
        sheet_names = [sheet.title for sheet in worksheets] # Lấy tên thật từ title
        print(f"Đã tìm thấy các sheet (tên thật): {sheet_names}") 

        # 7. Lặp qua các worksheet object đã lấy được
        for worksheet in worksheets:
            sheet_name = worksheet.title # Lấy tên thật
            
            # Chỉ xử lý các sheet có tên năm học
            year_match = re.search(r'(\d{4}-\d{4})', sheet_name)
            if not year_match:
                print(f"Bỏ qua sheet (không chứa năm học dạng YYYY-YYYY): {sheet_name}")
                continue

            print(f"Đang đọc sheet: {sheet_name}")

            # 8. Đọc dữ liệu trực tiếp từ worksheet object bằng gspread
            all_data = worksheet.get_all_values()
            
            if len(all_data) <= 5:
                print(f"Cảnh báo: Bỏ qua sheet {sheet_name} vì không đủ dữ liệu (<= 5 hàng)")
                continue
                
            # Hàng thứ 6 (index 5) là header
            header = all_data[5]
            # Dữ liệu bắt đầu từ hàng thứ 7 (index 6)
            data_rows = all_data[6:]
            
            # Tạo DataFrame
            df = pd.DataFrame(data_rows, columns=header)
            
            year = year_match.group(1)
            df['Năm học'] = year
            all_dfs.append(df)

        if not all_dfs:
                return False, "Không tìm thấy hoặc không đọc được sheet nào có tên chứa năm học hợp lệ (YYYY-YYYY) trong Google Sheet."
        print(all_dfs)
        # Gửi danh sách các DataFrame cho hàm xử lý của logic
        success = logic.process_data_from_sheets(all_dfs, DATA_FILE)

        if success:
            return True, "Dữ liệu Google Sheet đã được xử lý và sẵn sàng tư vấn."
        else:
            return False, "Xử lý dữ liệu từ Google Sheet thất bại."
            
    # Bắt các lỗi cụ thể hơn
    except json.JSONDecodeError:
        return False, "Lỗi: Dữ liệu 'service_account_info' trong secrets.toml không phải là một chuỗi JSON hợp lệ. Vui lòng copy và dán lại toàn bộ nội dung file key .json."
    except gspread.exceptions.SpreadsheetNotFound:
         return False, f"Lỗi: Không tìm thấy Google Sheet có tên '{GSHEET_NAME}'. Vui lòng kiểm tra lại tên Sheet trong code và trên Google Drive."
    except gspread.exceptions.APIError as e:
         # Thường do API chưa bật hoặc quyền truy cập
         error_details = e.response.json()
         error_message = error_details.get('error', {}).get('message', str(e))
         permission_denied = error_details.get('error', {}).get('status') == 'PERMISSION_DENIED'
         if permission_denied:
             error_message += " Lỗi này thường do bạn chưa chia sẻ Google Sheet với email service account trong secrets.toml (hoặc chia sẻ sai email)."
         return False, f"Lỗi Google API: {error_message}. Vui lòng kiểm tra quyền chia sẻ Sheet và đảm bảo Google Sheets API đã được bật trong Google Cloud Project."
    except ValueError as e:
         # Bắt lỗi nếu secrets.toml bị thiếu hoặc sai cấu trúc cơ bản
         return False, str(e)
    except TypeError as e:
         # Bắt lỗi nếu service_account_info không phải dict
         return False, str(e)
    except Exception as e:
        # Lỗi này sẽ hiển thị nếu file secrets.toml sai cấu trúc JSON bên trong, key bị thiếu,...
        return False, f"Lỗi không xác định khi kết nối hoặc đọc Google Sheets: {e}. Vui lòng kiểm tra kỹ file '.streamlit/secrets.toml', cấu trúc JSON bên trong, và quyền chia sẻ Sheet cho email service account."


def is_valid_score(score_str, min_val=0.0, max_val=10.0):
    """Kiểm tra xem điểm nhập vào có hợp lệ không."""
    try:
        score = float(score_str)
        if min_val <= score <= max_val: return True, score
        else: return False, None
    except ValueError:
        return False, None

def add_assistant_message(content):
    """
    Thêm tin nhắn VĂN BẢN của bot vào lịch sử chat và hiển thị.
    """
    st.session_state.messages.append({"role": "assistant", "type": "text", "content": content})

def get_next_question():
    """Xác định câu hỏi tiếp theo dựa trên trạng thái."""
    if "van" not in st.session_state.user_scores:
        return "ask_van", "Chào bạn! Tôi là chatbot tư vấn tuyển sinh. Đầu tiên, điểm thi môn **Văn** dự kiến của bạn là bao nhiêu?"
    if "toan" not in st.session_state.user_scores:
        return "ask_toan", "Tuyệt! Điểm thi môn **Toán** dự kiến của bạn là bao nhiêu?"
    if "anh" not in st.session_state.user_scores:
        return "ask_anh", "Tiếp theo, điểm thi môn **Tiếng Anh** dự kiến của bạn là bao nhiêu?"
    if "tb_4nam" not in st.session_state.user_scores:
        return "ask_tb_4nam", "Gần xong rồi! **Điểm trung bình 4 năm THCS** của bạn là bao nhiêu?"
    if "uu_tien" not in st.session_state.user_scores:
        return "ask_uu_tien", "Bạn có **điểm cộng/ưu tiên** không? (Nếu không, nhập 0)"
    if "mon_chuyen" not in st.session_state.user_scores:
        return "ask_chuyen_subject", f"Cuối cùng, bạn có thi chuyên không? Nếu có, vui lòng gõ **tên môn chuyên** (Ví dụ: 'Toán', 'Ngữ Văn',...). Nếu không, gõ **'Không'**."
    if st.session_state.user_scores.get("mon_chuyen") and "diem_mon_chuyen" not in st.session_state.user_scores:
        mon = st.session_state.user_scores["mon_chuyen"]
        return "ask_chuyen_score", f"OK. Điểm thi môn chuyên **{mon}** của bạn là bao nhiêu?"
    return "calculate", "" 

def run_calculation(scores):
    """
    Gọi bộ não logic và trả về KẾT QUẢ và TIN NHẮN TÙY CHỈNH.
    """
    recommendations, message = logic.get_recommendations(
        data_file=DATA_FILE,
        diem_van=scores.get('van', 0),
        diem_toan=scores.get('toan', 0),
        diem_anh=scores.get('anh', 0),
        diem_tb_4nam=scores.get('tb_4nam', 0),
        diem_uu_tien=scores.get('uu_tien', 0),
        mon_chuyen=scores.get('mon_chuyen'),
        diem_mon_chuyen=scores.get('diem_mon_chuyen', 0)
    )
    
    if not recommendations:
        return None, message # Trả về None nếu thất bại

    # Tạo 3 biểu đồ và lấy đường dẫn
    plot_paths = {}
    if not recommendations['an_toan_cao'].empty:
        plot_paths['plot_1'] = logic.plot_admission_trends(DATA_FILE, recommendations['an_toan_cao']['Tên trường'].tolist(), "plot_1.png")
    
    if not recommendations['an_toan'].empty:
        plot_paths['plot_2'] = logic.plot_admission_trends(DATA_FILE, recommendations['an_toan']['Tên trường'].tolist(), "plot_2.png")

    if not recommendations['nguy_co_giam'].empty:
        plot_paths['plot_3'] = logic.plot_admission_trends(DATA_FILE, recommendations['nguy_co_giam']['Tên trường'].tolist(), "plot_3.png")

    return {"recommendations": recommendations, "plot_paths": plot_paths}, message

def render_results(content):
    """
    Hàm này nhận một Đối tượng kết quả từ st.session_state.messages
    và hiển thị nó (bảng, biểu đồ, v.v.)
    """
    recommendations = content["recommendations"]
    plot_paths = content["plot_paths"]
    
    df_ma_1 = recommendations['an_toan_cao']
    df_ma_2 = recommendations['an_toan']
    df_ma_3 = recommendations['nguy_co_giam']
    
    # --- Hiển thị Nhóm 1 ---
    st.subheader("Nhóm 1: 🎯 An Toàn Cao (Điểm cao hơn, xu hướng giảm)")
    if df_ma_1.empty: 
        st.info("Không tìm thấy trường nào trong nhóm này.")
    else:
        df_ma_1 = df_ma_1.reset_index(drop=True); df_ma_1.index += 1
        if 'Đối tượng' in df_ma_1.columns:
            df_ma_1.rename(columns={'Đối tượng': 'Tên trường'}, inplace=True)
        st.dataframe(df_ma_1)
        if 'plot_1' in plot_paths: st.image(plot_paths['plot_1'], caption="Biểu đồ 5 trường Top đầu Nhóm 1")
    
    # --- Hiển thị Nhóm 2 ---
    st.subheader("Nhóm 2: 👍 An Toàn (Điểm cao hơn, xu hướng tăng/ổn định)")
    if df_ma_2.empty: 
        st.info("Không tìm thấy trường nào trong nhóm này.")
    else:
        df_ma_2 = df_ma_2.reset_index(drop=True); df_ma_2.index += 1
        if 'Đối tượng' in df_ma_2.columns:
            df_ma_2.rename(columns={'Đối tượng': 'Tên trường'}, inplace=True)
        st.dataframe(df_ma_2)
        if 'plot_2' in plot_paths: st.image(plot_paths['plot_2'], caption="Biểu đồ 5 trường Top đầu Nhóm 2")

    # --- Hiển thị Nhóm 3 ---
    st.subheader("Nhóm 3: ⚠️ Nguy Cơ (Điểm thấp hơn, nhưng xu hướng giảm)")
    if df_ma_3.empty: 
        st.info("Không tìm thấy trường nào trong nhóm này.")
    else:
        df_ma_3 = df_ma_3.reset_index(drop=True); df_ma_3.index += 1
        if 'Đối tượng' in df_ma_3.columns:
            df_ma_3.rename(columns={'Đối tượng': 'Tên trường'}, inplace=True)
        st.dataframe(df_ma_3)
        if 'plot_3' in plot_paths: st.image(plot_paths['plot_3'], caption="Biểu đồ 5 trường Top đầu Nhóm 3")


# ===================================================================
# XÂY DỰNG GIAO DIỆN CHATBOT (UI)
# ===================================================================

st.set_page_config(page_title="Chatbot Tư vấn Tuyển sinh", layout="wide")
st.title("🤖 Chatbot Tư vấn Tuyển sinh (Phiên bản Hội thoại)")

if st.button("Xóa toàn bộ lịch sử trò chuyện"):
    st.session_state.messages = []      
    st.session_state.user_scores = {}   
    st.session_state.step = "start"    
    st.rerun() 

st.markdown("---")

# 1. Chạy xử lý dữ liệu (từ Google Sheets)
success, message = run_data_processing()
if not success:
    st.error(message) 
    st.stop()

# 2. Khởi tạo bộ nhớ (session_state)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_scores" not in st.session_state:
    st.session_state.user_scores = {}
if "step" not in st.session_state:
    st.session_state.step = "start"

# 3. Hiển thị lịch sử chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("type") == "results":
            render_results(message["content"])
        else:
            st.write(message["content"])

# 4. Gửi câu hỏi đầu tiên
# (Chỉ gửi nếu là lần đầu và chưa có tin nhắn nào)
if st.session_state.step == "start" and not st.session_state.messages:
    next_step, question = get_next_question()
    st.session_state.step = next_step
    add_assistant_message(question)
    # Tải lại 1 lần để hiển thị tin nhắn đầu tiên
    st.rerun()

# 5. Xử lý input của người dùng
if prompt := st.chat_input("Nhập điểm số hoặc câu trả lời..."):
    # Thêm tin nhắn của USER vào bộ nhớ VÀ hiển thị
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})

    # Xử lý "Bắt đầu lại"
    if prompt.lower() == "bắt đầu lại":
        st.session_state.user_scores = {}
        st.session_state.step = "start"
        next_step, question = get_next_question()
        st.session_state.step = next_step
        add_assistant_message(question)
        st.rerun() 

    current_step = st.session_state.step
    
    # --- XỬ LÝ LUỒNG HỘI THOẠI ---
    
    # Bước 1-4: Hỏi điểm
    if current_step in ["ask_van", "ask_toan", "ask_anh", "ask_tb_4nam"]:
        is_valid, score = is_valid_score(prompt)
        if is_valid:
            score_key = current_step[4:] 
            st.session_state.user_scores[score_key] = score
            next_step, question = get_next_question()
            st.session_state.step = next_step
            add_assistant_message(question)
        else:
            add_assistant_message("Điểm không hợp lệ. Vui lòng nhập một số từ 0 đến 10.")

    # Bước 5: Hỏi điểm ưu tiên
    elif current_step == "ask_uu_tien":
        is_valid, score = is_valid_score(prompt, 0.0, 5.0)
        if is_valid:
            st.session_state.user_scores['uu_tien'] = score
            next_step, question = get_next_question()
            st.session_state.step = next_step
            add_assistant_message(question)
        else:
            add_assistant_message("Điểm không hợp lệ. Vui lòng nhập một số (nếu không có, nhập 0).")

    # Bước 6: Hỏi môn chuyên
    elif current_step == "ask_chuyen_subject":
        mon_chuyen_normalized = normalize_text(prompt)
        if mon_chuyen_normalized in NORMALIZED_KHO_LIST:
            st.session_state.user_scores['mon_chuyen'] = None
            st.session_state.user_scores['diem_mon_chuyen'] = 0.0
            st.session_state.step = "calculate" 
        elif mon_chuyen_normalized in MON_CHUYEN_MAP:
            correct_mon_chuyen = MON_CHUYEN_MAP[mon_chuyen_normalized]
            st.session_state.user_scores['mon_chuyen'] = correct_mon_chuyen
            next_step, question = get_next_question()
            st.session_state.step = next_step
            add_assistant_message(question)
        else:
            add_assistant_message(f"Không nhận diện được môn chuyên. Vui lòng gõ lại tên môn hoặc gõ 'Không'.")

    # Bước 7: Hỏi điểm chuyên
    elif current_step == "ask_chuyen_score":
        is_valid, score = is_valid_score(prompt)
        if is_valid:
            st.session_state.user_scores['diem_mon_chuyen'] = score
            st.session_state.step = "calculate"
        else:
            add_assistant_message("Điểm không hợp lệ. Vui lòng nhập điểm môn chuyên (từ 0 đến 10).")

    # --- XỬ LÝ TÍNH TOÁN ---
    if st.session_state.step == "calculate":
        with st.chat_message("assistant"):
            with st.spinner("Đang phân tích 3 nhóm đề xuất..."):
                results, message = run_calculation(st.session_state.user_scores)
        
        if results is None:
            add_assistant_message(message)
        else:
            # Hiển thị tin nhắn tùy chỉnh của bạn TRƯỚC
            add_assistant_message(message)
            
            # LƯU KẾT QUẢ (Bảng/Biểu đồ) vào bộ nhớ
            st.session_state.messages.append({
                "role": "assistant",
                "type": "results", 
                "content": results
            })
            
            # Thêm tin nhắn kết thúc
            add_assistant_message("Cuộc tư vấn đã kết thúc. Gõ 'Bắt đầu lại' để nhập điểm mới.")

        # Reset bộ nhớ điểm
        st.session_state.user_scores = {}
        st.session_state.step = "start" 
        
    # Tải lại trang sau mỗi lần xử lý input

    st.rerun()
