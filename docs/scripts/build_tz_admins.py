# -*- coding: utf-8 -*-
"""Сборка ТЗ «Персональные учётные записи администраторов» в DOCX."""

import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
SHOTS = os.path.join(ROOT, "mockups", "admin-auth", "shots")
OUT = os.path.join(BASE, "ТЗ_личные_аккаунты_администраторов.docx")

INK = RGBColor(0x0F, 0x17, 0x2A)
BODY = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x64, 0x70, 0x80)
ACCENT = RGBColor(0x1D, 0x4E, 0xD8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Calibri"


# ---------------------------------------------------------------- утилиты


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def cell_margins(table, top=60, bottom=60, left=100, right=100):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for name, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def table_borders(table, color="D8DEE9", size=4):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def no_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)

def keep_table_together(table):
    rows = table.rows
    for row in rows[:-1]:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True

def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def no_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def set_col_widths(table, widths_cm):
    table.autofit = False
    for row in table.rows:
        for idx, width in enumerate(widths_cm):
            row.cells[idx].width = Cm(width)
    for idx, width in enumerate(widths_cm):
        table.columns[idx].width = Cm(width)


def add_table(doc, headers, rows, widths, font_size=9.0, bold_first=False,
              header_fill="E9EFFA", zebra="F8FAFC"):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table_borders(table)
    cell_margins(table)

    hdr = table.rows[0]
    repeat_header(hdr)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        shade(cell, header_fill)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.name = FONT
        run.font.color.rgb = INK

    for r_idx, row in enumerate(rows):
        cells = table.add_row().cells
        no_split(table.rows[-1])
        for c_idx, text in enumerate(row):
            cell = cells[c_idx]
            if zebra and r_idx % 2 == 1:
                shade(cell, zebra)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            run = p.add_run(str(text))
            run.font.size = Pt(font_size)
            run.font.name = FONT
            run.font.color.rgb = BODY
            if bold_first and c_idx == 0:
                run.bold = True

    set_col_widths(table, widths)
    keep_table_together(table)
    return table


def para(doc, text="", size=10.5, bold=False, italic=False, color=BODY,
         space_before=0, space_after=6, align=None, line=1.22, indent=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    if align is not None:
        p.alignment = align
    if indent is not None:
        pf.left_indent = Cm(indent)
    if text:
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.font.name = FONT
        run.bold = bold
        run.italic = italic
        run.font.color.rgb = color
    return p


def rich(doc, parts, size=10.5, space_after=6, space_before=0, indent=None, line=1.22):
    """parts: список (text, bold, color)"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    if indent is not None:
        pf.left_indent = Cm(indent)
    for text, bold, color in parts:
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.font.name = FONT
        run.bold = bold
        run.font.color.rgb = color
    return p


def bullets(doc, items, size=10.5, space_after=3):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.18
        run = p.add_run(item)
        run.font.size = Pt(size)
        run.font.name = FONT
        run.font.color.rgb = BODY


def numbered(doc, items, size=10.5):
    for i, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.75)
        pf.first_line_indent = Cm(-0.75)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.18
        run = p.add_run(f"{i}.  ")
        run.font.size = Pt(size)
        run.font.name = FONT
        run.font.color.rgb = MUTED
        run2 = p.add_run(item)
        run2.font.size = Pt(size)
        run2.font.name = FONT
        run2.font.color.rgb = BODY


def req(doc, code, text, size=10.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(1.55)
    pf.first_line_indent = Cm(-1.55)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.2
    run = p.add_run(code)
    run.bold = True
    run.font.size = Pt(size)
    run.font.name = FONT
    run.font.color.rgb = ACCENT
    run2 = p.add_run("   " + text)
    run2.font.size = Pt(size)
    run2.font.name = FONT
    run2.font.color.rgb = BODY
    return p


def h1(doc, text, page_break=False):
    if page_break:
        doc.add_page_break()
    p = doc.add_heading(level=1)
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(15)
    run.font.bold = True
    run.font.color.rgb = ACCENT
    return p


def h2(doc, text):
    p = doc.add_heading(level=2)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = INK
    return p


def h3(doc, text):
    p = doc.add_heading(level=3)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(10.5)
    run.font.bold = True
    run.font.color.rgb = INK
    return p


def callout(doc, title, text, fill="EFF6FF", border="C7D2FE"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Cm(16.4)
    shade(cell, fill)
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, sz, color in (("left", 18, border), ("top", 4, border),
                            ("bottom", 4, border), ("right", 4, border)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tc_pr.append(borders)
    cell_margins(table, top=120, bottom=120, left=180, right=140)

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(9.5)
    run.font.name = FONT
    run.font.color.rgb = ACCENT

    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.paragraph_format.line_spacing = 1.18
    run2 = p2.add_run(text)
    run2.font.size = Pt(9.5)
    run2.font.name = FONT
    run2.font.color.rgb = BODY
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_field(paragraph, code):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = code
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    txt = OxmlElement("w:t")
    txt.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(txt)
    run._r.append(fld_end)


def rule(doc, color="D8DEE9", space_before=6, space_after=10):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p_pr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    borders.append(bottom)
    p_pr.append(borders)


def caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.name = FONT
    run.font.color.rgb = MUTED


# ---------------------------------------------------------------- документ

doc = Document()

section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.0)
section.bottom_margin = Cm(2.0)
section.left_margin = Cm(2.2)
section.right_margin = Cm(2.2)
section.header_distance = Cm(1.0)
section.footer_distance = Cm(1.0)

normal = doc.styles["Normal"]
normal.font.name = FONT
normal.font.size = Pt(10.5)
normal.font.color.rgb = BODY
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.22
rpr = normal.element.get_or_add_rPr()
rfonts = rpr.find(qn("w:rFonts"))
if rfonts is None:
    rfonts = OxmlElement("w:rFonts")
    rpr.append(rfonts)
for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
    rfonts.set(qn(attr), FONT)

lb = doc.styles["List Bullet"]
lb.font.name = FONT
lb.font.size = Pt(10.5)

# колонтитулы
section.different_first_page_header_footer = True

header = section.header
hp = header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
hr = hp.add_run("ТЗ · Персональные учётные записи администраторов · версия 1.0")
hr.font.size = Pt(8)
hr.font.name = FONT
hr.font.color.rgb = MUTED

footer = section.footer
fp = footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
add_field(fp, " PAGE ")
for run in fp.runs:
    run.font.size = Pt(8.5)
    run.font.name = FONT
    run.font.color.rgb = MUTED

# ---------------------------------------------------------------- обложка

para(doc, "ООО «ЮРИТЕХ»", size=9.5, bold=True, color=MUTED, space_after=2)
para(doc, "юридическая онлайн-платформа", size=8.5, color=MUTED, space_after=0)
rule(doc, space_before=4, space_after=70)

para(doc, "ТЕХНИЧЕСКОЕ ЗАДАНИЕ", size=26, bold=True, color=INK, space_after=10, line=1.0)
para(
    doc,
    "Персональные учётные записи администраторов\nи регистрация по приглашениям",
    size=15,
    color=RGBColor(0x33, 0x41, 0x55),
    space_after=18,
    line=1.25,
)

para(
    doc,
    "Доработка партнёрского кабинета: отказ от общей учётной записи, "
    "личные логины и пароли, управление доступами через супер-администратора.",
    size=10.5,
    color=MUTED,
    space_after=60,
    line=1.4,
)

meta = doc.add_table(rows=0, cols=2)
meta.autofit = False
no_borders(meta)
meta_rows = [
    ("Версия документа", "1.0 (первая редакция)"),
    ("Дата", "5 ноября 2026 г."),
    ("Статус", "На согласовании"),
    ("Заказчик", "ООО «ЮРИТЕХ», ИНН 3100009570"),
    ("Система", "Партнёрский кабинет, finzdorovie.ru"),
    ("Основание", "Решение руководства о разделении административного доступа"),
]
for label, value in meta_rows:
    cells = meta.add_row().cells
    cells[0].width = Cm(4.6)
    cells[1].width = Cm(11.8)
    p = cells[0].paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(label)
    r.font.size = Pt(9)
    r.font.name = FONT
    r.font.color.rgb = MUTED
    p2 = cells[1].paragraphs[0]
    p2.paragraph_format.space_after = Pt(4)
    r2 = p2.add_run(value)
    r2.font.size = Pt(9.5)
    r2.font.name = FONT
    r2.font.color.rgb = INK

set_col_widths(meta, [4.6, 11.8])

for _ in range(9):
    para(doc, "", space_after=0)

rule(doc, space_before=0, space_after=4)
para(doc, "Старый Оскол · 2026", size=8.5, color=MUTED, space_after=0)

# ---------------------------------------------------------------- история и согласование

doc.add_page_break()

h1(doc, "История изменений")
add_table(
    doc,
    ["Версия", "Дата", "Автор", "Изменения"],
    [
        ["1.0", "05.11.2026", "Команда разработки", "Первая редакция: постановка задачи, требования, критерии приёмки."],
    ],
    [2.0, 2.8, 4.4, 7.2],
)

h1(doc, "Лист согласования")
add_table(
    doc,
    ["Роль", "ФИО", "Подпись", "Дата"],
    [
        ["Заказчик (руководство)", "", "", ""],
        ["Ответственный за продукт", "", "", ""],
        ["Технический руководитель", "", "", ""],
    ],
    [5.2, 5.4, 3.0, 2.8],
)

callout(
    doc,
    "Как читать документ",
    "Разделы 1–5 фиксируют задачу и границы работ. Разделы 6–11 — что именно нужно сделать "
    "и как это должно быть устроено. Разделы 12–14 — как принять результат и внедрить. "
    "Раздел 16 содержит вопросы, которые нужно закрыть до старта разработки.",
)

# ---------------------------------------------------------------- содержание

doc.add_page_break()
h1(doc, "Содержание")

toc = [
    ("1.", "Общие сведения"),
    ("2.", "Назначение и цели"),
    ("3.", "Текущее состояние"),
    ("4.", "Границы работ"),
    ("5.", "Роли и права"),
    ("6.", "Функциональные требования"),
    ("7.", "Требования к интерфейсу"),
    ("8.", "Требования к API"),
    ("9.", "Требования к данным"),
    ("10.", "Требования к безопасности"),
    ("11.", "Нефункциональные требования"),
    ("12.", "Критерии приёмки"),
    ("13.", "Тестирование"),
    ("14.", "Порядок внедрения и миграция"),
    ("15.", "Риски и меры"),
    ("16.", "Открытые вопросы"),
    ("17.", "Приложения"),
]

for num, title in toc:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(5)
    pf.line_spacing = 1.2
    pf.left_indent = Cm(0.0)
    r = p.add_run(num + "  ")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.name = FONT
    r.font.color.rgb = ACCENT
    r2 = p.add_run(title)
    r2.font.size = Pt(10.5)
    r2.font.name = FONT
    r2.font.color.rgb = BODY

# ---------------------------------------------------------------- 1

h1(doc, "1. Общие сведения", page_break=True)

h2(doc, "1.1. Наименование работы")
para(
    doc,
    "Доработка партнёрского кабинета: персональные учётные записи администраторов "
    "и регистрация по приглашениям.",
)

h2(doc, "1.2. Заказчик и исполнитель")
add_table(
    doc,
    ["Сторона", "Описание"],
    [
        ["Заказчик", "ООО «ЮРИТЕХ», ИНН 3100009570, г. Старый Оскол"],
        ["Исполнитель", "Команда разработки партнёрского кабинета (внутренняя или подрядная)"],
        ["Владелец продукта", "Руководство ООО «ЮРИТЕХ»"],
        ["Система", "Партнёрский кабинет: frontend (React + Vite), backend (FastAPI), PostgreSQL"],
    ],
    [4.4, 12.0],
)

h2(doc, "1.3. Основание для выполнения работ")
para(
    doc,
    "Сейчас все администраторы работают под одной общей учётной записью. Из-за этого система "
    "не различает сотрудников: в журналах и истории действий невозможно определить, кто именно "
    "выполнил операцию, а при увольнении одного человека пароль приходится менять всей команде.",
)
para(
    doc,
    "Принято решение перейти на персональные учётные записи: у каждого администратора — "
    "своя почта, свой логин и свой пароль. Доступ выдаётся только по приглашению, "
    "которое создаёт супер-администратор.",
)

h2(doc, "1.4. Термины и сокращения")
add_table(
    doc,
    ["Термин", "Определение"],
    [
        ["Кабинет", "Партнёрский кабинет ЮРИТЕХ — веб-приложение для работы с партнёрами и клиентами."],
        ["Учётная запись", "Набор данных для входа: почта, логин, пароль, роль, статус."],
        ["Общая учётная запись", "Единый логин и пароль, под которым сейчас работают все администраторы."],
        ["Супер-админ", "Администратор с правом управлять доступами: приглашать, блокировать, менять роли."],
        ["Админ", "Сотрудник, который работает в кабинете, но не управляет доступами других."],
        ["Приглашение", "Одноразовая ссылка, привязанная к конкретной почте, по которой создаётся аккаунт."],
        ["Токен приглашения", "Случайная строка в ссылке; в базе хранится только её хэш."],
        ["Bootstrap-ключ", "Одноразовый ключ из консоли сервера для создания первого супер-админа."],
        ["Журнал доступа", "Неизменяемый список событий: входы, приглашения, блокировки, смены ролей."],
        ["Сессия", "Пара токенов доступа и обновления, выданная после успешного входа."],
        ["MVP", "Минимально достаточный объём доработки, описанный в разделах 6–9."],
    ],
    [4.2, 12.2],
    bold_first=True,
)

# ---------------------------------------------------------------- 2

h1(doc, "2. Назначение и цели")

h2(doc, "2.1. Цель доработки")
para(
    doc,
    "Сделать так, чтобы каждый администратор входил в кабинет только под своими данными, "
    "а доступ выдавался осознанно — по приглашению супер-администратора.",
)

h2(doc, "2.2. Задачи")
numbered(
    doc,
    [
        "Отказаться от общей учётной записи администратора и перевести всех на личные аккаунты.",
        "Ввести роль супер-администратора, который управляет доступами.",
        "Реализовать приглашения: почта, роль, срок действия, одноразовая ссылка.",
        "Реализовать регистрацию по приглашению: человек сам задаёт логин и пароль.",
        "Ввести журнал доступа, где видно, кто и когда входил и что менял.",
        "Провести миграцию: отключить общий логин, пригласить всех действующих администраторов.",
    ],
)

h2(doc, "2.3. Ожидаемый эффект")
bullets(
    doc,
    [
        "Персональная ответственность: у каждого действия есть автор.",
        "Точечное управление доступом: выдать или забрать доступ одному человеку, не затрагивая остальных.",
        "Быстрое отключение при увольнении или переводе сотрудника.",
        "Прозрачная история входов — основа для разбора инцидентов.",
        "Снижение рисков, связанных с обезличенным доступом к финансовым и клиентским данным.",
    ],
)

# ---------------------------------------------------------------- 3

h1(doc, "3. Текущее состояние")

h2(doc, "3.1. Как работает сейчас")
para(
    doc,
    "В системе есть роль «администратор», но фактически все сотрудники используют один и тот же "
    "логин и пароль. Разделения по людям нет: система видит одного и того же пользователя, "
    "кто бы ни сел за компьютер.",
)

h2(doc, "3.2. Проблемы текущей схемы")
add_table(
    doc,
    ["Проблема", "Последствие"],
    [
        ["Все действия обезличены", "В истории невозможно понять, кто изменил данные или совершил операцию."],
        ["Один пароль на всех", "Пароль знают все; утечка или увольнение требуют смены пароля всей команде."],
        ["Нет учёта входов", "Нельзя увидеть, кто и когда заходил, в том числе в нерабочее время."],
        ["Нет точечного отзыва", "Заблокировать одного сотрудника, не затронув остальных, невозможно."],
        ["Нет подтверждения личности", "Почта сотрудника не связана с аккаунтом, восстановление доступа затруднено."],
    ],
    [6.0, 10.4],
)

h2(doc, "3.3. Вывод")
para(
    doc,
    "Схема с общей учётной записью не масштабируется и не даёт управляемости. Требуется доработка "
    "с разделением учётных записей и управлением доступами через супер-администратора.",
)

# ---------------------------------------------------------------- 4

h1(doc, "4. Границы работ")

h2(doc, "4.1. Что входит в работы")
bullets(
    doc,
    [
        "Модель данных: поля логина и служебных отметок в учётной записи, таблицы приглашений и журнала.",
        "Серверная часть: первичная настройка, приглашения, регистрация, вход, управление доступами, журнал.",
        "Клиентская часть: семь экранов, описанных в разделе 7, и пункт меню «Админы» для супер-админа.",
        "Почтовые уведомления: приглашение и сброс пароля (при настроенном SMTP).",
        "Миграция: отключение общей учётной записи и приглашение действующих администраторов.",
        "Документация: инструкция для супер-админа и порядок восстановления доступа.",
    ],
)

h2(doc, "4.2. Что не входит в работы")
bullets(
    doc,
    [
        "Двухфакторная аутентификация (2FA). Рекомендуется отдельным этапом после запуска.",
        "Единый вход через внешние провайдеры (SSO, Active Directory, Яндекс 360 ID).",
        "Изменение прав и сценариев входа партнёров — их процесс остаётся прежним.",
        "Регистрация администраторов без приглашения «self-signup» — не реализуется принципиально.",
        "Ребрендинг или редизайн кабинета: новые экраны выполняются в текущей визуальной системе.",
        "Мобильное приложение и push-уведомления.",
    ],
)

# ---------------------------------------------------------------- 5

h1(doc, "5. Роли и права")

h2(doc, "5.1. Роли")
add_table(
    doc,
    ["Роль", "Код", "Назначение"],
    [
        ["Супер-администратор", "super_admin", "Управляет доступами: приглашает, блокирует, меняет роли, видит журнал."],
        ["Администратор", "admin", "Работает в кабинете с партнёрами, клиентами, задачами, финансами и чатом."],
        ["Сотрудник", "staff", "Ограниченный набор разделов; без финансов, настроек и управления доступами."],
        ["Партнёр", "partner", "Внешний пользователь кабинета; процесс входа и регистрации не меняется."],
    ],
    [4.2, 3.2, 9.0],
    bold_first=True,
)

para(
    doc,
    "Роль «Сотрудник» вводится как задел: её состав разделов уточняется (см. раздел 16). "
    "Если заказчик решит ограничиться двумя ролями, требования к staff из документа исключаются "
    "без влияния на остальные сценарии.",
    size=9.5,
    color=MUTED,
)

h2(doc, "5.2. Матрица доступа")
add_table(
    doc,
    ["Функция", "Супер-админ", "Админ", "Сотрудник"],
    [
        ["Дашборд", "Да", "Да", "Да"],
        ["Партнёры: просмотр и редактирование", "Да", "Да", "Да"],
        ["Клиенты: просмотр и редактирование", "Да", "Да", "Да"],
        ["Задачи", "Да", "Да", "Да"],
        ["Транзакции и финансы", "Да", "Да", "Нет"],
        ["Чат и документы из чата", "Да", "Да", "Да"],
        ["Новости", "Да", "Да", "Нет"],
        ["Настройки", "Да", "Да", "Нет"],
        ["Раздел «Админы» и управление доступами", "Да", "Нет", "Нет"],
        ["Журнал доступа", "Да", "Нет", "Нет"],
        ["Приглашение и блокировка администраторов", "Да", "Нет", "Нет"],
        ["Сброс пароля другому администратору", "Да", "Нет", "Нет"],
    ],
    [9.4, 2.4, 2.2, 2.4],
    bold_first=True,
)

# ---------------------------------------------------------------- 6

h1(doc, "6. Функциональные требования")

para(
    doc,
    "Требования пронумерованы. Каждый номер используется в критериях приёмки (раздел 12) "
    "и в тестах (раздел 13).",
    size=9.5,
    color=MUTED,
)

h2(doc, "6.1. Первичная настройка и супер-администратор")
req(doc, "FR-01", "Пока в системе нет ни одного супер-администратора, единственным доступным "
                  "сценарием остаётся первичная настройка по адресу /setup.")
req(doc, "FR-02", "Bootstrap-ключ создаётся серверной командой, выводится в консоль один раз, "
                  "действует 60 минут и хранится в базе только в виде хэша.")
req(doc, "FR-03", "По ключу создаётся супер-администратор: почта, логин, пароль. Ключ погашается, "
                  "событие фиксируется в журнале.")
req(doc, "FR-04", "После создания первого супер-администратора страница /setup возвращает 404, "
                  "а повторное использование ключа отклоняется.")

h2(doc, "6.2. Приглашения")
req(doc, "FR-05", "Создавать, отзывать и перевыпускать приглашения может только супер-администратор.")
req(doc, "FR-06", "Приглашение содержит: почту, роль, срок действия (24, 72 или 168 часов; по умолчанию 72).")
req(doc, "FR-07", "Почта проверяется на формат. Приглашение на почту, уже занятую активной учётной записью, "
                  "запрещено.")
req(doc, "FR-08", "Одновременно на одну почту может действовать только одно приглашение: новое отзывает предыдущее.")
req(doc, "FR-09", "Токен приглашения — случайная строка не менее 256 бит. В базе хранится только хэш токена; "
                  "сравнение выполняется за постоянное время.")
req(doc, "FR-10", "Ссылка имеет вид https://<домен>/invite/<токен>. Супер-админ всегда может скопировать её "
                  "из интерфейса, независимо от доставки письма.")
req(doc, "FR-11", "Если почтовый сервер настроен, приглашение отправляется письмом. Ошибка отправки не отменяет "
                  "приглашение: ссылка остаётся доступной, а супер-админ видит предупреждение.")
req(doc, "FR-12", "Список приглашений показывает почту, роль, автора, дату создания, срок и статус.")
req(doc, "FR-13", "Отзыв приглашения делает ссылку недействительной немедленно.")
req(doc, "FR-14", "Перевыпуск создаёт новый токен, отзывает прежний и продлевает срок.")

h3(doc, "Статусы приглашения")
add_table(
    doc,
    ["Статус", "Когда возникает", "Что видит приглашённый", "Действия супер-админа"],
    [
        ["Активно", "Создано, срок не истёк, не использовано", "Форму регистрации", "Отозвать, перевыпустить"],
        ["Использовано", "Регистрация завершена", "«Ссылка уже использована»", "Только просмотр аккаунта"],
        ["Просрочено", "Истёк срок действия", "«Срок действия ссылки истёк»", "Перевыпустить"],
        ["Отозвано", "Отозвано вручную", "«Приглашение отозвано»", "Создать новое"],
    ],
    [3.2, 5.2, 4.6, 3.6],
    bold_first=True,
)

h2(doc, "6.3. Регистрация по приглашению")
req(doc, "FR-15", "Страница /invite/<токен> доступна без авторизации.")
req(doc, "FR-16", "При валидном токене отображается форма: почта (только чтение), логин, пароль, повтор пароля.")
req(doc, "FR-17", "При недействительном токене показывается причина: использован, просрочен, отозван, не найден — "
                  "и инструкция, что делать дальше.")
req(doc, "FR-18", "Логин: 3–32 символа, латинские буквы, цифры, точка, дефис, подчёркивание. "
                  "Уникален без учёта регистра; занятый логин отклоняется с понятной ошибкой.")
req(doc, "FR-19", "Пароль: не менее 10 символов, содержит буквы и цифры. Хранится в виде bcrypt-хэша "
                  "(как и остальные пароли системы).")
req(doc, "FR-20", "При успехе создаётся учётная запись с ролью из приглашения, почта считается подтверждённой, "
                  "приглашение переходит в статус «Использовано», выполняется вход в кабинет, пишется событие.")
req(doc, "FR-21", "Повторная отправка формы и двойной клик не создают вторую учётную запись.")

h2(doc, "6.4. Вход и восстановление пароля")
req(doc, "FR-22", "Вход выполняется по почте или логину и паролю.")
req(doc, "FR-23", "При ошибке выводится нейтральное сообщение «Неверный email/логин или пароль» — без указания, "
                  "что именно неверно.")
req(doc, "FR-24", "Ограничение попыток: 5 неудач за 15 минут на пару «учётная запись + IP» — временная блокировка "
                  "входа на 15 минут. После 3 неудач запрашивается капча.")
req(doc, "FR-25", "Успешный вход обновляет время последнего входа и фиксируется в журнале.")
req(doc, "FR-26", "«Забыли пароль» отправляет письмо со ссылкой на сброс (действует 60 минут, одноразовая). "
                  "Ответ одинаков независимо от того, существует ли почта.")
req(doc, "FR-27", "Сброс пароля завершает все активные сессии пользователя.")

h2(doc, "6.5. Управление администраторами")
req(doc, "FR-28", "Список администраторов с поиском по почте и логину, фильтром по роли и статусу.")
req(doc, "FR-29", "Доступные действия: изменить роль, заблокировать, разблокировать, сбросить пароль, "
                  "отозвать приглашение, скопировать ссылку приглашения.")
req(doc, "FR-30", "Блокировка, смена роли и удаление немедленно завершают активные сессии пользователя.")
req(doc, "FR-31", "Удаление реализуется как деактивация: запись сохраняется для истории и журнала. "
                  "Жёсткое удаление не предусмотрено.")
req(doc, "FR-32", "Нельзя заблокировать, понизить в роли или удалить самого себя.")
req(doc, "FR-33", "Система не позволяет остаться без активного супер-администратора.")

h2(doc, "6.6. Защита от потери доступа")
req(doc, "FR-34", "Если в системе один супер-администратор, интерфейс показывает предупреждение "
                  "и предлагает назначить второго.")
req(doc, "FR-35", "Восстановление доступа при утрате всех супер-админов выполняется серверной командой; "
                  "порядок описан в инструкции администратора.")

h2(doc, "6.7. Журнал доступа")
req(doc, "FR-36", "Журнал фиксирует события: первичная настройка, создание/отзыв/перевыпуск приглашения, "
                  "регистрация по приглашению, вход (успешный и неуспешный), выход, сброс пароля, "
                  "смена роли, блокировка, разблокировка, деактивация, попытка запрещённого действия.")
req(doc, "FR-37", "Запись содержит: время (МСК), кто (учётная запись или «система»), действие, объект, "
                  "результат, IP-адрес, user-agent.")
req(doc, "FR-38", "Журнал доступен только супер-администраторам. Записи нельзя редактировать или удалять.")
req(doc, "FR-39", "Хранение — 12 месяцев. Фильтры: период, тип действия, почта или логин; постраничный вывод.")

h2(doc, "6.8. Почтовые уведомления")
req(doc, "FR-40", "Письмо-приглашение содержит: кто пригласил, роль, срок действия ссылки и кнопку перехода.")
req(doc, "FR-41", "Письмо для сброса пароля содержит ссылку и срок её действия.")
req(doc, "FR-42", "Пароли в письмах не отправляются никогда.")
req(doc, "FR-43", "При недоступности почтового сервера ссылки выдаются в интерфейсе (резервный способ).")

h2(doc, "6.9. Миграция с общей учётной записи")
req(doc, "FR-44", "Общая учётная запись отключается (is_active = false) и помечается как устаревшая; "
                  "запись сохраняется, чтобы история не потеряла автора.")
req(doc, "FR-45", "Приглашения для действующих администраторов создаются пакетно: вручную или импортом списка.")
req(doc, "FR-46", "Администраторы уведомляются за 5 рабочих дней; в письме — инструкция из трёх шагов.")
req(doc, "FR-47", "В течение 24 часов после переключения ответственный может временно вернуть общий доступ "
                  "(флаг), если часть сотрудников не успела зарегистрироваться.")
req(doc, "FR-48", "По итогам миграции формируется отчёт: приглашено, зарегистрировано, не зашло ни разу.")

# ---------------------------------------------------------------- 7

h1(doc, "7. Требования к интерфейсу")

h2(doc, "7.1. Экраны")
add_table(
    doc,
    ["№", "Экран", "Адрес", "Назначение", "Кому доступен"],
    [
        ["1", "Вход", "/login", "Вход по почте или логину; без публичной регистрации", "Все"],
        ["2", "Регистрация по приглашению", "/invite/<токен>", "Создание личного аккаунта", "По ссылке"],
        ["3", "Первый запуск", "/setup", "Создание первого супер-админа по ключу", "По ключу из консоли"],
        ["4", "Админы и доступы", "/admin/admins", "Список админов, роли, статусы, приглашения", "Супер-админ"],
        ["5", "Приглашение (окно)", "/admin/admins", "Почта, роль, срок действия", "Супер-админ"],
        ["6", "Приглашение создано (окно)", "/admin/admins", "Ссылка, копирование, срок", "Супер-админ"],
        ["7", "Журнал доступа", "/admin/admins → вкладка", "История событий доступа", "Супер-админ"],
    ],
    [1.0, 5.0, 3.6, 5.2, 3.0],
)

h2(doc, "7.2. Общие требования к интерфейсу")
bullets(
    doc,
    [
        "Новые экраны выполняются в текущей визуальной системе кабинета: те же шрифты, цвета, кнопки и поля.",
        "На экране входа нет и не может быть кнопки «Зарегистрироваться».",
        "Пункт меню «Админы» отображается только супер-администратору.",
        "Все ошибки формулируются по-русски и объясняют, что делать дальше, без технических кодов.",
        "Пустые состояния содержат пояснение и действие: например, «Приглашений пока нет — пригласите админа».",
        "Формы проверяют поля до отправки и показывают ошибку рядом с полем.",
        "Интерфейс работает на экранах от 360 px; таблицы на узких экранах прокручиваются горизонтально.",
        "Элементы доступны с клавиатуры, у полей есть подписи, у кнопок — понятные названия.",
        "Пароль можно показать/скрыть; при вводе нового пароля видны требования к нему.",
    ],
)

h2(doc, "7.3. Макеты")
para(
    doc,
    "Макеты всех семи экранов приведены в Приложении А. Они согласуются с заказчиком до начала разработки; "
    "отклонения от макетов допускаются только по письменному согласованию.",
)

# ---------------------------------------------------------------- 8

h1(doc, "8. Требования к API")

para(
    doc,
    "Пути приведены ориентировочно, в стиле существующего API. Точные имена согласуются при реализации; "
    "поведение и коды ошибок обязательны.",
)


add_table(
    doc,
    ["Метод", "Путь", "Назначение", "Доступ"],
    [
        ["POST", "/api/setup/bootstrap", "Создание первого супер-админа по ключу", "По bootstrap-ключу"],
        ["POST", "/api/auth/login", "Вход по почте или логину", "Без авторизации"],
        ["POST", "/api/auth/logout", "Завершение сессии", "Авторизован"],
        ["POST", "/api/auth/register-by-invite", "Регистрация по токену приглашения", "По токену"],
        ["POST", "/api/auth/forgot-password", "Запрос ссылки на сброс пароля", "Без авторизации"],
        ["POST", "/api/auth/reset-password", "Установка нового пароля по токену", "По токену"],
        ["GET", "/api/admin/invites", "Список приглашений", "Супер-админ"],
        ["POST", "/api/admin/invites", "Создание приглашения", "Супер-админ"],
        ["POST", "/api/admin/invites/{id}/resend", "Перевыпуск приглашения", "Супер-админ"],
        ["DELETE", "/api/admin/invites/{id}", "Отзыв приглашения", "Супер-админ"],
        ["GET", "/api/admin/users", "Список администраторов", "Супер-админ"],
        ["PATCH", "/api/admin/users/{id}", "Смена роли, блокировка, разблокировка", "Супер-админ"],
        ["POST", "/api/admin/users/{id}/reset-password", "Ссылка на сброс пароля", "Супер-админ"],
        ["GET", "/api/admin/audit", "Журнал доступа с фильтрами", "Супер-админ"],
    ],
    [1.8, 6.2, 6.4, 3.4],
)

h2(doc, "8.2. Общие требования к API")
bullets(
    doc,
    [
        "Все ответы — JSON; ошибки содержат машинный код и понятное человеку сообщение.",
        "Коды ошибок: INVITE_INVALID, INVITE_EXPIRED, INVITE_USED, INVITE_REVOKED, EMAIL_TAKEN, "
        "LOGIN_TAKEN, LAST_SUPER_ADMIN, SELF_ACTION_FORBIDDEN, RATE_LIMITED, WEAK_PASSWORD.",
        "Создание приглашения идемпотентно по почте: повторный запрос отзывает предыдущее приглашение.",
        "Списки поддерживают пагинацию и фильтры; журнал — фильтр по периоду и типу действия.",
        "Все действия, изменяющие доступы, пишут событие в журнал в той же транзакции.",
    ],
)

# ---------------------------------------------------------------- 9

h1(doc, "9. Требования к данным")

h2(doc, "9.1. Учётная запись (users)")
add_table(
    doc,
    ["Поле", "Тип", "Обязательно", "Комментарий"],
    [
        ["id", "uuid", "Да", "Первичный ключ"],
        ["email", "varchar(255), уникальный", "Да", "Без учёта регистра"],
        ["login", "varchar(32), уникальный", "Да", "Новое поле; латиница, цифры, . _ -"],
        ["hashed_password", "varchar(255)", "Да", "bcrypt"],
        ["role", "varchar(20)", "Да", "partner | admin | super_admin | staff"],
        ["is_active", "boolean", "Да", "Блокировка без удаления"],
        ["is_legacy_shared", "boolean", "Да", "Признак бывшей общей учётной записи"],
        ["created_by", "uuid, nullable", "Нет", "Кто пригласил"],
        ["last_login_at", "timestamptz, nullable", "Нет", "Время последнего входа"],
        ["password_changed_at", "timestamptz, nullable", "Нет", "Для политики паролей"],
        ["created_at / updated_at", "timestamptz", "Да", "Служебные"],
    ],
    [5.0, 5.0, 2.6, 5.4],
)

h2(doc, "9.2. Приглашения (invites)")
add_table(
    doc,
    ["Поле", "Тип", "Комментарий"],
    [
        ["id", "uuid", "Первичный ключ"],
        ["email", "varchar(255)", "Привязана к приглашению"],
        ["role", "varchar(20)", "Роль будущего аккаунта"],
        ["token_hash", "char(64), уникальный", "SHA-256 от токена; сам токен не хранится"],
        ["expires_at", "timestamptz", "Срок действия"],
        ["used_at / revoked_at", "timestamptz, nullable", "Погашение"],
        ["created_by", "uuid", "Автор приглашения"],
        ["created_at", "timestamptz", "Дата создания"],
    ],
    [5.0, 5.4, 7.0],
)

h2(doc, "9.3. Журнал (audit_events)")
add_table(
    doc,
    ["Поле", "Тип", "Комментарий"],
    [
        ["id", "bigserial", "Первичный ключ"],
        ["occurred_at", "timestamptz", "Время события"],
        ["actor_id", "uuid, nullable", "Кто; null для системы"],
        ["actor_label", "text", "Почта или логин на момент события"],
        ["action", "varchar(64)", "Тип действия"],
        ["target_type / target_id", "varchar(32) / uuid", "Над чем выполнено"],
        ["target_label", "text", "Почта, логин или название объекта"],
        ["result", "varchar(16)", "success | failure"],
        ["ip", "inet", "Адрес клиента"],
        ["user_agent", "text", "Браузер"],
        ["meta", "jsonb", "Дополнительные детали без секретов"],
    ],
    [5.4, 4.6, 7.4],
)

h2(doc, "9.4. Bootstrap-ключи (bootstrap_tokens)")
para(
    doc,
    "Таблица хранит хэш одноразового ключа, срок действия и отметку использования. "
    "Записи старше 30 дней удаляются автоматически.",
)

h2(doc, "9.5. Миграции")
bullets(
    doc,
    [
        "Миграции выполняются автоматически при деплое и обратимы (up/down).",
        "Существующие партнёры не затрагиваются: для них поле login заполняется служебно и не используется.",
        "Общая учётная запись не удаляется, а деактивируется с отметкой is_legacy_shared = true.",
        "Перед миграцией создаётся резервная копия базы.",
    ],
)

# ---------------------------------------------------------------- 10

h1(doc, "10. Требования к безопасности")

h2(doc, "10.1. Модель угроз и меры")
add_table(
    doc,
    ["Угроза", "Мера защиты"],
    [
        ["Подбор пароля", "Ограничение попыток, капча, блокировка на 15 минут, журналирование."],
        ["Регистрация постороннего", "Публичной регистрации нет; только приглашение на конкретную почту."],
        ["Кража ссылки приглашения", "Привязка к почте, одноразовость, срок 72 часа, отзыв."],
        ["Перехват сессии", "HTTPS, токены с ограниченным сроком, завершение сессий при блокировке."],
        ["Утечка пароля из базы", "bcrypt; пароли не логируются и не отдаются API."],
        ["Подмена автора действия", "Журнал пишется на сервере, поле автора недоступно клиенту."],
        ["Захват единственного супер-админа", "Минимум два супер-админа, запрет на самоблокировку."],
        ["Раскрытие существования почты", "Одинаковый ответ на сброс пароля и нейтральные ошибки входа."],
    ],
    [6.6, 9.8],
)

h2(doc, "10.2. Дополнительные требования")
bullets(
    doc,
    [
        "Токены приглашений и сброса пароля хранятся только в виде хэша и сравниваются за постоянное время.",
        "Пароль не может совпадать с логином или почтой; проверяется по списку частых паролей.",
        "Все административные действия доступны только по HTTPS; cookies — Secure, HttpOnly, SameSite=Lax.",
        "Секреты (ключ подписи, SMTP) хранятся в переменных окружения, не в репозитории.",
        "Персональные данные в журнале ограничены почтой и логином; содержимое клиентских документов не пишется.",
        "Резервное копирование базы — ежедневно; проверка восстановления — не реже раза в квартал.",
    ],
)

# ---------------------------------------------------------------- 11

h1(doc, "11. Нефункциональные требования")

add_table(
    doc,
    ["Категория", "Требование"],
    [
        ["Производительность", "Ответ списков и приглашений — не более 300 мс на 95-м процентиле при 50 админах."],
        ["Надёжность", "Ошибка отправки письма не отменяет приглашение; ссылка остаётся доступной."],
        ["Совместимость", "Chrome, Safari, Firefox, Edge последних двух версий; мобильные браузеры."],
        ["Локализация", "Интерфейс и письма — на русском языке; даты в московском времени."],
        ["Доступность", "Контраст текста не ниже 4.5:1, работа с клавиатуры, подписи у полей."],
        ["Наблюдаемость", "Ошибки входа и отправки писем попадают в логи с идентификатором запроса."],
        ["Обратная совместимость", "Вход партнёров и существующие разделы кабинета работают без изменений."],
    ],
    [4.4, 12.0],
    bold_first=True,
)

# ---------------------------------------------------------------- 12

h1(doc, "12. Критерии приёмки")

para(
    doc,
    "Работа считается выполненной, когда все сценарии ниже проходят на тестовом стенде "
    "и подтверждены на проде после миграции.",
)


add_table(
    doc,
    ["ID", "Сценарий", "Ожидаемый результат"],
    [
        ["A-01", "Первый запуск: ввод bootstrap-ключа", "Создан супер-админ, ключ погашен, /setup недоступен."],
        ["A-02", "Повторный ввод того же ключа", "Отказ, событие в журнале."],
        ["A-03", "Создание приглашения на почту", "Приглашение в статусе «Активно», ссылка копируется."],
        ["A-04", "Переход по ссылке и регистрация", "Аккаунт создан, выполнен вход, ссылка погашена."],
        ["A-05", "Повторный переход по ссылке", "Сообщение «Ссылка уже использована»."],
        ["A-06", "Просроченная ссылка", "Сообщение об истечении срока, приглашение «Просрочено», доступен перевыпуск."],
        ["A-07", "Попытка сменить почту при регистрации", "Поле недоступно, подмена отклоняется сервером."],
        ["A-08", "Вход по почте и по логину", "Оба способа работают, журнал фиксирует вход."],
        ["A-09", "Пять неудачных попыток входа", "Блокировка на 15 минут, запись в журнале."],
        ["A-10", "Блокировка админа супер-админом", "Активная сессия завершена, вход невозможен."],
        ["A-11", "Попытка заблокировать себя или последнего супер-админа", "Отказ с понятной ошибкой."],
        ["A-12", "Отзыв приглашения", "Ссылка сразу перестаёт работать."],
        ["A-13", "Прямой переход на форму регистрации без токена", "Страница недоступна, публичной формы нет."],
        ["A-14", "Миграция", "Общий логин отключён, все действующие админы зарегистрированы."],
        ["A-15", "Сброс пароля", "Письмо приходит, ссылка одноразовая, сессии завершены."],
    ],
    [1.6, 7.4, 7.4],
)

# ---------------------------------------------------------------- 13

h1(doc, "13. Тестирование")

h2(doc, "13.1. Уровни тестирования")
add_table(
    doc,
    ["Уровень", "Что проверяется"],
    [
        ["Модульные", "Валидация логина и пароля, генерация и проверка токенов, расчёт срока действия."],
        ["Интеграционные", "API приглашений, регистрации, входа, управления доступами, журнала."],
        ["Сквозные (E2E)", "Полный путь: приглашение → регистрация → вход → блокировка → журнал."],
        ["Ручные", "Письма, мобильная вёрстка, понятность ошибок, поведение при недоступной почте."],
    ],
    [4.0, 12.4],
    bold_first=True,
)

h2(doc, "13.2. Обязательные негативные проверки")
bullets(
    doc,
    [
        "Приглашение на занятую почту и на занятый логин.",
        "Просроченный, отозванный и уже использованный токен.",
        "Слабый пароль, пароль без цифр, пароль короче 10 символов.",
        "Попытка обратиться к административным методам под ролью «Админ» и «Партнёр».",
        "Одновременная регистрация по одной ссылке с двух устройств (второй запрос отклоняется).",
        "Отправка формы без сети и повторная отправка после ошибки.",
        "Попытка изменить роль самому себе и заблокировать последнего супер-админа.",
    ],
)

h2(doc, "13.3. Приёмочные данные")
para(
    doc,
    "Тестирование проводится на копии боевой базы с обезличенными персональными данными. "
    "Почтовый сервер — тестовый ящик; дополнительно проверяется сценарий без почты (ссылка вручную).",
)

# ---------------------------------------------------------------- 14

h1(doc, "14. Порядок внедрения и миграция")

h2(doc, "14.1. Этапы")
add_table(
    doc,
    ["№", "Этап", "Результат", "Оценка"],
    [
        ["1", "Согласование ТЗ и макетов", "Подписанное ТЗ, утверждённые экраны", "2 рабочих дня"],
        ["2", "Модель данных и миграции", "Миграции, тестовые данные", "1 день"],
        ["3", "Серверная часть", "API приглашений, регистрации, входа, управления, журнала", "5 дней"],
        ["4", "Клиентская часть", "Семь экранов и пункт меню", "5 дней"],
        ["5", "Почтовые шаблоны", "Письма приглашения и сброса пароля", "1 день"],
        ["6", "Тестирование", "Протокол тестирования, исправленные дефекты", "3 дня"],
        ["7", "Пилот на 2–3 админах", "Подтверждение сценариев на реальных людях", "2 дня"],
        ["8", "Миграция и коммуникация", "Общий логин отключён, все приглашены", "1 день"],
    ],
    [0.9, 5.0, 7.6, 2.9],
)

para(
    doc,
    "Итого — около 20 рабочих дней при одном исполнителе; при параллельной работе над серверной "
    "и клиентской частью — 3 недели. Оценка ориентировочная и уточняется после согласования.",
    size=9.5,
    color=MUTED,
)

h2(doc, "14.2. План коммуникации")
add_table(
    doc,
    ["Когда", "Что происходит"],
    [
        ["За 5 рабочих дней", "Письмо администраторам: зачем переходим, что делать, к кому вопросы."],
        ["За 1 рабочий день", "Напоминание и короткая инструкция из трёх шагов."],
        ["День переключения, 10:00", "Общий логин отключается, приглашения уходят на почты."],
        ["День переключения + 1", "Контроль регистраций, помощь тем, у кого не получилось."],
        ["Через 3 дня", "Отчёт: кто зарегистрировался, кто нет; повторные приглашения."],
    ],
    [5.0, 11.4],
    bold_first=True,
)

h2(doc, "14.3. Порядок отката")
para(
    doc,
    "Если в день переключения значительная часть администраторов не может войти, ответственный "
    "включает флаг временного доступа к общей учётной записи на срок до 24 часов. "
    "Приглашения при этом остаются действительными, повторная миграция выполняется после устранения причины.",
)

# ---------------------------------------------------------------- 15

h1(doc, "15. Риски и меры")

add_table(
    doc,
    ["Риск", "Вероятность", "Влияние", "Мера"],
    [
        ["Письма попадают в спам", "Средняя", "Высокое", "Настроить SPF/DKIM/DMARC; ссылка всегда доступна в интерфейсе."],
        ["Сотрудники не успели зарегистрироваться", "Средняя", "Среднее", "Уведомления заранее, окно отката 24 часа, поддержка."],
        ["Утрата доступа ко всем супер-админам", "Низкая", "Критическое", "Минимум два супер-админа, серверная процедура восстановления."],
        ["Путаница «почта или логин»", "Средняя", "Низкое", "Подсказки на форме входа, вход по обоим идентификаторам."],
        ["Ссылка приглашения утекла", "Низкая", "Среднее", "Привязка к почте, одноразовость, срок 72 часа."],
        ["Ошибка миграции данных", "Низкая", "Высокое", "Резервная копия, прогон на копии базы, обратимая миграция."],
        ["Сопротивление сотрудников", "Средняя", "Среднее", "Объяснение выгоды, простая инструкция, помощь в день Х."],
    ],
    [6.0, 2.6, 2.6, 5.2],
    font_size=8.6,
)

# ---------------------------------------------------------------- 16

h1(doc, "16. Открытые вопросы")

para(
    doc,
    "Вопросы ниже нужно закрыть до старта разработки: от них зависят объём работ и сроки.",
)

add_table(
    doc,
    ["№", "Вопрос", "Варианты", "Решение"],
    [
        ["1", "Сколько ролей вводим?", "Две (супер-админ, админ) или три (+ сотрудник)", ""],
        ["2", "Вход по логину или только по почте?", "Почта и логин / только почта", ""],
        ["3", "Через какой сервис отправляем письма?", "Яндекс 360, Mail.ru для бизнеса, SMTP-провайдер", ""],
        ["4", "Кто второй супер-администратор?", "ФИО сотрудника", ""],
        ["5", "Дата переключения", "Конкретная дата и время", ""],
        ["6", "Нужна ли 2FA для супер-админов?", "Да, отдельным этапом / нет", ""],
        ["7", "Нужен ли экспорт журнала?", "CSV / нет", ""],
        ["8", "Срок хранения журнала", "12 месяцев / иной", ""],
    ],
    [0.9, 5.0, 7.0, 3.5],
)

# ---------------------------------------------------------------- 17 / приложение

h1(doc, "17. Приложения", page_break=True)

para(doc, "Приложение А. Макеты экранов", size=12, bold=True, color=INK, space_before=4, space_after=8)

images = [
    ("01-login.png", "Рисунок А.1 — Экран входа: публичной регистрации нет, только вход по личным данным."),
    ("02-admins.png", "Рисунок А.2 — Раздел «Админы и доступы»: состав, роли, статусы, счётчики."),
    ("03-invite-modal.png", "Рисунок А.3 — Создание приглашения: почта, роль, срок действия ссылки."),
    ("04-invite-created.png", "Рисунок А.4 — Приглашение создано: ссылка, срок, копирование."),
    ("05-accept-invite.png", "Рисунок А.5 — Регистрация по приглашению: почта закреплена, логин и пароль задаёт человек."),
    ("06-journal.png", "Рисунок А.6 — Журнал доступа: кто, что, когда, с какого адреса."),
    ("07-first-run.png", "Рисунок А.7 — Первый запуск: одноразовый ключ из консоли сервера."),
]

for filename, cap in images:
    path = os.path.join(SHOTS, filename)
    pic_par = doc.add_paragraph()
    pic_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic_par.paragraph_format.space_before = Pt(6)
    pic_par.paragraph_format.space_after = Pt(2)
    pic_par.add_run().add_picture(path, width=Cm(15.6))
    caption(doc, cap)

doc.add_page_break()
para(doc, "Приложение Б. Шаблон письма-приглашения", size=12, bold=True, color=INK, space_after=8)

callout(
    doc,
    "Тема письма",
    "Доступ в кабинет ЮРИТЕХ — приглашение для {email}",
)

para(doc, "Здравствуйте!", space_after=6)
para(
    doc,
    "{Имя пригласившего} пригласил(а) вас в кабинет ЮРИТЕХ с ролью «{Роль}».",
    space_after=6,
)
para(
    doc,
    "Чтобы создать личный аккаунт, перейдите по ссылке:",
    space_after=6,
)
para(doc, "{Ссылка}", bold=True, color=ACCENT, space_after=6)
para(
    doc,
    "Ссылка действует до {дата и время} и может быть использована один раз. "
    "Почта {email} уже закреплена за приглашением — изменить её нельзя.",
    space_after=6,
)
para(
    doc,
    "Если вы не ожидали это письмо, просто проигнорируйте его: без перехода по ссылке ничего не произойдёт.",
    space_after=12,
)
para(doc, "ЮРИТЕХ · юридическая онлайн-платформа · finzdorovie.ru", size=9, color=MUTED)

doc.add_page_break()
para(doc, "Приложение В. Чек-лист супер-администратора", size=12, bold=True, color=INK, space_after=8)

bullets(
    doc,
    [
        "Проверить, что в системе два супер-администратора.",
        "Пригласить всех действующих администраторов на их рабочие почты.",
        "Убедиться, что каждый зарегистрировался и хотя бы раз вошёл.",
        "Отключить общую учётную запись и убедиться, что вход под ней невозможен.",
        "Проверить журнал: все приглашения и регистрации видны.",
        "Напомнить сотрудникам, что пароль нельзя передавать коллегам.",
    ],
)

doc.core_properties.title = "ТЗ: персональные учётные записи администраторов"
doc.core_properties.subject = "Партнёрский кабинет ЮРИТЕХ"
doc.core_properties.author = "ООО «ЮРИТЕХ»"
doc.core_properties.comments = "Версия 1.0 от 05.11.2026"

doc.save(OUT)
print("saved:", OUT)
