# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 시스템
- 로그인 기능
- 서비스별 지침서 관리
- 페이지 수 설정 (목차별 자동 분할 호출)
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import io
from datetime import datetime

# ============================================
# 설정값
# ============================================

ADMIN_ID = "wolsam"
ADMIN_PW = "1113"

DATA_DIR = "data"
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

COVER_IMAGE = "cover_bg.jpg"
PAGE_IMAGE = "page_bg.jpg"

SERVICE_TYPES = ["사주", "연애", "타로"]

# PDF 설정 (페이지 수 조절용)
PDF_FONT_SIZE = 14  # 폰트 크기
PDF_LINE_HEIGHT = 24  # 행간
PDF_MARGIN = 65  # 여백
CHARS_PER_PAGE = 800  # 페이지당 예상 글자 수

# ============================================
# 데이터 저장/불러오기
# ============================================

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_default_guides():
    """세분화된 기본 목차"""
    return {
        "사주": {
            "목차": [
                "1장. 사주 원국 분석",
                "2장. 타고난 기질과 성향",
                "3장. 성격의 장점",
                "4장. 성격의 단점과 보완점",
                "5장. 대인관계 성향",
                "6장. 재물운 총론",
                "7장. 재물 획득 방법",
                "8장. 투자와 재테크",
                "9장. 직업운 총론",
                "10장. 적합한 직업군",
                "11장. 직장 vs 사업 분석",
                "12장. 건강운 총론",
                "13장. 주의해야 할 질병",
                "14장. 건강 관리 조언",
                "15장. 연애운과 이상형",
                "16장. 결혼운과 배우자",
                "17장. 부부 관계 조언",
                "18장. 1월~3월 운세",
                "19장. 4월~6월 운세",
                "20장. 7월~9월 운세",
                "21장. 10월~12월 운세",
                "22장. 내년 운세 전망",
                "23장. 5년 대운 흐름",
                "24장. 행운의 방향과 색상",
                "25장. 종합 조언과 마무리"
            ],
            "지침": """[사주 풀이 지침서]

당신은 30년 경력의 사주명리학 대가입니다.
고객의 사주 원국을 분석하여 상세하고 따뜻한 풀이를 제공합니다.

[작성 원칙]
1. 전문적이면서도 이해하기 쉬운 설명
2. 구체적인 예시와 실천 가능한 조언
3. 희망적이고 긍정적인 톤 유지
4. 요청받은 분량을 반드시 채울 것

[포함 내용]
- 오행 분석과 균형
- 십성 해석
- 운의 흐름과 시기
- 실생활 적용 방안
"""
        },
        "연애": {
            "목차": [
                "1장. 연애 운명 총론",
                "2장. 타고난 연애 성향",
                "3장. 사랑의 표현 방식",
                "4장. 이상형 분석",
                "5장. 끌리는 타입",
                "6장. 피해야 할 타입",
                "7장. 연애 강점",
                "8장. 연애 약점과 보완",
                "9장. 첫 만남과 썸 단계",
                "10장. 연애 초기 전략",
                "11장. 관계 발전 단계",
                "12장. 갈등과 화해",
                "13장. 장거리/권태기 극복",
                "14장. 결혼 적합성",
                "15장. 결혼 최적 시기",
                "16장. 배우자로서의 모습",
                "17장. 올해 연애운",
                "18장. 월별 연애 운세",
                "19장. 인연을 만나는 장소",
                "20장. 연애 성공 전략"
            ],
            "지침": """[연애 풀이 지침서]

당신은 20년 경력의 연애/궁합 전문가입니다.
고객의 연애 운명을 분석하여 실질적인 조언을 제공합니다.

[작성 원칙]
1. 공감가는 따뜻한 톤
2. 구체적인 연애 상황 예시
3. 실천 가능한 연애 조언
4. 희망적인 메시지

[포함 내용]
- 연애 성향 분석
- 이상형과 궁합
- 시기별 연애운
- 관계 발전 전략
"""
        },
        "타로": {
            "목차": [
                "1장. 타로 리딩 개요",
                "2장. 현재 상황 분석",
                "3장. 과거의 영향",
                "4장. 숨겨진 내면",
                "5장. 외부 환경 요인",
                "6장. 주변 인물 영향",
                "7장. 장애물과 도전",
                "8장. 극복 방안",
                "9장. 희망과 두려움",
                "10장. 가까운 미래",
                "11장. 중장기 전망",
                "12장. 최종 결과",
                "13장. 카드가 주는 조언",
                "14장. 실천 가이드",
                "15장. 종합 메시지"
            ],
            "지침": """[타로 해석 지침서]

당신은 15년 경력의 타로 마스터입니다.
카드의 상징과 메시지를 깊이 있게 해석합니다.

[작성 원칙]
1. 신비롭고 통찰력 있는 해석
2. 구체적인 상황 적용
3. 실천 가능한 조언
4. 균형 잡힌 시각

[포함 내용]
- 카드 상징 해석
- 현재 상황 분석
- 미래 전망
- 실천 조언
"""
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
                for key in default_settings:
                    if key not in saved:
                        saved[key] = default_settings[key]
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
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(attachment_buffer.getvalue())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(attachment)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)
        server.quit()
        
        return True, "발송 성공"
    except Exception as e:
        return False, str(e)

# ============================================
# GPT API 호출 (목차별 + 파트별 분할)
# ============================================

def generate_chapter_part(client, model, customer_data, chapter_title, part_num, total_parts, target_chars, guide, service_type):
    """챕터의 각 파트 생성"""
    
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items() if pd.notna(value) and str(value).strip()])
    
    if total_parts == 1:
        part_instruction = f"이 챕터를 약 {target_chars}자 분량으로 상세하게 작성해주세요."
    else:
        part_instruction = f"""이 챕터는 총 {total_parts}개 파트로 나뉩니다.
현재는 파트 {part_num}/{total_parts}을 작성해주세요.
이 파트를 약 {target_chars}자 분량으로 상세하게 작성해주세요.

파트 {part_num} 작성 시:
- 파트 1이면: 챕터 도입부와 전반부 내용
- 중간 파트면: 핵심 내용과 상세 분석
- 마지막 파트면: 심화 내용과 마무리"""

    prompt = f"""당신은 {service_type} 분야 최고 전문가입니다.

[고객 정보]
{customer_info}

[서비스 유형]
{service_type}

[작성 지침]
{guide}

[현재 작성할 챕터]
{chapter_title}

[분량 지시]
{part_instruction}

[중요 규칙]
1. 반드시 {target_chars}자 이상 작성하세요.
2. 내용을 풍부하게, 예시를 많이 들어주세요.
3. 일반적인 내용이 아닌, 고객 맞춤형 내용으로 작성하세요.
4. 절대 분량을 줄이지 마세요. 요청한 글자 수를 꼭 채우세요.
5. 문단을 나누어 읽기 쉽게 작성하세요.
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"당신은 {service_type} 분야 30년 경력 전문가입니다. 요청받은 분량을 반드시 채워서 상세하게 작성합니다. 절대 짧게 쓰지 않습니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.75
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[오류 발생: {str(e)}]"

def generate_full_content(client, model, customer_data, chapters, total_pages, guide, service_type, progress_callback=None):
    """전체 콘텐츠 생성 (목차별 + 파트별 분할)"""
    
    # 목표 글자 수 계산
    total_chars_needed = total_pages * CHARS_PER_PAGE
    chars_per_chapter = total_chars_needed // len(chapters)
    
    # 한 번 GPT 호출로 약 2500자 생성 가능
    chars_per_call = 2500
    parts_per_chapter = max(1, chars_per_chapter // chars_per_call)
    
    full_content = []
    total_calls = len(chapters) * parts_per_chapter
    current_call = 0
    
    for chapter in chapters:
        chapter_content_parts = []
        
        for part in range(1, parts_per_chapter + 1):
            current_call += 1
            
            if progress_callback:
                progress = current_call / total_calls
                progress_callback(progress, f"'{chapter}' 파트 {part}/{parts_per_chapter} 작성 중... ({current_call}/{total_calls})")
            
            part_content = generate_chapter_part(
                client, model, customer_data,
                chapter, part, parts_per_chapter,
                chars_per_call, guide, service_type
            )
            chapter_content_parts.append(part_content)
        
        # 파트들을 합쳐서 하나의 챕터로
        full_chapter_content = "\n\n".join(chapter_content_parts)
        
        full_content.append({
            "title": chapter,
            "content": full_chapter_content
        })
    
    return full_content

# ============================================
# PDF 생성 (표지 → 목차 → 본문)
# ============================================

def create_pdf_with_toc(chapters_content, customer_name, service_type, customer_name2=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
        font_name = 'NanumGothic'
    except:
        font_name = 'Helvetica'
    
    # ============ 1. 표지 ============
    if os.path.exists(COVER_IMAGE):
        try:
            c.drawImage(COVER_IMAGE, 0, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
        except:
            pass
    
    c.setFont(font_name, 28)
    if service_type == "연애" and customer_name2:
        name_text = f"{customer_name}  ♥  {customer_name2}"
    else:
        name_text = f"{customer_name} 님"
    
    text_width = c.stringWidth(name_text, font_name, 28)
    c.drawString((width - text_width) / 2, height * 0.22, name_text)
    c.showPage()
    
    # ============ 2. 목차 ============
    if os.path.exists(PAGE_IMAGE):
        try:
            c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
        except:
            pass
    
    c.setFont(font_name, 24)
    title_text = "목 차"
    title_width = c.stringWidth(title_text, font_name, 24)
    c.drawString((width - title_width) / 2, height - 100, title_text)
    
    c.setFont(font_name, 13)
    toc_y = height - 160
    
    for i, chapter in enumerate(chapters_content):
        chapter_title = chapter['title']
        c.drawString(70, toc_y, chapter_title)
        toc_y -= 28
        
        if toc_y < 80:
            c.showPage()
            if os.path.exists(PAGE_IMAGE):
                try:
                    c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
                except:
                    pass
            toc_y = height - 80
    
    c.showPage()
    
    # ============ 3. 본문 ============
    margin_left = PDF_MARGIN
    margin_right = PDF_MARGIN
    margin_top = 75
    margin_bottom = 75
    line_height = PDF_LINE_HEIGHT
    font_size = PDF_FONT_SIZE
    max_width = width - margin_left - margin_right
    
    for chapter in chapters_content:
        # 챕터 시작 - 새 페이지
        if os.path.exists(PAGE_IMAGE):
            try:
                c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
            except:
                pass
        
        current_y = height - margin_top
        
        # 챕터 제목
        c.setFont(font_name, 18)
        c.drawString(margin_left, current_y, chapter['title'])
        current_y -= 45
        
        # 본문
        c.setFont(font_name, font_size)
        
        content = chapter['content']
        paragraphs = content.split('\n')
        
        for para in paragraphs:
            para = para.strip()
            
            if not para:
                current_y -= 12
                continue
            
            # 소제목 처리 (**, ##, 숫자. 등으로 시작)
            is_subheading = para.startswith('**') or para.startswith('##') or (len(para) < 40 and para[0].isdigit())
            
            if is_subheading:
                current_y -= 10
                c.setFont(font_name, font_size + 1)
                para = para.replace('**', '').replace('##', '').strip()
            else:
                c.setFont(font_name, font_size)
            
            # 텍스트 줄바꿈 처리
            words = para
            while words:
                if current_y < margin_bottom:
                    c.showPage()
                    if os.path.exists(PAGE_IMAGE):
                        try:
                            c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
                        except:
                            pass
                    current_y = height - margin_top
                    c.setFont(font_name, font_size)
                
                if c.stringWidth(words, font_name, font_size) <= max_width:
                    c.drawString(margin_left, current_y, words)
                    current_y -= line_height
                    break
                else:
                    cut = len(words)
                    while cut > 0 and c.stringWidth(words[:cut], font_name, font_size) > max_width:
                        cut -= 1
                    
                    # 단어 중간 자르기 방지 (한글은 글자 단위로)
                    if cut > 10:
                        space = words[:cut].rfind(' ')
                        comma = words[:cut].rfind(',')
                        period = words[:cut].rfind('.')
                        best_cut = max(space, comma, period)
                        if best_cut > cut * 0.5:
                            cut = best_cut + 1
                    
                    c.drawString(margin_left, current_y, words[:cut])
                    current_y -= line_height
                    words = words[cut:].strip()
            
            if is_subheading:
                current_y -= 5
        
        # 챕터 끝나면 새 페이지
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer

# ============================================
# 로그인 화면
# ============================================

def show_login_page():
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
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🔮 PDF 자동 생성 시스템")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.markdown("---")
    
    if 'settings' not in st.session_state:
        st.session_state.settings = load_settings()
    
    if "guides" not in st.session_state.settings:
        st.session_state.settings["guides"] = get_default_guides()
    
    tab1, tab2, tab3 = st.tabs(["📝 지침서 관리", "📄 PDF 생성", "⚙️ 설정"])
    
    # ============ 탭 1: 지침서 관리 ============
    with tab1:
        st.header("📝 서비스별 지침서 관리")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_service = st.selectbox("📌 서비스 선택", SERVICE_TYPES, key="guide_service")
        
        st.markdown("---")
        
        guides = st.session_state.settings["guides"]
        if selected_service not in guides:
            guides[selected_service] = get_default_guides()[selected_service]
        
        current_guide = guides[selected_service]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📚 목차 구성")
            st.info("📌 목차가 많을수록 더 많은 페이지 생성!")
            
            chapters = current_guide.get("목차", [])
            chapters_text = st.text_area(
                "목차 (한 줄에 하나씩)",
                value="\n".join(chapters),
                height=400,
                help="각 줄이 하나의 챕터가 됩니다. 25~30개 권장!"
            )
            new_chapters = [ch.strip() for ch in chapters_text.split("\n") if ch.strip()]
            
            st.caption(f"현재 목차 수: **{len(new_chapters)}개**")
        
        with col2:
            st.subheader("📋 작성 지침")
            st.info("GPT가 따를 지침을 상세히 작성하세요.")
            
            guide_text = st.text_area(
                "지침 내용",
                value=current_guide.get("지침", ""),
                height=400,
                help="톤, 스타일, 포함할 내용 등"
            )
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 저장", type="primary", use_container_width=True):
                st.session_state.settings["guides"][selected_service] = {
                    "목차": new_chapters,
                    "지침": guide_text
                }
                save_settings(st.session_state.settings)
                st.success(f"✅ {selected_service} 지침서 저장 완료!")
        
        with col2:
            if st.button("🔄 기본값 복원", use_container_width=True):
                st.session_state.settings["guides"][selected_service] = get_default_guides()[selected_service]
                save_settings(st.session_state.settings)
                st.rerun()
    
    # ============ 탭 2: PDF 생성 ============
    with tab2:
        st.header("📄 PDF 생성")
        
        api_key_exists = st.session_state.settings.get("api_key")
        
        if not api_key_exists:
            st.warning("⚠️ 먼저 '설정' 탭에서 OpenAI API 키를 입력해주세요!")
        
        st.subheader("🎯 생성 설정")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pdf_service = st.selectbox("📌 서비스", SERVICE_TYPES, key="pdf_service")
        
        with col2:
            total_pages = st.number_input(
                "📖 페이지 수",
                min_value=20,
                max_value=300,
                value=100,
                step=10
            )
        
        with col3:
            # 현재 목차 수 표시
            guides = st.session_state.settings.get("guides", {})
            current_chapters = guides.get(pdf_service, {}).get("목차", [])
            st.metric("📚 목차 수", f"{len(current_chapters)}개")
        
        with col4:
            auto_email = st.checkbox("📧 이메일 발송", value=True)
        
        # 예상 정보 표시
        parts_per_ch = max(1, (total_pages * CHARS_PER_PAGE // len(current_chapters)) // 2500) if current_chapters else 1
        total_api_calls = len(current_chapters) * parts_per_ch
        estimated_cost = total_api_calls * 0.02  # 대략적 비용
        
        st.info(f"📊 예상: 목차당 {parts_per_ch}회 × {len(current_chapters)}개 = **총 {total_api_calls}회 API 호출** (예상 비용: ${estimated_cost:.2f})")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if os.path.exists(COVER_IMAGE):
                st.success("✅ 표지 이미지 있음")
            else:
                st.warning("⚠️ cover_bg.jpg 없음")
        with col2:
            if os.path.exists(PAGE_IMAGE):
                st.success("✅ 본문 배경 있음")
            else:
                st.warning("⚠️ page_bg.jpg 없음")
        
        st.markdown("---")
        st.subheader("📊 고객 정보 업로드")
        
        uploaded_file = st.file_uploader("엑셀 파일 선택", type=["xlsx", "csv"])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ {len(df)}명 로드 완료!")
                
                with st.expander("📋 데이터 미리보기", expanded=True):
                    st.dataframe(df, use_container_width=True)
                
                st.markdown("---")
                st.subheader("🔗 컬럼 매핑")
                
                columns = df.columns.tolist()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    name_col = st.selectbox("이름 컬럼", columns)
                with col2:
                    name2_col = st.selectbox("이름2 (궁합용)", ["없음"] + columns)
                with col3:
                    email_col = st.selectbox("이메일 컬럼", ["없음"] + columns)
                
                st.markdown("---")
                
                selected_rows = st.multiselect(
                    "생성할 고객 선택 (비우면 전체)",
                    options=df.index.tolist(),
                    format_func=lambda x: f"{x+1}. {df.iloc[x][name_col]}"
                )
                
                if not selected_rows:
                    selected_rows = df.index.tolist()
                
                st.info(f"📌 {len(selected_rows)}명 × {total_pages}페이지 PDF 생성 예정")
                
                if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True, disabled=not api_key_exists):
                    
                    client = OpenAI(api_key=st.session_state.settings["api_key"])
                    model = st.session_state.settings.get("model", "gpt-4o-mini")
                    
                    guides = st.session_state.settings["guides"]
                    if pdf_service not in guides:
                        guides[pdf_service] = get_default_guides()[pdf_service]
                    
                    current_guide = guides[pdf_service]
                    chapters = current_guide.get("목차", ["총운"])
                    guide_text = current_guide.get("지침", "")
                    
                    gmail_address = st.session_state.settings.get("gmail_address", "")
                    gmail_password = st.session_state.settings.get("gmail_app_password", "")
                    
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        customer_name = str(row[name_col])
                        customer_name2 = str(row[name2_col]) if name2_col != "없음" and pd.notna(row.get(name2_col)) else None
                        customer_email = str(row[email_col]) if email_col != "없음" and pd.notna(row.get(email_col)) else None
                        
                        st.markdown(f"### 📝 {customer_name} 님 처리 중...")
                        
                        customer_data = row.to_dict()
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(progress, status):
                            progress_bar.progress(progress)
                            status_text.text(status)
                        
                        chapters_content = generate_full_content(
                            client, model, customer_data,
                            chapters, total_pages,
                            guide_text, pdf_service,
                            update_progress
                        )
                        
                        status_text.text("📄 PDF 생성 중...")
                        pdf_buffer = create_pdf_with_toc(
                            chapters_content,
                            customer_name,
                            pdf_service,
                            customer_name2
                        )
                        
                        if pdf_service == "연애" and customer_name2:
                            filename = f"{customer_name}_{customer_name2}_{pdf_service}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        else:
                            filename = f"{customer_name}_{pdf_service}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        
                        if auto_email and customer_email and gmail_address and gmail_password:
                            status_text.text("📧 이메일 발송 중...")
                            
                            email_subject = f"[{pdf_service}] {customer_name}님의 감정서가 도착했습니다"
                            email_body = f"""안녕하세요, {customer_name}님!

요청하신 {pdf_service} 감정서를 보내드립니다.
첨부된 PDF 파일을 확인해주세요.

감사합니다.
"""
                            
                            pdf_buffer.seek(0)
                            success, message = send_email_with_attachment(
                                customer_email, email_subject, email_body,
                                pdf_buffer, filename, gmail_address, gmail_password
                            )
                            
                            if success:
                                st.success(f"📧 {customer_email} 발송 완료!")
                            else:
                                st.warning(f"📧 발송 실패: {message}")
                            
                            pdf_buffer.seek(0)
                        
                        st.download_button(
                            f"📥 {filename}",
                            pdf_buffer,
                            filename,
                            "application/pdf",
                            key=f"dl_{idx}"
                        )
                        
                        st.success(f"✅ {customer_name} 님 완료!")
                        st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 오류: {str(e)}")
    
    # ============ 탭 3: 설정 ============
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
                value=st.session_state.settings.get("gmail_address", "")
            )
            
            gmail_password = st.text_input(
                "앱 비밀번호",
                value=st.session_state.settings.get("gmail_app_password", ""),
                type="password"
            )
            
            with st.expander("📌 앱 비밀번호 발급 방법"):
                st.markdown("""
                1. Google 계정 → 보안 → 2단계 인증 활성화
                2. https://myaccount.google.com/apppasswords 접속
                3. 앱 이름 입력 후 생성
                4. 16자리 비밀번호 복사하여 입력
                """)
        
        st.markdown("---")
        
        if st.button("💾 설정 저장", type="primary"):
            st.session_state.settings["api_key"] = api_key
            st.session_state.settings["model"] = model
            st.session_state.settings["gmail_address"] = gmail_address
            st.session_state.settings["gmail_app_password"] = gmail_password
            save_settings(st.session_state.settings)
            st.success("✅ 설정 저장 완료!")

# ============================================
# 메인 실행
# ============================================

def main():
    st.set_page_config(
        page_title="PDF 자동 생성 시스템",
        page_icon="🔮",
        layout="wide"
    )
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
