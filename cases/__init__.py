"""案例/交付物层：把诊断/裁剪/项目过程打包成可打印、可发给客户的交付物，并存档结构化案例。"""

from cases.archive import CASES_ROOT, list_cases, load_case, save_case, new_case_id
from cases.render import build_diagnosis_html, render_html_to_pdf

__all__ = [
    "CASES_ROOT", "list_cases", "load_case", "save_case", "new_case_id",
    "build_diagnosis_html", "render_html_to_pdf",
]
