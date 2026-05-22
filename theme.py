"""
공통 UI 스타일 설정.

모든 Streamlit 페이지에서 set_page_config() 직후 init_page_style()을 호출한다.
페이지별 추가 CSS가 필요하면 init_page_style()의 extra_css 파라미터에 전달.

사용 예:
    from theme import init_page_style
    st.set_page_config(...)
    init_page_style()                       # 공통 스타일
    init_page_style(extra_css=".chip {...}") # 공통 + 추가 스타일
"""

import streamlit as st

# 모든 페이지에 적용되는 공통 CSS
_COMMON_CSS = """
<style>
h1 { font-size: 1.6rem !important; }
h2 { font-size: 1.3rem !important; }
h3 { font-size: 1.1rem !important; }
{extra}
</style>
"""


def init_page_style(extra_css: str = "") -> None:
    """
    공통 헤딩 크기 CSS를 주입한다.

    Args:
        extra_css: 페이지별 추가 CSS 문자열 (선택).
                   <style> 태그 없이 CSS 내용만 전달.
    """
    css = _COMMON_CSS.replace("{extra}", extra_css)
    st.markdown(css, unsafe_allow_html=True)
