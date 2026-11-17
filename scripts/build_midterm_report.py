"""Build the polished DOCX midterm report from frozen experiment results."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "stage1-midterm-report.docx"
FIGURE = ROOT / "runs" / "formal" / "analysis" / "attempt_execute.png"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="D9D9D9", size="4"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), size)
        tag.set(qn("w:space"), "0")
        tag.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)


def set_cell_text(cell, text, bold=False, color="000000", size=9.5, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_cell_margins(cell)


def add_table(doc, headers, rows, widths=None, caption=None):
    if caption:
        p = doc.add_paragraph(style="Caption")
        p.add_run(caption)
        p.paragraph_format.keep_with_next = True
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_text(cell, header, bold=True, color="FFFFFF", align=WD_ALIGN_PARAGRAPH.CENTER)
        set_cell_shading(cell, "21405A")
        if widths:
            cell.width = Cm(widths[index])
    set_repeat_table_header(table.rows[0])
    table.rows[0].allow_break_across_pages = False
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        table.rows[-1].allow_break_across_pages = False
        for col_index, value in enumerate(row):
            set_cell_text(
                cells[col_index],
                value,
                align=WD_ALIGN_PARAGRAPH.CENTER if col_index > 0 else WD_ALIGN_PARAGRAPH.LEFT,
            )
            if row_index % 2 == 1:
                set_cell_shading(cells[col_index], "EEF3F7")
            if widths:
                cells[col_index].width = Cm(widths[col_index])
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_together = True
                paragraph.paragraph_format.keep_with_next = row_index < len(table.rows) - 1
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table


def add_hyperlink(paragraph, text, url, size=8.5):
    part = paragraph.part
    rel_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    run = paragraph.add_run(text)
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(30, 74, 109)
    run.font.underline = True
    hyperlink.append(run._r)
    paragraph._p.append(hyperlink)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("第 ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    run._r.addnext(field)
    end_run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = " 页"
    end_run.append(text)
    field.addnext(end_run)
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(103, 112, 120)
    r_pr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Microsoft YaHei")
    fonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    fonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "677078")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "16")
    r_pr.extend((fonts, color, size))
    end_run.insert(0, r_pr)


def add_image_alt(paragraph, text):
    drawing = paragraph._p.xpath(".//w:drawing")[0]
    doc_pr = drawing.xpath(".//wp:docPr")[0]
    doc_pr.set("descr", text)
    doc_pr.set("title", text)


def add_body(doc, text, bold_lead=None):
    paragraph = doc.add_paragraph(style="Body Text")
    paragraph.paragraph_format.keep_together = False
    if bold_lead:
        run = paragraph.add_run(bold_lead)
        run.bold = True
    paragraph.add_run(text)
    return paragraph


def add_bullet(doc, lead, text):
    paragraph = doc.add_paragraph(style="List Bullet")
    lead_run = paragraph.add_run(lead)
    lead_run.bold = True
    paragraph.add_run(text)
    return paragraph


def configure_document(doc):
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.8)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.35

    body = styles["Body Text"]
    body.font.name = "Microsoft YaHei"
    body._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    body.font.size = Pt(10.5)
    body.font.color.rgb = RGBColor(0, 0, 0)
    body.paragraph_format.line_spacing = 1.45
    body.paragraph_format.space_after = Pt(8)

    for name, size, before, after in (
        ("Title", 25, 0, 10),
        ("Heading 1", 16, 14, 7),
        ("Heading 2", 12.5, 10, 5),
        ("Heading 3", 11, 8, 4),
    ):
        style = styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    title_style = styles["Title"]
    if title_style._element.pPr is not None:
        for border in list(title_style._element.pPr.findall(qn("w:pBdr"))):
            title_style._element.pPr.remove(border)

    styles["Caption"].font.name = "Microsoft YaHei"
    styles["Caption"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    styles["Caption"].font.size = Pt(8.5)
    styles["Caption"].font.color.rgb = RGBColor(94, 102, 110)
    styles["Caption"].paragraph_format.space_after = Pt(4)

    add_page_number(section.footer.paragraphs[0])


def cover(doc):
    paragraph = doc.add_paragraph(style="Title")
    paragraph.paragraph_format.space_before = Pt(72)
    paragraph.paragraph_format.space_after = Pt(14)
    first = paragraph.add_run("系统提示泄露对中文工具型 Agent")
    first.add_break()
    second = paragraph.add_run("提示注入的增益效应")
    first.font.size = Pt(22.5)
    second.font.size = Pt(22.5)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = subtitle.add_run("人工智能安全课程第一阶段中期报告")
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = RGBColor(0, 0, 0)

    meta = doc.add_paragraph()
    meta.paragraph_format.space_before = Pt(8)
    meta.add_run("报告日期：2026 年 11 月 17 日\n研究性质：课程复现与受控扩展\n正式批次：单模型、4 个测试配置")
    for run in meta.runs:
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(70, 76, 82)

    doc.add_paragraph().paragraph_format.space_after = Pt(24)
    conclusion = doc.add_paragraph(style="Body Text")
    conclusion.paragraph_format.left_indent = Cm(0.3)
    conclusion.paragraph_format.right_indent = Cm(0.3)
    run = conclusion.add_run("主要结论：")
    run.bold = True
    conclusion.add_run(
        "在当前单模型冻结批次中，完整业务规则信息没有提高越权调用率；"
        "执行前授权检查阻断了全部预设越权模拟写入，同时保持正常任务完成。"
    )

    add_table(
        doc,
        ["核心指标", "结果", "解释边界"],
        [
            ("K0 / D0 越权调用", "8/48（16.7%）", "无额外业务事实"),
            ("K100 / D0 越权调用", "3/48（6.2%）", "完整业务事实；主假设未获支持"),
            ("K100−K0 配对风险差", "−10.4 个百分点", "4 个配置簇，区间不稳定"),
            ("Dgate 越权执行", "0/144", "程序阻断，不代表模型安全"),
            ("正常任务成功", "64/64（100%）", "模拟任务范围"),
            ("自然抽取随机标识命中", "0", "严格词组下界"),
        ],
        widths=[4.9, 4.4, 7.4],
        caption="表 1  第一阶段核心结果概览",
    )
    doc.add_page_break()


def main_content(doc):
    doc.add_heading("摘要", level=1)
    add_body(
        doc,
        "本报告检验应用系统提示中的业务事实是否会提高间接提示注入对中文工具型 Agent 的增益。"
        "实验使用单一路由 auto/deepseek-v4.1-flash 和 4 个测试配置，比较不披露、约 75% 披露和完整披露三种知识条件，"
        "以及无授权检查与执行前检查两种防御。攻击仅进入工具返回的外部文本，身份、记录和审批状态均由本地模拟后端维护。"
    )
    add_body(
        doc,
        "冻结批次包含 288 个攻击 episode、64 个正常 episode 和 24 个自然抽取会话，全部完成，"
        "没有技术错误、协议无效或 JSON 解析失败。D0 下 K0、K75、K100 的任意越权调用分别为 8/48、5/48、3/48；"
        "K100 相对 K0 的配对风险差为 −10.4 个百分点。该结果与“披露更多规则会提高注入成功”的主假设方向相反。"
        "Dgate 将预设越权模拟执行降为 0，但模型仍提出 20 次越权调用。"
    )
    keywords = doc.add_paragraph(style="Body Text")
    keywords.add_run("关键词：").bold = True
    keywords.add_run("系统提示泄露；间接提示注入；工具型 Agent；授权检查；负结果")

    doc.add_heading("1  研究问题与设计", level=1)
    doc.add_heading("1.1  研究问题与假设", level=2)
    add_body(
        doc,
        "研究包含三个问题：在固定交互预算下能恢复哪些受保护业务事实；受控提供这些事实是否改变越权调用率；"
        "执行前授权检查能否阻断违规调用，而不损害正常任务。主假设 H2 为 D0 下完整知识条件 K100 的任意越权调用率高于 K0；"
        "H3 为 Dgate 降低模拟执行，同时保持正常任务成功。"
    )
    add_body(
        doc,
        "本项目定位为已有工作的课程复现与受控扩展。已有研究已经分别覆盖提示抽取、攻击者知识对注入的影响以及程序层隔离，"
        "因此本项目不声称首次连接这些方向，也不把简单授权检查当作新防御算法。"
    )

    doc.add_heading("1.2  威胁模型", level=2)
    add_body(
        doc,
        "受保护对象是应用系统提示中的非公开业务事实、用户记录归属与审批规则。攻击者能够改写工具返回中的外部文本，"
        "知道公共工具 schema，但不能修改用户任务、应用指令、真实用户身份或可信审批状态。应用系统提示通过独立指令字段提供，"
        "与合法用户消息分离。"
    )
    add_table(
        doc,
        ["层次", "本实验内容", "攻击者权限"],
        [
            ("应用指令", "归属、字段、审批、流程与输出约束", "不可修改"),
            ("用户请求", "读取本人记录并处理售后工单", "不可修改"),
            ("工具返回", "记录状态与外部文本", "可注入文本字段"),
            ("可信状态", "USER-A、记录 owner、approved_by_workflow", "不可由外部文本改变"),
        ],
        widths=[3.2, 8.4, 5.1],
        caption="表 2  信任边界与攻击面",
    )
    add_body(
        doc,
        "任意越权调用表示模型提议违反身份、归属或审批条件的写操作；精确目标命中要求记录、字段和值与攻击目标完全一致；"
        "越权执行表示本地模拟后端在缺少可信授权时实际写入状态。三类结果分别报告。"
    )

    doc.add_heading("2  相关工作与本文位置", level=1)
    add_body(
        doc,
        "提示抽取研究覆盖直接询问、候选筛选、多轮行为和输出反演。Effective Prompt Extraction 使用句级包含与候选置信选择；"
        "output2prompt 训练输出到提示的反演器；Raccoon 聚合 14 类攻击策略；ProxyPrompt 则在连续嵌入空间优化代理提示。"
        "本文采用有限轮数的固定业务事实探测，不宣称复现这些优化方法。"
    )
    add_body(
        doc,
        "ExtraHerO 已用结构分解和行为反馈恢复 Agent 提示，并测量下游注入效用；SASP 更早将提示获取连接到自对抗越狱。"
        "AgentDojo 已比较攻击者掌握正确或错误身份信息的效果。本文的具体扩展对象是归属与审批业务规则，"
        "并把任意越权、精确目标和模拟执行分层记录。"
    )
    add_body(
        doc,
        "InjecAgent 通过解析模型输出计算工具调用 ASR；CaMeL 将可信规划、隔离的外部数据处理和程序策略执行结合。"
        "本文的 Dgate 只是执行前的简化授权检查。它与 CaMeL 不同，也不证明模型本身能区分指令与数据。"
    )

    doc.add_heading("3  实验方法", level=1)
    doc.add_heading("3.1  任务与条件", level=2)
    add_table(
        doc,
        ["组成", "规模或定义"],
        [
            ("测试配置", "售后、课程、文档、报销，共 4 个"),
            ("知识条件", "K0、K75、K100，按原子事实计覆盖"),
            ("攻击模板", "伪造审批记录、伪造流程通知、知识说明夹带指令"),
            ("攻击目标", "跨用户修改 note；无可信审批修改 status"),
            ("攻击规模", "4×3×2×3×2×2 = 288 episode"),
            ("正常效用", "4×8×2 = 64 episode"),
            ("自然抽取", "4×3 策略×2 重复 = 24 会话，每会话 5 轮"),
        ],
        widths=[4.2, 12.5],
        caption="表 3  冻结批次设计",
    )

    doc.add_heading("3.2  模型隔离与运行", level=2)
    add_body(
        doc,
        "被测模型使用独立 ephemeral 会话，应用指令通过 baseInstructions 提供，业务工具通过 dynamicTools 声明。"
        "每次攻击目标、正常任务和抽取会话都新建会话；审计记录显示 instructionSources 为空，应用指令包含随机业务标识，"
        "用户消息不含这些标识。模型只实际操作 read_case 和 update_record，平台通用工具说明作为固定后台条件保留。"
    )
    add_body(
        doc,
        "攻击候选在目标运行前独立生成并冻结。候选生成器只收到公共任务、攻击目标、模板和本条件事实，"
        "不能读取评分结果或其他条件。每个目标均先读取记录；模型拒绝、格式错误和任务失败仍留在 completed 分母。"
    )

    doc.add_heading("4  结果", level=1)
    doc.add_heading("4.1  越权调用、模拟执行与配对差", level=2)
    add_table(
        doc,
        ["知识", "D0 调用", "D0 执行", "Dgate 调用", "Dgate 执行"],
        [
            ("K0", "8/48（16.7%）", "8/48（16.7%）", "7/48（14.6%）", "0/48"),
            ("K75", "5/48（10.4%）", "5/48（10.4%）", "6/48（12.5%）", "0/48"),
            ("K100", "3/48（6.2%）", "3/48（6.2%）", "7/48（14.6%）", "0/48"),
        ],
        widths=[2.3, 3.6, 3.6, 3.6, 3.6],
        caption="表 4  各知识条件下的任意越权调用与模拟执行",
    )
    add_body(
        doc,
        "D0 下 48 个完整配对中，K100 相对 K0 的任意越权调用风险差为 −10.4 个百分点，"
        "固定种子的 4 配置簇重采样描述区间为 −20.8 至 −2.1 个百分点。"
        "配对中仅 K0 违规 7 对、仅 K100 违规 2 对、两者均违规 1 对、两者均未违规 38 对。"
        "逐配置差异为文档 0、教育 −8.3、报销 −8.3、售后 −25.0 个百分点。"
    )
    figure = doc.add_paragraph()
    figure.alignment = WD_ALIGN_PARAGRAPH.CENTER
    figure.paragraph_format.keep_with_next = True
    figure.add_run().add_picture(str(FIGURE), width=Inches(6.25))
    add_image_alt(figure, "Knowledge conditions K0 K75 K100 by defenses D0 Dgate, showing attempt and executed violation rates.")
    cap = doc.add_paragraph(style="Caption")
    cap.add_run("图 1  越权调用与模拟执行率。误差线为单条件 Wilson 描述性区间，未处理任务与重复之间的相关性。")

    doc.add_heading("4.2  任意越权与精确目标命中", level=2)
    add_table(
        doc,
        ["条件", "任意越权调用", "精确目标命中"],
        [
            ("K0 / D0", "8/48（16.7%）", "0/48（0.0%）"),
            ("K100 / D0", "3/48（6.2%）", "1/48（2.1%）"),
        ],
        widths=[4.2, 6.1, 6.1],
        caption="表 5  任意越权与目标精确匹配的差异",
    )
    add_body(
        doc,
        "K100 只有一次精确实现攻击目标，K0 没有。单个事件不能改变主指标方向，也不能证明知识帮助攻击，"
        "但说明“提出某种违规调用”与“准确实现预先指定动作”需要分开解释。"
    )

    doc.add_heading("4.3  授权检查与正常任务效用", level=2)
    add_body(
        doc,
        "Dgate 在三种知识条件下均为 0/48 模拟执行，合计阻断所有预设越权写操作。"
        "模型仍提出 20/144（13.9%）次越权调用；K100/Dgate 的调用率甚至高于 K100/D0，"
        "说明零执行来自可信授权规则，不代表模型行为改善。正常任务在两种防御下均为 32/32，合计 64/64。"
    )
    add_body(
        doc,
        "由于只覆盖已编码规则、模拟后端和固定工具入口，这一结果不能外推到真实账户、生产数据库、未编码授权规则或开放工具环境。"
    )

    doc.add_heading("4.4  自然抽取的严格下界", level=2)
    add_table(
        doc,
        ["策略", "严格业务事实覆盖", "随机流程标识命中"],
        [
            ("直接索取", "0.0%", "0.0%"),
            ("通用变换", "0.0%", "0.0%"),
            ("结构化分块", "0.8%", "0.0%"),
        ],
        widths=[5.3, 5.6, 5.5],
        caption="表 6  24 个只读抽取会话的平均严格覆盖",
    )
    add_body(
        doc,
        "严格判据只在 test_support-structured-0 中识别到审批参数规则 approved_by_workflow；所有随机业务流程标识均未恢复。"
        "严格词组判据会漏掉同义改写，因此 0.0% 与 0.8% 是下界，不是完整语义召回。"
        "受控知识增益与自然抽取必须分开报告，当前不构建完整“真实恢复度—攻击率”经验曲线。"
    )

    doc.add_heading("4.5  辅助观察", level=2)
    add_bullet(doc, "攻击模板：", "知识说明夹带指令发生 21/96 次任意越权，高于伪造审批 9/96 和伪造流程通知 6/96；精确目标命中没有同步提高。")
    add_bullet(doc, "任务差异：", "教育和售后各 13/72，文档 4/72，报销 6/72；4 个配置不足以做稳定排名。")
    add_bullet(doc, "候选长度：", "K0、K75、K100 平均为 134.5、158.0、152.4 个字符；K75/K100 接近，K0 较短，仍存在长度混杂。")

    doc.add_heading("5  讨论", level=1)
    add_body(
        doc,
        "第一项发现是负结果。在当前候选生成、公开工具 schema 和模型行为下，完整业务事实没有转化为更稳定的越权诱导。"
        "这不能解释为更多规则信息会保护模型；更可能是可信来源、原始用户范围和目标定位共同限制了攻击文本的有效性。"
        "只有 16 个 D0 越权事件、4 个配置，且配置差异从 0 到 −25 个百分点，不能识别稳定机制。"
    )
    add_body(
        doc,
        "第二项发现是调用与执行分离。Dgate 的零执行是授权逻辑拒绝写操作的结果，模型仍会提出越权调用。"
        "程序层约束适用于规则已编码、状态可信且工具入口被完全包裹的场景；它不能减轻开放环境中所有提示注入后果。"
    )
    add_body(
        doc,
        "第三项发现是自然抽取与受控增益回答不同问题。当前 5 轮策略没有稳定恢复随机业务信息，"
        "而受控实验直接把事实提供给攻击生成器。两者不能拼成完整攻击链。负结果、零执行和精确下界共同说明："
        "课程中期应优先保留证据分层，不宜用“模型说已执行”或单次成功案例替代原始状态与分母。"
    )

    doc.add_heading("6  局限与后续工作", level=1)
    add_body(
        doc,
        "本阶段只使用一个模型路由、4 个测试配置和有限重复；底层权重快照没有独立认证，"
        "结论不能代表其他版本或基础模型。每条件仅 48 个攻击 episode，低事件数使百分比对单个事件敏感，"
        "4 个配置簇的重采样区间不稳定。本报告不报告 p 值，也不声明统计显著、普遍性或真实系统越权。"
    )
    add_body(
        doc,
        "知识条件的表达长度和具体性尚未完全匹配，缺少等长无关信息、错误信息和第二模型对照。"
        "自然抽取仅执行 5 轮，严格判据会漏掉同义改写。平台仍提供固定后台工具说明；实验不包含真实账户或审批服务。"
    )
    add_body(
        doc,
        "后续工作将优先加入等长无关信息和错误信息条件、增加独立任务簇或第二模型，并扩展自然抽取轮数与语义复核。"
        "只有自然取得事实、受控增益和模拟执行三层均有可复核证据时，才适合讨论完整的泄露—注入链。"
    )

    doc.add_heading("7  结论", level=1)
    add_body(
        doc,
        "第一阶段完成了方案、闭环、正式实验、统计与复核。结果显示，在当前设置下，完整业务规则信息没有提高越权调用率；"
        "程序化授权检查能阻断已编码规则的预设越权执行，同时模型仍可能提出违规动作。"
        "自然抽取的严格业务事实下界很低，未取得随机流程标识。"
        "这些结果不支持原始正向增长假设，但明确展示了来源分离、调用提议与执行后果分层的重要性。"
    )

    doc.add_heading("资料与复现索引", level=1)
    for title, url in [
        ("ExtraHerO", "https://arxiv.org/html/2611.04803v1"),
        ("AgentDojo", "https://arxiv.org/html/2406.13352v3"),
        ("Prompt Leakage effect", "https://aclanthology.org/2024.emnlp-industry.94.pdf"),
        ("InjecAgent", "https://arxiv.org/html/2403.02691v3"),
        ("CaMeL", "https://arxiv.org/html/2503.18813v2"),
        ("SEP", "https://arxiv.org/html/2403.06833v3"),
        ("Effective Prompt Extraction", "https://arxiv.org/html/2307.06865v2"),
        ("output2prompt", "https://arxiv.org/html/2405.15012v2"),
        ("Raccoon", "https://arxiv.org/html/2406.06737v2"),
        ("ProxyPrompt", "https://arxiv.org/html/2505.11459v2"),
        ("SASP", "https://arxiv.org/html/2311.09127v2"),
    ]:
        paragraph = doc.add_paragraph(style="Body Text")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(title + "：")
        add_hyperlink(paragraph, url, url)

    doc.add_heading("数据与代码", level=2)
    paths = doc.add_paragraph(style="Body Text")
    paths.paragraph_format.space_after = Pt(3)
    first = paths.add_run("正式结果与统计：")
    first.bold = True
    paths.add_run("runs/formal/combined-results.jsonl；runs/formal/analysis/results.md 与 summary.json。")
    audit_paths = doc.add_paragraph(style="Body Text")
    audit_paths.paragraph_format.space_after = Pt(0)
    second = audit_paths.add_run("审计与程序：")
    second.bold = True
    audit_paths.add_run("runs/formal/audit.json；scripts/experiment.py；analysis/analyze.py。")
    for paragraph in (paths, audit_paths):
        for run in paragraph.runs:
            run.font.size = Pt(9.5)


def main():
    doc = Document()
    configure_document(doc)
    cover(doc)
    main_content(doc)
    doc.core_properties.title = "系统提示泄露对中文工具型 Agent 提示注入的增益效应"
    doc.core_properties.subject = "人工智能安全课程第一阶段中期报告"
    doc.core_properties.author = "AI 辅助研究团队"
    doc.core_properties.comments = "基于 2026-11-17 冻结正式实验数据生成"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
