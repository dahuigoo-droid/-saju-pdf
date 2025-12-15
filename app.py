# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 시스템
- 로그인 기능
- 서비스별 지침서 관리
- 페이지 수 설정
- 목차별 GPT 분할 요청
- 이메일 자동 발송
"""

import streamlit as st
import pandas as pd
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import io
from datetime import datetime

# ============================================
# 설정값
# ============================================

# 로그인 정보
ADMIN_ID = "wolsam"
ADMIN_PW = "1113"

# 데이터 저장 경로
DATA_DIR = "data"
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# 이미지 파일
COVER_IMAGE = "cover_bg.jpg"
PAGE_IMAGE = "page_bg.jpg"

# 서비스 종류
SERVICE_TYPES = ["사주", "연애", "타로"]

# ============================================
# 데이터 저장/불러오기
# ============================================

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_default_guides():
    return {
        "사주": {
            "목차": ["총운", "성격분석", "재물운", "직업운", "건강운", "연애운", "년도별운세"],
            "지침": "사주 풀이 지침을 여기에 작성하세요."
        },
        "연애": {
            "목차": ["연애총운", "이상형분석", "연애스타일", "궁합분석", "미래전망"],
            "지침": "연애 풀이 지침을 여기에 작성하세요."
        },
        "타로": {
            "목차": ["현재상황", "장애물", "조언", "미래전망", "종합해석"],
            "지침": "타로 해석 지침을 여기에 작성하세요."
        }
    }

def load_settings():
    ensure_data_dir()
    default_settings = {
        "api_key": "",
        "model": "gpt-4o-mini",
        "gmail_address": "",
        "gmail_app_password": "",
        "guides": get_default_guides()
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # 기본값 병합
                for key in default_settings:
                    if key not in saved:
                        saved[key] = default_settings[key]
                # guides 내부 서비스별 기본값 병합
                if "guides" not in saved:
                    saved["guides"] = get_default_guides()
                else:
                    default_guides = get_default_guides()
                    for service in SERVICE_TYPES:
                        if service not in saved["guides"]:
                            saved["guides"][service] = default_guides[service]
                return saved
        except:
            return default_settings
    return default_settings

def save_settings(settings):
    ensure_data_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ============================================
# 이메일 발송
# ============================================

def send_email_with_attachment(to_email, subject, body, attachment_buffer, filename, gmail_address, gmail_password):
    """Gmail로 PDF 첨부 이메일 발송"""
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # PDF 첨부
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(attachment_buffer.getvalue())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(attachment)
        
        # Gmail SMTP 발송
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)
        server.quit()
        
        return True, "발송 성공"
    except Exception as e:
        return False, str(e)

# ============================================
# GPT API 호출 (목차별 분할)
# ============================================

def generate_chapter_content(client, model, customer_data, chapter_title, chapter_pages, guide, service_type):
    """목차(챕터)별로 GPT 호출"""
    
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items() if pd.notna(value)])
    
    prompt = f"""당신은 20년 경력의 {service_type} 전문가입니다.

[고객 정보]
{customer_info}

[서비스 유형]
{service_type}

[작성 지침]
{guide}

[현재 작성할 챕터]
챕터 제목: {chapter_title}
요청 페이지 수: 약 {chapter_pages}페이지 (A4 기준, 페이지당 약 500자)

위 챕터를 {chapter_pages}페이지 분량으로 상세하게 작성해주세요.
- 총 글자 수: 약 {chapter_pages * 500}자 이상
- 전문적이면서도 이해하기 쉽게
- 구체적인 조언과 예시 포함
- 따뜻하고 희망적인 톤 유지

절대로 분량을 줄이지 말고, 요청한 페이지 수에 맞게 충분히 상세하게 작성하세요.
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"당신은 전문적이고 따뜻한 {service_type} 전문가입니다. 요청받은 분량을 반드시 채워서 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[오류 발생: {str(e)}]"

def generate_full_content(client, model, customer_data, chapters, total_pages, guide, service_type, progress_callback=None):
    """전체 콘텐츠 생성 (목차별 분할 요청)"""
    
    # 페이지 수를 목차별로 분배
    num_chapters = len(chapters)
    pages_per_chapter = max(1, total_pages // num_chapters)
    
    full_content = []
    
    for i, chapter in enumerate(chapters):
        if progress_callback:
            progress_callback((i + 1) / num_chapters, f"'{chapter}' 작성 중... ({i+1}/{num_chapters})")
        
        chapter_content = generate_chapter_content(
            client, model, customer_data, 
            chapter, pages_per_chapter, 
            guide, service_type
        )
        
        full_content.append({
            "title": chapter,
            "content": chapter_content
        })
    
    return full_content

# ============================================
# PDF 생성 (표지 → 목차 → 본문)
# ============================================

def create_pdf_with_toc(chapters_content, customer_name, service_type, customer_name2=None):
    """표지 + 목차 + 본문 PDF 생성"""
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 폰트 등록
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
        font_name = 'NanumGothic'
    except:
        font_name = 'Helvetica'
    
    # ============================================
    # 1. 표지 페이지
    # ============================================
    if os.path.exists(COVER_IMAGE):
        try:
            c.drawImage(COVER_IMAGE, 0, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
        except:
            pass
    
    # 고객 이름 (하단 중앙)
    c.setFont(font_name, 28)
    if service_type == "연애" and customer_name2:
        name_text = f"{customer_name}  ♥  {customer_name2}"
    else:
        name_text = f"{customer_name} 님"
    
    text_width = c.stringWidth(name_text, font_name, 28)
    c.drawString((width - text_width) / 2, height * 0.22, name_text)
    
    c.showPage()
    
    # ============================================
    # 2. 목차 페이지
    # ============================================
    if os.path.exists(PAGE_IMAGE):
        try:
            c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
        except:
            pass
    
    c.setFont(font_name, 24)
    c.drawString(width/2 - 30, height - 100, "목 차")
    
    c.setFont(font_name, 15)
    toc_y = height - 180
    
    for i, chapter in enumerate(chapters_content):
        chapter_title = f"{i+1}. {chapter['title']}"
        c.drawString(80, toc_y, chapter_title)
        toc_y -= 35
        
        if toc_y < 100:
            c.showPage()
            if os.path.exists(PAGE_IMAGE):
                try:
                    c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
                except:
                    pass
            toc_y = height - 100
    
    c.showPage()
    
    # ============================================
    # 3. 본문 페이지들
    # ============================================
    margin_left = 60
    margin_right = 60
    margin_top = 80
    margin_bottom = 80
    line_height = 22  # 폰트 15에 맞춤
    max_width = width - margin_left - margin_right
    
    for chapter in chapters_content:
        # 챕터 시작 페이지
        if os.path.exists(PAGE_IMAGE):
            try:
                c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
            except:
                pass
        
        current_y = height - margin_top
        
        # 챕터 제목
        c.setFont(font_name, 20)
        c.drawString(margin_left, current_y, chapter['title'])
        current_y -= 50
        
        # 챕터 내용
        c.setFont(font_name, 15)
        
        lines = chapter['content'].split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                current_y -= 15
                continue
            
            # 긴 줄 자동 줄바꿈
            while line:
                # 페이지 넘김 체크
                if current_y < margin_bottom:
                    c.showPage()
                    if os.path.exists(PAGE_IMAGE):
                        try:
                            c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
                        except:
                            pass
                    current_y = height - margin_top
                    c.setFont(font_name, 15)
                
                # 한 줄에 들어갈 수 있는 만큼 자르기
                if c.stringWidth(line, font_name, 15) <= max_width:
                    c.drawString(margin_left, current_y, line)
                    current_y -= line_height
                    break
                else:
                    # 적절한 위치에서 자르기
                    cut_point = len(line)
                    while cut_point > 0 and c.stringWidth(line[:cut_point], font_name, 15) > max_width:
                        cut_point -= 1
                    
                    # 단어 중간에서 자르지 않도록
                    space_point = line[:cut_point].rfind(' ')
                    if space_point > cut_point * 0.3:
                        cut_point = space_point
                    
                    c.drawString(margin_left, current_y, line[:cut_point])
                    current_y -= line_height
                    line = line[cut_point:].strip()
        
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer

# ============================================
# 로그인 화면
# ============================================

def show_login_page():
    """로그인 페이지 표시"""
    
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }
    .login-title {
        text-align: center;
        color: white;
        font-size: 28px;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        st.markdown("## 🔮 PDF 자동 생성 시스템")
        st.markdown("### 관리자 로그인")
        st.markdown("---")
        
        user_id = st.text_input("👤 아이디", placeholder="아이디를 입력하세요")
        user_pw = st.text_input("🔒 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        
        st.markdown("")
        
        if st.button("🔐 로그인", type="primary", use_container_width=True):
            if user_id == ADMIN_ID and user_pw == ADMIN_PW:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀렸습니다.")

# ============================================
# 메인 앱 화면
# ============================================

def show_main_app():
    """메인 앱 화면"""
    
    # 헤더
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🔮 PDF 자동 생성 시스템")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.markdown("---")
    
    # 설정 불러오기
    if 'settings' not in st.session_state:
        st.session_state.settings = load_settings()
    
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📝 지침서 관리", "📄 PDF 생성", "⚙️ 설정"])
    
    # ============================================
    # 탭 1: 지침서 관리
    # ============================================
    with tab1:
        st.header("📝 서비스별 지침서 관리")
        
        # 서비스 선택
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_service = st.selectbox(
                "📌 서비스 선택",
                SERVICE_TYPES,
                key="guide_service"
            )
        
        st.markdown("---")
        
        # 현재 서비스의 설정 가져오기
        if "guides" not in st.session_state.settings:
            st.session_state.settings["guides"] = get_default_guides()
        
        guides = st.session_state.settings["guides"]
        
        if selected_service not in guides:
            guides[selected_service] = get_default_guides()[selected_service]
        
        current_guide = guides.get(selected_service, {"목차": [], "지침": ""})
        
        # 목차 관리
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📚 목차 구성")
            st.info("각 목차 항목별로 GPT가 분할 작성합니다.")
            
            # 현재 목차 표시
            chapters = current_guide.get("목차", [])
            
            # 목차 편집
            chapters_text = st.text_area(
                "목차 (한 줄에 하나씩)",
                value="\n".join(chapters),
                height=200,
                help="각 줄이 하나의 챕터가 됩니다"
            )
            
            # 새 목차로 업데이트
            new_chapters = [ch.strip() for ch in chapters_text.split("\n") if ch.strip()]
        
        with col2:
            st.subheader("📋 작성 지침")
            st.info("GPT가 내용을 작성할 때 따를 지침입니다.")
            
            guide_text = st.text_area(
                "지침 내용",
                value=current_guide.get("지침", ""),
                height=200,
                help="톤, 스타일, 포함할 내용 등을 작성하세요"
            )
        
        st.markdown("---")
        
        # 저장 버튼
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 저장", type="primary", use_container_width=True):
                if "guides" not in st.session_state.settings:
                    st.session_state.settings["guides"] = get_default_guides()
                st.session_state.settings["guides"][selected_service] = {
                    "목차": new_chapters,
                    "지침": guide_text
                }
                save_settings(st.session_state.settings)
                st.success(f"✅ {selected_service} 지침서가 저장되었습니다!")
        
        with col2:
            if st.button("🔄 초기화", use_container_width=True):
                if "guides" not in st.session_state.settings:
                    st.session_state.settings["guides"] = get_default_guides()
                st.session_state.settings["guides"][selected_service] = get_default_guides()[selected_service]
                save_settings(st.session_state.settings)
                st.rerun()
    
    # ============================================
    # 탭 2: PDF 생성
    # ============================================
    with tab2:
        st.header("📄 PDF 생성")
        
        # API 키 체크
        if not st.session_state.settings.get("api_key"):
            st.warning("⚠️ 먼저 '설정' 탭에서 OpenAI API 키를 입력해주세요!")
            return
        
        # 상단 설정 영역
        st.subheader("🎯 생성 설정")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pdf_service = st.selectbox(
                "📌 서비스 유형",
                SERVICE_TYPES,
                key="pdf_service"
            )
        
        with col2:
            total_pages = st.number_input(
                "📖 총 페이지 수",
                min_value=10,
                max_value=200,
                value=50,
                step=10,
                help="원하는 PDF 페이지 수"
            )
        
        with col3:
            auto_email = st.checkbox("📧 이메일 자동발송", value=True)
            if auto_email:
                if not st.session_state.settings.get("gmail_address"):
                    st.warning("⚠️ 설정에서 Gmail 정보를 입력하세요")
        
        st.markdown("---")
        
        # 이미지 파일 상태
        col1, col2 = st.columns(2)
        with col1:
            if os.path.exists(COVER_IMAGE):
                st.success(f"✅ 표지 이미지 있음")
            else:
                st.warning(f"⚠️ 표지 이미지 없음 (cover_bg.jpg)")
        with col2:
            if os.path.exists(PAGE_IMAGE):
                st.success(f"✅ 본문 배경 있음")
            else:
                st.warning(f"⚠️ 본문 배경 없음 (page_bg.jpg)")
        
        st.markdown("---")
        
        # 엑셀 업로드
        st.subheader("📊 고객 정보 업로드")
        
        uploaded_file = st.file_uploader(
            "엑셀 파일 선택 (.xlsx, .csv)",
            type=["xlsx", "csv"],
            help="고객 정보가 담긴 엑셀 파일을 업로드하세요"
        )
        
        if uploaded_file:
            try:
                # 파일 읽기
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ {len(df)}명의 고객 정보를 불러왔습니다!")
                
                # 데이터 미리보기
                with st.expander("📋 데이터 미리보기", expanded=True):
                    st.dataframe(df, use_container_width=True)
                
                # 컬럼 매핑
                st.markdown("---")
                st.subheader("🔗 컬럼 매핑")
                
                columns = df.columns.tolist()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    name_col = st.selectbox("이름 컬럼", columns, index=0 if columns else 0)
                with col2:
                    name2_col = st.selectbox("이름2 컬럼 (궁합용)", ["없음"] + columns)
                with col3:
                    email_col = st.selectbox("이메일 컬럼", ["없음"] + columns)
                
                st.markdown("---")
                
                # 생성할 고객 선택
                selected_rows = st.multiselect(
                    "생성할 고객 선택 (비우면 전체)",
                    options=df.index.tolist(),
                    format_func=lambda x: f"{x+1}. {df.iloc[x][name_col]}"
                )
                
                if not selected_rows:
                    selected_rows = df.index.tolist()
                
                st.info(f"📌 {len(selected_rows)}명의 PDF를 생성합니다.")
                
                # 생성 버튼
                if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True):
                    
                    # 설정 가져오기
                    client = OpenAI(api_key=st.session_state.settings["api_key"])
                    model = st.session_state.settings.get("model", "gpt-4o-mini")
                    
                    # guides 안전하게 가져오기
                    if "guides" not in st.session_state.settings:
                        st.session_state.settings["guides"] = get_default_guides()
                    guides = st.session_state.settings["guides"]
                    
                    if pdf_service not in guides:
                        guides[pdf_service] = get_default_guides()[pdf_service]
                    
                    current_guide = guides.get(pdf_service, {})
                    chapters = current_guide.get("목차", ["총운"])
                    guide_text = current_guide.get("지침", "")
                    
                    # Gmail 설정
                    gmail_address = st.session_state.settings.get("gmail_address", "")
                    gmail_password = st.session_state.settings.get("gmail_app_password", "")
                    
                    # 각 고객 처리
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        customer_name = str(row[name_col])
                        customer_name2 = str(row[name2_col]) if name2_col != "없음" and pd.notna(row.get(name2_col)) else None
                        customer_email = str(row[email_col]) if email_col != "없음" and pd.notna(row.get(email_col)) else None
                        
                        st.markdown(f"### 📝 {customer_name} 님 처리 중...")
                        
                        # 고객 데이터
                        customer_data = row.to_dict()
                        
                        # 진행 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(progress, status):
                            progress_bar.progress(progress)
                            status_text.text(status)
                        
                        # GPT로 콘텐츠 생성 (목차별 분할)
                        chapters_content = generate_full_content(
                            client, model, customer_data,
                            chapters, total_pages,
                            guide_text, pdf_service,
                            update_progress
                        )
                        
                        # PDF 생성
                        status_text.text("📄 PDF 변환 중...")
                        pdf_buffer = create_pdf_with_toc(
                            chapters_content,
                            customer_name,
                            pdf_service,
                            customer_name2
                        )
                        
                        # 파일명
                        if pdf_service == "연애" and customer_name2:
                            filename = f"{customer_name}_{customer_name2}_{pdf_service}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        else:
                            filename = f"{customer_name}_{pdf_service}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        
                        # 이메일 발송
                        if auto_email and customer_email and gmail_address and gmail_password:
                            status_text.text("📧 이메일 발송 중...")
                            
                            email_subject = f"[{pdf_service}] {customer_name}님의 감정서가 도착했습니다"
                            email_body = f"""안녕하세요, {customer_name}님!

요청하신 {pdf_service} 감정서를 보내드립니다.
첨부된 PDF 파일을 확인해주세요.

감사합니다.
"""
                            
                            # 버퍼 위치 리셋
                            pdf_buffer.seek(0)
                            
                            success, message = send_email_with_attachment(
                                customer_email,
                                email_subject,
                                email_body,
                                pdf_buffer,
                                filename,
                                gmail_address,
                                gmail_password
                            )
                            
                            if success:
                                st.success(f"📧 {customer_email}로 발송 완료!")
                            else:
                                st.warning(f"📧 발송 실패: {message}")
                            
                            # 버퍼 위치 다시 리셋
                            pdf_buffer.seek(0)
                        
                        # 다운로드 버튼
                        st.download_button(
                            label=f"📥 {filename} 다운로드",
                            data=pdf_buffer,
                            file_name=filename,
                            mime="application/pdf",
                            key=f"download_{idx}"
                        )
                        
                        st.success(f"✅ {customer_name} 님 완료!")
                        st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")
    
    # ============================================
    # 탭 3: 설정
    # ============================================
    with tab3:
        st.header("⚙️ 시스템 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔑 OpenAI API")
            
            api_key = st.text_input(
                "API 키",
                value=st.session_state.settings.get("api_key", ""),
                type="password"
            )
            
            model = st.selectbox(
                "GPT 모델",
                ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
                index=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"].index(
                    st.session_state.settings.get("model", "gpt-4o-mini")
                )
            )
        
        with col2:
            st.subheader("📧 Gmail 설정")
            
            gmail_address = st.text_input(
                "Gmail 주소",
                value=st.session_state.settings.get("gmail_address", ""),
                help="이메일 발송에 사용할 Gmail 주소"
            )
            
            gmail_password = st.text_input(
                "앱 비밀번호",
                value=st.session_state.settings.get("gmail_app_password", ""),
                type="password",
                help="Gmail 앱 비밀번호 (일반 비밀번호 아님!)"
            )
            
            with st.expander("📌 앱 비밀번호 발급 방법"):
                st.markdown("""
                1. Google 계정 → 보안 → 2단계 인증 활성화
                2. Google 계정 → 보안 → 앱 비밀번호
                3. '앱 선택' → '기타' 선택 → 이름 입력
                4. 생성된 16자리 비밀번호를 여기에 입력
                
                [앱 비밀번호 생성 바로가기](https://myaccount.google.com/apppasswords)
                """)
        
        st.markdown("---")
        
        if st.button("💾 설정 저장", type="primary"):
            st.session_state.settings["api_key"] = api_key
            st.session_state.settings["model"] = model
            st.session_state.settings["gmail_address"] = gmail_address
            st.session_state.settings["gmail_app_password"] = gmail_password
            save_settings(st.session_state.settings)
            st.success("✅ 설정이 저장되었습니다!")

# ============================================
# 메인 실행
# ============================================

def main():
    st.set_page_config(
        page_title="PDF 자동 생성 시스템",
        page_icon="🔮",
        layout="wide"
    )
    
    # 로그인 상태 확인
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
