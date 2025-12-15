# -*- coding: utf-8 -*-
"""
사주 PDF 자동 생성 시스템
표지 + 배경 이미지 적용 버전
"""

import streamlit as st
import pandas as pd
import json
import os
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Frame, PageTemplate, BaseDocTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import io
from datetime import datetime

# ============================================
# 데이터 저장/불러오기 함수들
# ============================================

DATA_DIR = "data"
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
GUIDE_FILE = os.path.join(DATA_DIR, "guide.txt")

# 이미지 파일 경로
COVER_IMAGE = "cover_bg.jpg"
PAGE_IMAGE = "page_bg.jpg"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_settings():
    ensure_data_dir()
    default_settings = {
        "api_key": "",
        "columns": [
            {"name": "이름", "description": "고객 이름"},
            {"name": "이름2", "description": "두번째 이름 (궁합용)"},
            {"name": "서비스유형", "description": "일년운세/평생운세/평생+일년운세/궁합"},
            {"name": "성별", "description": "남/여"},
            {"name": "생년월일", "description": "YYYY-MM-DD 형식"},
            {"name": "태어난시간", "description": "HH:MM 형식"},
            {"name": "년주", "description": "예: 乙丑"},
            {"name": "월주", "description": "예: 己卯"},
            {"name": "일주", "description": "예: 丙午"},
            {"name": "시주", "description": "예: 乙未"},
            {"name": "심층정보", "description": "추가 분석 정보"}
        ],
        "model": "gpt-4o-mini"
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for key in default_settings:
                    if key not in saved:
                        saved[key] = default_settings[key]
                return saved
        except:
            return default_settings
    return default_settings

def save_settings(settings):
    ensure_data_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def load_guide():
    ensure_data_dir()
    default_guide = """[사주 풀이 지침서]

아래 지침에 따라 상세하고 전문적인 사주 풀이를 작성해주세요.

1. 총운 (2-3페이지)
- 사주 원국의 전체적인 특징
- 오행의 균형과 조화
- 타고난 기질과 성향

2. 성격 분석 (3-4페이지)
- 일주를 기반으로 한 핵심 성격
- 장점과 단점
- 대인관계 특성

3. 재물운 (3-4페이지)
- 재물을 다루는 성향
- 적합한 재테크 방향
- 주의해야 할 점

4. 직업운 (3-4페이지)
- 적성에 맞는 직업군
- 사업 vs 직장 적합성
- 성공을 위한 조언

5. 건강운 (2-3페이지)
- 주의해야 할 신체 부위
- 건강 관리 조언

6. 연애운/결혼운 (3-4페이지)
- 이상적인 배우자상
- 결혼 시기와 방향
- 부부 관계 조언

7. 년도별 운세 (5-10페이지)
- 향후 5년간의 운세 흐름
- 각 년도별 주요 포인트

[작성 스타일]
- 따뜻하고 희망적인 톤 유지
- 전문 용어는 쉽게 풀어서 설명
- 구체적인 조언 포함
"""
    
    if os.path.exists(GUIDE_FILE):
        try:
            with open(GUIDE_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return default_guide
    return default_guide

def save_guide(guide_text):
    ensure_data_dir()
    with open(GUIDE_FILE, "w", encoding="utf-8") as f:
        f.write(guide_text)

# ============================================
# GPT API 호출 함수
# ============================================

def generate_saju_reading(client, customer_data, guide, model):
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items()])
    
    prompt = f"""당신은 30년 경력의 사주명리학 전문가입니다.

[고객 정보]
{customer_info}

[풀이 지침]
{guide}

위 지침에 따라 이 고객을 위한 상세한 사주 풀이를 작성해주세요.
각 섹션은 충분히 상세하게 작성하고, 고객의 원국 특성에 맞는 맞춤형 조언을 제공해주세요.
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 전문적이고 따뜻한 사주명리학 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=16000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"오류 발생: {str(e)}"

def generate_saju_sections(client, customer_data, guide, model, service_type, progress_callback=None):
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items()])
    
    # 서비스 유형별 섹션 구성
    if service_type == "궁합":
        sections = [
            ("궁합 총론", "두 사람의 사주 궁합 전체 분석, 천생연분 여부를 5페이지 분량으로"),
            ("성격 궁합", "두 사람의 성격 조화, 충돌 포인트를 4페이지 분량으로"),
            ("애정운 궁합", "연애 스타일, 사랑의 방식 궁합을 4페이지 분량으로"),
            ("결혼 궁합", "결혼 후 가정생활, 배우자로서의 궁합을 5페이지 분량으로"),
            ("재물 궁합", "함께할 때의 재물운, 경제적 궁합을 4페이지 분량으로"),
            ("자녀운", "두 사람의 자녀운, 육아 스타일을 3페이지 분량으로"),
            ("위기와 극복", "예상되는 갈등과 극복 방안을 4페이지 분량으로"),
            ("종합 조언", "행복한 관계를 위한 조언을 3페이지 분량으로")
        ]
    elif service_type == "일년운세":
        current_year = datetime.now().year
        sections = [
            (f"{current_year}년 총운", f"{current_year}년 전체 운세 흐름을 5페이지 분량으로"),
            (f"{current_year}년 월별운세 (1-4월)", "1월부터 4월까지 월별 상세 운세를 5페이지 분량으로"),
            (f"{current_year}년 월별운세 (5-8월)", "5월부터 8월까지 월별 상세 운세를 5페이지 분량으로"),
            (f"{current_year}년 월별운세 (9-12월)", "9월부터 12월까지 월별 상세 운세를 5페이지 분량으로"),
            (f"{current_year}년 재물운", "올해의 재물운과 투자 시기를 4페이지 분량으로"),
            (f"{current_year}년 직업운", "올해의 직업운과 이직/승진 시기를 4페이지 분량으로"),
            (f"{current_year}년 건강운", "올해 주의할 건강 사항을 3페이지 분량으로"),
            (f"{current_year}년 연애운", "올해의 연애운과 좋은 시기를 3페이지 분량으로"),
            ("올해의 행운 포인트", "행운의 방향, 색상, 숫자 등을 2페이지 분량으로")
        ]
    elif service_type == "평생운세":
        sections = [
            ("타고난 운명", "사주 원국 분석, 타고난 기질과 운명을 5페이지 분량으로"),
            ("성격과 심리", "일주 기반 성격 심층 분석을 5페이지 분량으로"),
            ("평생 재물운", "일생의 재물 흐름과 부의 시기를 5페이지 분량으로"),
            ("평생 직업운", "천직과 성공 분야, 커리어 흐름을 5페이지 분량으로"),
            ("평생 건강운", "체질과 주의 질병, 건강 관리법을 4페이지 분량으로"),
            ("연애와 결혼운", "배우자상, 결혼 시기, 결혼 생활을 5페이지 분량으로"),
            ("대운 분석 (초년)", "1세-30세 운의 흐름을 4페이지 분량으로"),
            ("대운 분석 (중년)", "31세-60세 운의 흐름을 4페이지 분량으로"),
            ("대운 분석 (말년)", "61세 이후 운의 흐름을 3페이지 분량으로"),
            ("인생 조언", "행복한 삶을 위한 종합 조언을 3페이지 분량으로")
        ]
    else:  # 평생+일년운세
        current_year = datetime.now().year
        sections = [
            ("타고난 운명", "사주 원국 분석, 타고난 기질과 운명을 5페이지 분량으로"),
            ("성격과 심리", "일주 기반 성격 심층 분석을 4페이지 분량으로"),
            ("평생 재물운", "일생의 재물 흐름과 부의 시기를 4페이지 분량으로"),
            ("평생 직업운", "천직과 성공 분야를 4페이지 분량으로"),
            ("평생 건강운", "체질과 건강 관리법을 3페이지 분량으로"),
            ("연애와 결혼운", "배우자상과 결혼 생활을 4페이지 분량으로"),
            ("대운 흐름", "일생의 대운 흐름 요약을 4페이지 분량으로"),
            (f"{current_year}년 총운", f"{current_year}년 전체 운세를 4페이지 분량으로"),
            (f"{current_year}년 월별운세", "올해 월별 운세를 5페이지 분량으로"),
            (f"{current_year}년 행운 포인트", "올해 행운의 방향과 조언을 3페이지 분량으로")
        ]
    
    full_content = []
    
    for i, (section_title, section_desc) in enumerate(sections):
        if progress_callback:
            progress_callback(i / len(sections), f"'{section_title}' 생성 중...")
        
        prompt = f"""당신은 30년 경력의 사주명리학 전문가입니다.

[고객 정보]
{customer_info}

[서비스 유형]
{service_type}

[전체 풀이 지침 참고]
{guide}

[현재 작성할 섹션]
섹션 제목: {section_title}
요청 사항: {section_desc}

위 섹션을 매우 상세하게 작성해주세요.
- 전문적이면서도 이해하기 쉬운 설명
- 구체적인 예시와 조언 포함
- 고객의 원국 특성에 맞춤화된 내용
"""
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 전문적이고 따뜻한 사주명리학 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.7
            )
            section_content = response.choices[0].message.content
            full_content.append(f"\n\n{'='*50}\n{section_title}\n{'='*50}\n\n{section_content}")
        except Exception as e:
            full_content.append(f"\n\n[{section_title}] 생성 오류: {str(e)}")
    
    if progress_callback:
        progress_callback(1.0, "완료!")
    
    return "\n".join(full_content)

# ============================================
# PDF 생성 함수 (배경 이미지 적용)
# ============================================

class BackgroundCanvas(canvas.Canvas):
    def __init__(self, *args, bg_image=None, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.bg_image = bg_image
        self.pages = []
    
    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        for page in self.pages:
            self.__dict__.update(page)
            if self.bg_image and os.path.exists(self.bg_image):
                self.drawImage(self.bg_image, 0, 0, width=A4[0], height=A4[1])
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

def create_pdf_with_background(content, customer_name, service_type, customer_name2=None):
    """표지와 배경이 적용된 PDF 생성"""
    
    buffer = io.BytesIO()
    
    # 폰트 등록
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
        font_name = 'NanumGothic'
    except:
        font_name = 'Helvetica'
    
    # PDF 캔버스 생성
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # ============================================
    # 1. 표지 페이지
    # ============================================
    if os.path.exists(COVER_IMAGE):
        c.drawImage(COVER_IMAGE, 0, 0, width=width, height=height)
    
    # 표지 하단에 고객 이름 추가
    c.setFont(font_name, 28)
    
    # 이름 표시 (궁합이면 두 명)
    if service_type == "궁합" and customer_name2:
        name_text = f"{customer_name}  ♥  {customer_name2}"
    else:
        name_text = f"{customer_name} 님"
    
    # 이름 위치 (하단 중앙)
    text_width = c.stringWidth(name_text, font_name, 28)
    c.drawString((width - text_width) / 2, height * 0.25, name_text)
    
    c.showPage()
    
    # ============================================
    # 2. 본문 페이지들
    # ============================================
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        fontName=font_name,
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER,
        leading=24
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        fontName=font_name,
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        leading=20
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        fontName=font_name,
        fontSize=10,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceBefore=4,
        spaceAfter=4
    )
    
    # 본문 내용을 페이지별로 나누기
    lines = content.split('\n')
    current_y = height - 80
    line_height = 18
    margin_left = 60
    margin_right = 60
    margin_bottom = 80
    
    # 첫 본문 페이지 배경
    if os.path.exists(PAGE_IMAGE):
        c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
    
    for line in lines:
        line = line.strip()
        
        if not line:
            current_y -= 10
            continue
        
        if line.startswith('===') or line.startswith('---'):
            continue
        
        # 제목인지 본문인지 판단
        is_heading = line.startswith('#') or (len(line) < 50 and any(keyword in line for keyword in ['운', '분석', '조언', '마무리', '서문', '총운', '궁합', '년', '월']))
        
        if is_heading:
            clean_title = line.replace('#', '').strip()
            c.setFont(font_name, 14)
            current_y -= 25
        else:
            c.setFont(font_name, 10)
        
        # 페이지 넘김 체크
        if current_y < margin_bottom:
            c.showPage()
            if os.path.exists(PAGE_IMAGE):
                c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
            current_y = height - 80
        
        # 텍스트 그리기 (긴 줄은 자동 줄바꿈)
        max_width = width - margin_left - margin_right
        
        if is_heading:
            c.drawString(margin_left, current_y, clean_title if is_heading else line)
            current_y -= line_height
        else:
            # 긴 텍스트 줄바꿈 처리
            words = line
            while words:
                if c.stringWidth(words, font_name, 10) <= max_width:
                    c.drawString(margin_left, current_y, words)
                    current_y -= line_height
                    break
                else:
                    # 적절한 위치에서 자르기
                    cut_point = len(words)
                    while cut_point > 0 and c.stringWidth(words[:cut_point], font_name, 10) > max_width:
                        cut_point -= 1
                    
                    # 단어 중간에서 자르지 않도록
                    space_point = words[:cut_point].rfind(' ')
                    if space_point > 0:
                        cut_point = space_point
                    
                    c.drawString(margin_left, current_y, words[:cut_point])
                    current_y -= line_height
                    words = words[cut_point:].strip()
                    
                    # 페이지 넘김 체크
                    if current_y < margin_bottom:
                        c.showPage()
                        if os.path.exists(PAGE_IMAGE):
                            c.drawImage(PAGE_IMAGE, 0, 0, width=width, height=height)
                        current_y = height - 80
    
    c.save()
    buffer.seek(0)
    return buffer

# ============================================
# 메인 웹앱 화면
# ============================================

def main():
    st.set_page_config(
        page_title="사주 PDF 생성기",
        page_icon="🔮",
        layout="wide"
    )
    
    st.title("🔮 사주 PDF 자동 생성 시스템")
    st.markdown("---")
    
    if 'settings' not in st.session_state:
        st.session_state.settings = load_settings()
    if 'guide' not in st.session_state:
        st.session_state.guide = load_guide()
    
    tab1, tab2, tab3 = st.tabs(["⚙️ 설정", "📝 지침서", "📄 PDF 생성"])
    
    # ============================================
    # 설정 탭
    # ============================================
    with tab1:
        st.header("⚙️ 시스템 설정")
        
        st.subheader("🔑 OpenAI API 키")
        api_key = st.text_input(
            "API 키 입력",
            value=st.session_state.settings.get("api_key", ""),
            type="password",
            help="OpenAI에서 발급받은 API 키를 입력하세요"
        )
        
        st.subheader("🤖 GPT 모델 선택")
        model = st.selectbox(
            "사용할 모델",
            ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
            index=0,
            help="gpt-4o-mini: 저렴하고 빠름 / gpt-4o: 고품질"
        )
        
        st.markdown("---")
        
        st.subheader("📊 엑셀 컬럼 구성")
        st.info("고객 정보 엑셀 파일의 컬럼 구성을 설정합니다.")
        
        columns = st.session_state.settings.get("columns", [])
        
        st.write("**현재 컬럼 목록:**")
        
        columns_to_remove = []
        updated_columns = []
        
        for i, col in enumerate(columns):
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                new_name = st.text_input(f"컬럼명 {i+1}", value=col["name"], key=f"col_name_{i}")
            with col2:
                new_desc = st.text_input(f"설명 {i+1}", value=col["description"], key=f"col_desc_{i}")
            with col3:
                st.write("")
                st.write("")
                if st.button("🗑️", key=f"del_{i}", help="이 컬럼 삭제"):
                    columns_to_remove.append(i)
            
            if i not in columns_to_remove:
                updated_columns.append({"name": new_name, "description": new_desc})
        
        if columns_to_remove:
            st.session_state.settings["columns"] = updated_columns
            st.rerun()
        
        st.markdown("---")
        st.write("**새 컬럼 추가:**")
        col1, col2, col3 = st.columns([2, 3, 1])
        with col1:
            new_col_name = st.text_input("새 컬럼명", key="new_col_name")
        with col2:
            new_col_desc = st.text_input("새 컬럼 설명", key="new_col_desc")
        with col3:
            st.write("")
            st.write("")
            if st.button("➕ 추가"):
                if new_col_name:
                    columns.append({"name": new_col_name, "description": new_col_desc})
                    st.session_state.settings["columns"] = columns
                    st.rerun()
        
        st.markdown("---")
        
        if st.button("💾 설정 저장", type="primary"):
            st.session_state.settings["api_key"] = api_key
            st.session_state.settings["model"] = model
            st.session_state.settings["columns"] = updated_columns if updated_columns else columns
            save_settings(st.session_state.settings)
            st.success("✅ 설정이 저장되었습니다!")
    
    # ============================================
    # 지침서 탭
    # ============================================
    with tab2:
        st.header("📝 사주 풀이 지침서")
        st.info("GPT가 사주를 풀이할 때 따를 지침을 작성합니다.")
        
        guide_text = st.text_area(
            "지침서 내용",
            value=st.session_state.guide,
            height=500,
            help="사주 풀이의 구성, 스타일, 포함할 내용 등을 상세히 작성하세요"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 지침서 저장", type="primary"):
                st.session_state.guide = guide_text
                save_guide(guide_text)
                st.success("✅ 지침서가 저장되었습니다!")
        
        with col2:
            if st.button("🔄 기본 지침서로 초기화"):
                st.session_state.guide = load_guide()
                save_guide(st.session_state.guide)
                st.rerun()
    
    # ============================================
    # PDF 생성 탭
    # ============================================
    with tab3:
        st.header("📄 PDF 생성")
        
        if not st.session_state.settings.get("api_key"):
            st.warning("⚠️ 먼저 '설정' 탭에서 OpenAI API 키를 입력해주세요!")
            return
        
        # 이미지 파일 체크
        col1, col2 = st.columns(2)
        with col1:
            if os.path.exists(COVER_IMAGE):
                st.success(f"✅ 표지 이미지: {COVER_IMAGE}")
            else:
                st.warning(f"⚠️ 표지 이미지 없음: {COVER_IMAGE}")
        with col2:
            if os.path.exists(PAGE_IMAGE):
                st.success(f"✅ 본문 배경: {PAGE_IMAGE}")
            else:
                st.warning(f"⚠️ 본문 배경 없음: {PAGE_IMAGE}")
        
        st.markdown("---")
        st.subheader("📊 고객 정보 엑셀 업로드")
        
        columns = st.session_state.settings.get("columns", [])
        example_data = {col["name"]: [f"예시_{col['name']}"] for col in columns}
        example_df = pd.DataFrame(example_data)
        
        st.download_button(
            label="📥 엑셀 양식 다운로드",
            data=example_df.to_csv(index=False).encode('utf-8-sig'),
            file_name="사주_고객정보_양식.csv",
            mime="text/csv"
        )
        
        st.info("""
        **서비스유형 입력 방법:**
        - 일년운세
        - 평생운세
        - 평생+일년운세
        - 궁합 (이름2 컬럼에 두번째 사람 이름 입력)
        """)
        
        uploaded_file = st.file_uploader(
            "엑셀 파일 업로드 (.xlsx, .csv)",
            type=["xlsx", "csv"]
        )
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ {len(df)}명의 고객 정보를 불러왔습니다!")
                
                st.subheader("📋 데이터 미리보기")
                st.dataframe(df, use_container_width=True)
                
                st.markdown("---")
                
                st.subheader("🎯 생성 옵션")
                
                generation_mode = st.radio(
                    "생성 모드 선택",
                    ["빠른 생성 (약 10-15페이지)", "상세 생성 (약 50-100페이지)"],
                    help="상세 생성은 시간과 비용이 더 소요됩니다"
                )
                
                selected_rows = st.multiselect(
                    "생성할 고객 선택 (비우면 전체)",
                    options=df.index.tolist(),
                    format_func=lambda x: f"{x+1}. {df.iloc[x].get('이름', f'고객{x+1}')} ({df.iloc[x].get('서비스유형', '미지정')})"
                )
                
                if not selected_rows:
                    selected_rows = df.index.tolist()
                
                st.info(f"📌 {len(selected_rows)}명의 PDF를 생성합니다.")
                
                if st.button("🚀 PDF 생성 시작", type="primary"):
                    
                    client = OpenAI(api_key=st.session_state.settings["api_key"])
                    model = st.session_state.settings.get("model", "gpt-4o-mini")
                    
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        customer_name = row.get('이름', f'고객{idx+1}')
                        customer_name2 = row.get('이름2', '')
                        service_type = row.get('서비스유형', '평생운세')
                        
                        # 빈 값 처리
                        if pd.isna(customer_name2):
                            customer_name2 = None
                        
                        st.markdown(f"### 📝 {customer_name} 님 ({service_type}) 처리 중...")
                        
                        customer_data = row.to_dict()
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(progress, status):
                            progress_bar.progress(progress)
                            status_text.text(status)
                        
                        if "상세" in generation_mode:
                            content = generate_saju_sections(
                                client, 
                                customer_data, 
                                st.session_state.guide,
                                model,
                                service_type,
                                update_progress
                            )
                        else:
                            update_progress(0.3, "GPT 생성 중...")
                            content = generate_saju_reading(
                                client,
                                customer_data,
                                st.session_state.guide,
                                model
                            )
                            update_progress(1.0, "완료!")
                        
                        status_text.text("PDF 변환 중...")
                        pdf_buffer = create_pdf_with_background(
                            content, 
                            customer_name, 
                            service_type,
                            customer_name2
                        )
                        
                        # 파일명 생성
                        if service_type == "궁합" and customer_name2:
                            filename = f"{customer_name}_{customer_name2}_궁합_{datetime.now().strftime('%Y%m%d')}.pdf"
                        else:
                            filename = f"{customer_name}_{service_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        
                        st.download_button(
                            label=f"📥 {filename} 다운로드",
                            data=pdf_buffer,
                            file_name=filename,
                            mime="application/pdf",
                            key=f"download_{idx}"
                        )
                        
                        st.success(f"✅ {customer_name} 님 PDF 생성 완료!")
                        st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 파일 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()
