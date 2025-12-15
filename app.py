# -*- coding: utf-8 -*-
"""
🔮 사주 PDF 자동 생성 시스템
비개발자도 쉽게 사용할 수 있는 웹앱
"""

import streamlit as st
import pandas as pd
import json
import os
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
import io
from datetime import datetime

# ============================================
# 📁 데이터 저장/불러오기 함수들
# ============================================

DATA_DIR = "data"
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
GUIDE_FILE = os.path.join(DATA_DIR, "guide.txt")

def ensure_data_dir():
    """데이터 폴더가 없으면 만들기"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_settings():
    """설정 불러오기"""
    ensure_data_dir()
    default_settings = {
        "api_key": "",
        "columns": [
            {"name": "이름", "description": "고객 이름"},
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
                # 기존 설정과 기본값 병합
                for key in default_settings:
                    if key not in saved:
                        saved[key] = default_settings[key]
                return saved
        except:
            return default_settings
    return default_settings

def save_settings(settings):
    """설정 저장하기"""
    ensure_data_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def load_guide():
    """지침서 불러오기"""
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
    """지침서 저장하기"""
    ensure_data_dir()
    with open(GUIDE_FILE, "w", encoding="utf-8") as f:
        f.write(guide_text)

# ============================================
# 🤖 GPT API 호출 함수
# ============================================

def generate_saju_reading(client, customer_data, guide, model):
    """GPT로 사주 풀이 생성"""
    
    # 고객 정보를 텍스트로 변환
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items()])
    
    prompt = f"""당신은 30년 경력의 사주명리학 전문가입니다.

[고객 정보]
{customer_info}

[풀이 지침]
{guide}

위 지침에 따라 이 고객을 위한 상세한 사주 풀이를 작성해주세요.
약 150페이지 분량의 깊이 있는 내용을 작성해주세요.
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

def generate_saju_sections(client, customer_data, guide, model, progress_callback=None):
    """섹션별로 나눠서 긴 사주 풀이 생성"""
    
    customer_info = "\n".join([f"- {key}: {value}" for key, value in customer_data.items()])
    
    sections = [
        ("서문 및 총운", "사주 원국의 전체적인 해석, 오행 분석, 타고난 기질을 5페이지 분량으로 상세히"),
        ("성격 및 심리 분석", "일주 기반 성격, 내면의 욕구, 강점과 약점을 5페이지 분량으로"),
        ("재물운 상세", "재물 성향, 투자 적성, 부의 흐름을 5페이지 분량으로"),
        ("직업 및 사업운", "적합 직업군, 성공 전략, 커리어 조언을 5페이지 분량으로"),
        ("건강운", "오행별 건강, 주의 질병, 관리법을 4페이지 분량으로"),
        ("연애 및 결혼운", "배우자상, 결혼 시기, 부부 궁합을 5페이지 분량으로"),
        ("대인관계 및 사회운", "인간관계 패턴, 사회적 성공 전략을 4페이지 분량으로"),
        ("2024년 운세", "2024년 월별 상세 운세를 5페이지 분량으로"),
        ("2025년 운세", "2025년 월별 상세 운세를 5페이지 분량으로"),
        ("2026년 운세", "2026년 월별 상세 운세를 5페이지 분량으로"),
        ("2027-2028년 운세", "2027-2028년 운세 흐름을 4페이지 분량으로"),
        ("인생 조언 및 마무리", "종합 조언, 행운의 방향, 마무리 메시지를 3페이지 분량으로")
    ]
    
    full_content = []
    
    for i, (section_title, section_desc) in enumerate(sections):
        if progress_callback:
            progress_callback(i / len(sections), f"'{section_title}' 생성 중...")
        
        prompt = f"""당신은 30년 경력의 사주명리학 전문가입니다.

[고객 정보]
{customer_info}

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
                    {"role": "system", "content": "당신은 전문적이고 따뜻한 사주명리학 전문가입니다. 상세하고 깊이 있는 풀이를 제공합니다."},
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
# 📄 PDF 생성 함수
# ============================================

def create_pdf(content, customer_name):
    """사주 풀이 내용을 PDF로 변환"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    # 기본 스타일 가져오기
    styles = getSampleStyleSheet()
    
    # 한글 스타일 (기본 폰트 사용 - 배포 환경에서는 한글 폰트 설치 필요)
    # Streamlit Cloud에서는 나눔고딕이 기본 설치됨
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
        font_name = 'NanumGothic'
    except:
        try:
            pdfmetrics.registerFont(TTFont('NanumGothic', 'NanumGothic.ttf'))
            font_name = 'NanumGothic'
        except:
            font_name = 'Helvetica'  # 폰트 없으면 기본 폰트 사용
    
    # 커스텀 스타일 생성
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=11,
        leading=18,
        alignment=TA_JUSTIFY,
        spaceBefore=6,
        spaceAfter=6
    )
    
    # PDF 내용 구성
    story = []
    
    # 제목 페이지
    story.append(Spacer(1, 100))
    story.append(Paragraph(f"사주명리 감정서", title_style))
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"{customer_name} 님", title_style))
    story.append(Spacer(1, 50))
    story.append(Paragraph(f"작성일: {datetime.now().strftime('%Y년 %m월 %d일')}", body_style))
    story.append(PageBreak())
    
    # 본문 내용
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith('===') or line.startswith('---'):
            continue  # 구분선 스킵
        elif line.startswith('#') or (len(line) < 50 and any(keyword in line for keyword in ['운', '분석', '조언', '마무리', '서문', '총운'])):
            # 제목으로 처리
            clean_title = line.replace('#', '').strip()
            if clean_title:
                story.append(Spacer(1, 15))
                story.append(Paragraph(clean_title, heading_style))
        else:
            # 일반 본문
            # HTML 특수문자 이스케이프
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            try:
                story.append(Paragraph(line, body_style))
            except:
                # 파싱 오류시 일반 텍스트로
                story.append(Paragraph(line.encode('utf-8', errors='ignore').decode('utf-8'), body_style))
    
    # PDF 빌드
    doc.build(story)
    buffer.seek(0)
    return buffer

# ============================================
# 🖥️ 메인 웹앱 화면
# ============================================

def main():
    st.set_page_config(
        page_title="🔮 사주 PDF 생성기",
        page_icon="🔮",
        layout="wide"
    )
    
    st.title("🔮 사주 PDF 자동 생성 시스템")
    st.markdown("---")
    
    # 설정 불러오기
    if 'settings' not in st.session_state:
        st.session_state.settings = load_settings()
    if 'guide' not in st.session_state:
        st.session_state.guide = load_guide()
    
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["⚙️ 설정", "📝 지침서", "📄 PDF 생성"])
    
    # ============================================
    # ⚙️ 설정 탭
    # ============================================
    with tab1:
        st.header("⚙️ 시스템 설정")
        
        # API 키 설정
        st.subheader("🔑 OpenAI API 키")
        api_key = st.text_input(
            "API 키 입력",
            value=st.session_state.settings.get("api_key", ""),
            type="password",
            help="OpenAI에서 발급받은 API 키를 입력하세요"
        )
        
        # GPT 모델 선택
        st.subheader("🤖 GPT 모델 선택")
        model = st.selectbox(
            "사용할 모델",
            ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
            index=0,
            help="gpt-4o-mini: 저렴하고 빠름 / gpt-4o: 고품질"
        )
        
        st.markdown("---")
        
        # 엑셀 컬럼 설정
        st.subheader("📊 엑셀 컬럼 구성")
        st.info("고객 정보 엑셀 파일의 컬럼 구성을 설정합니다.")
        
        columns = st.session_state.settings.get("columns", [])
        
        # 현재 컬럼 표시 및 수정
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
                st.write("")  # 공백
                st.write("")  # 버튼 위치 조정
                if st.button("🗑️", key=f"del_{i}", help="이 컬럼 삭제"):
                    columns_to_remove.append(i)
            
            if i not in columns_to_remove:
                updated_columns.append({"name": new_name, "description": new_desc})
        
        # 삭제된 컬럼 반영
        if columns_to_remove:
            st.session_state.settings["columns"] = updated_columns
            st.rerun()
        
        # 새 컬럼 추가
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
        
        # 설정 저장 버튼
        if st.button("💾 설정 저장", type="primary"):
            st.session_state.settings["api_key"] = api_key
            st.session_state.settings["model"] = model
            st.session_state.settings["columns"] = updated_columns if updated_columns else columns
            save_settings(st.session_state.settings)
            st.success("✅ 설정이 저장되었습니다!")
    
    # ============================================
    # 📝 지침서 탭
    # ============================================
    with tab2:
        st.header("📝 사주 풀이 지침서")
        st.info("GPT가 사주를 풀이할 때 따를 지침을 작성합니다. 이 지침에 따라 PDF 내용이 결정됩니다.")
        
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
                default_guide = load_guide.__code__.co_consts[1]  # 기본값 가져오기
                st.session_state.guide = """[사주 풀이 지침서]

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
                save_guide(st.session_state.guide)
                st.rerun()
    
    # ============================================
    # 📄 PDF 생성 탭
    # ============================================
    with tab3:
        st.header("📄 PDF 생성")
        
        # API 키 확인
        if not st.session_state.settings.get("api_key"):
            st.warning("⚠️ 먼저 '설정' 탭에서 OpenAI API 키를 입력해주세요!")
            return
        
        # 엑셀 업로드
        st.subheader("📊 고객 정보 엑셀 업로드")
        
        # 예시 다운로드
        columns = st.session_state.settings.get("columns", [])
        example_data = {col["name"]: [f"예시_{col['name']}"] for col in columns}
        example_df = pd.DataFrame(example_data)
        
        st.download_button(
            label="📥 엑셀 양식 다운로드",
            data=example_df.to_csv(index=False).encode('utf-8-sig'),
            file_name="사주_고객정보_양식.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader(
            "엑셀 파일 업로드 (.xlsx, .csv)",
            type=["xlsx", "csv"]
        )
        
        if uploaded_file:
            # 파일 읽기
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ {len(df)}명의 고객 정보를 불러왔습니다!")
                
                # 데이터 미리보기
                st.subheader("📋 데이터 미리보기")
                st.dataframe(df, use_container_width=True)
                
                st.markdown("---")
                
                # 생성 옵션
                st.subheader("🎯 생성 옵션")
                
                generation_mode = st.radio(
                    "생성 모드 선택",
                    ["빠른 생성 (약 10-15페이지)", "상세 생성 (약 50-100페이지)"],
                    help="상세 생성은 시간과 비용이 더 소요됩니다"
                )
                
                selected_rows = st.multiselect(
                    "생성할 고객 선택 (비우면 전체)",
                    options=df.index.tolist(),
                    format_func=lambda x: f"{x+1}. {df.iloc[x].get('이름', f'고객{x+1}')}"
                )
                
                if not selected_rows:
                    selected_rows = df.index.tolist()
                
                st.info(f"📌 {len(selected_rows)}명의 PDF를 생성합니다.")
                
                # 생성 버튼
                if st.button("🚀 PDF 생성 시작", type="primary"):
                    
                    # OpenAI 클라이언트 초기화
                    client = OpenAI(api_key=st.session_state.settings["api_key"])
                    model = st.session_state.settings.get("model", "gpt-4o-mini")
                    
                    for idx in selected_rows:
                        row = df.iloc[idx]
                        customer_name = row.get('이름', f'고객{idx+1}')
                        
                        st.markdown(f"### 📝 {customer_name} 님 처리 중...")
                        
                        # 고객 데이터 딕셔너리로 변환
                        customer_data = row.to_dict()
                        
                        # 진행 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(progress, status):
                            progress_bar.progress(progress)
                            status_text.text(status)
                        
                        # GPT로 사주 풀이 생성
                        if "상세" in generation_mode:
                            content = generate_saju_sections(
                                client, 
                                customer_data, 
                                st.session_state.guide,
                                model,
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
                        
                        # PDF 생성
                        status_text.text("PDF 변환 중...")
                        pdf_buffer = create_pdf(content, customer_name)
                        
                        # 다운로드 버튼
                        st.download_button(
                            label=f"📥 {customer_name}_사주풀이.pdf 다운로드",
                            data=pdf_buffer,
                            file_name=f"{customer_name}_사주풀이_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key=f"download_{idx}"
                        )
                        
                        st.success(f"✅ {customer_name} 님 PDF 생성 완료!")
                        st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 파일 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()
