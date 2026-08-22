"""
Generates an A5 donation receipt that matches the All Saints' Cathedral printed format.
"""
import io
from reportlab.lib.pagesizes import A5
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from utils.helpers import amount_in_words


# ── Style helpers ─────────────────────────────────────────────
def _sty(name, **kw):
    return ParagraphStyle(name, **kw)


def generate_receipt_pdf(donation):
    """Return PDF bytes for the given Donation object."""
    buf = io.BytesIO()
    W, H = A5   # 148 × 210 mm

    doc = SimpleDocTemplate(buf, pagesize=A5,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm,   bottomMargin=8*mm)

    usable = W - 24*mm   # usable width

    # ── Styles ────────────────────────────────────
    hd   = _sty('hd',  fontSize=17, fontName='Helvetica-Bold',  alignment=TA_CENTER, spaceAfter=1)
    sub  = _sty('sub', fontSize=10, fontName='Helvetica-BoldOblique', alignment=TA_CENTER, spaceAfter=2)
    rcpt = _sty('rcpt',fontSize=11, fontName='Helvetica-Bold',  alignment=TA_CENTER,
                borderWidth=1, borderColor=colors.black, borderPadding=(3,10,3,10), spaceAfter=5,
                backColor=colors.Color(1, 0.9, 0.2)) # Yellow
    sm   = _sty('sm',  fontSize=9,  fontName='Helvetica')
    smb  = _sty('smb', fontSize=9,  fontName='Helvetica-Bold')
    smr  = _sty('smr', fontSize=9,  fontName='Helvetica', alignment=TA_RIGHT)
    row  = _sty('row', fontSize=8.5,fontName='Helvetica')
    rowb = _sty('rowb',fontSize=8.5,fontName='Helvetica-Bold')
    rem_sty = _sty('rem', fontSize=7, fontName='Helvetica-Oblique', textColor=colors.grey)
    tot  = _sty('tot', fontSize=9,  fontName='Helvetica-Bold', alignment=TA_RIGHT)
    foot = _sty('foot',fontSize=7,  fontName='Helvetica',
                textColor=colors.grey, alignment=TA_CENTER)
    sig  = _sty('sig', fontSize=9,  fontName='Helvetica-Bold', alignment=TA_RIGHT)
    Rc   = _sty('Rc',  fontSize=8.5,fontName='Helvetica', alignment=TA_RIGHT)
    Pc   = _sty('Pc',  fontSize=8.5,fontName='Helvetica', alignment=TA_CENTER)
    Nc   = _sty('Nc',  fontSize=8.5,fontName='Helvetica', alignment=TA_CENTER)

    story = []

    # ── Header ────────────────────────────────────
    story.append(Paragraph("All Saints' Cathedral, Nagpur", hd))
    story.append(Paragraph("<i>DIOCESE OF NAGPUR (C.N.I.)</i>", sub))
    story.append(Paragraph("RECEIPT", rcpt))

    # Receipt No + Date row
    nd_data = [[Paragraph(f"<b>No.</b>  {donation.receipt_number}", sm),
                Paragraph(f"<b>Date:</b>  {donation.donation_date.strftime('%d %b %Y')}", smr)]]
    nd_tbl = Table(nd_data, colWidths=[usable/2, usable/2])
    nd_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(nd_tbl)
    story.append(Spacer(1, 3*mm))

    # Received from
    story.append(Paragraph(
        f"Received with Thanks from &nbsp;&nbsp;<b>{donation.donor_display_name}</b>",
        sm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.black, spaceAfter=3))

    # Sum of Rupees
    total = donation.total_amount
    story.append(Paragraph(f"Sum of Rupees &nbsp;<b>{amount_in_words(total)}</b>", sm))

    # Payment mode
    mode_str = donation.payment_mode.value
    if donation.payment_reference:
        mode_str += f" No. {donation.payment_reference}"
    story.append(Paragraph(f"by &nbsp;<b>{mode_str}</b>", sm))
    story.append(Spacer(1, 3*mm))

    # ── Particulars table ─────────────────────────
    from models import DonationHead
    items_dict = {item.head: float(item.amount) for item in donation.items}
    remarks_dict = {item.head: item.remarks or '' for item in donation.items}

    hdr = [Paragraph('<b>S.N.</b>', smb),
           Paragraph('<b>PARTICULARS</b>', smb),
           Paragraph('<b>REMARKS</b>', smb),
           Paragraph('<b>Rs.</b>', smb),
           Paragraph('<b>Ps.</b>', smb)]
    tbl_data = [hdr]

    for i, head in enumerate(DonationHead, 1):
        amt = items_dict.get(head, 0)
        rem = remarks_dict.get(head, '')
        rs  = str(int(amt)) if amt else ''
        ps  = f"{int(round((amt % 1)*100)):02d}" if amt and (amt % 1) else ('' if not amt else '00')
        sty_row = rowb if amt else row
        tbl_data.append([
            Paragraph(str(i), Nc),
            Paragraph(head.value, sty_row),
            Paragraph(rem, rem_sty),
            Paragraph(rs, Rc),
            Paragraph(ps, Pc),
        ])

    # Total row
    rs_t = str(int(total))
    ps_t = f"{int(round((total % 1)*100)):02d}"
    tbl_data.append([
        Paragraph('', sm),
        Paragraph('<b>TOTAL</b>', tot),
        Paragraph('', sm),
        Paragraph(f'<b>{rs_t}</b>', _sty('tx', fontSize=9, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph(f'<b>{ps_t}</b>', _sty('ty', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)),
    ])

    col_w = [8*mm, usable - 8*mm - 25*mm - 20*mm - 12*mm, 25*mm, 20*mm, 12*mm]
    tbl = Table(tbl_data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ('GRID',         (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND',   (0,0), (-1,0),  colors.Color(1, 0.9, 0.2)), # Yellow header
        ('TEXTCOLOR',    (0,0), (-1,0),  colors.black),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',   (0,0), (-1,-1), 2),
        ('BOTTOMPADDING',(0,0), (-1,-1), 2),
        ('LEFTPADDING',  (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS',(0,1),(-1,-2), [colors.white, colors.Color(1, 1, 0.9)]), # Light yellow
        ('BACKGROUND',   (0,-1),(-1,-1), colors.Color(1, 0.9, 0.2)), # Yellow total row
    ]))
    doc.pagesize = A5
    doc.background = colors.Color(1, 1, 0.95) # Very light yellow for the whole page
    story.append(tbl)
    story.append(Spacer(1, 7*mm))

    # ── Signature ─────────────────────────────────
    story.append(Paragraph("Priest in Charge / Treasurer", sig))
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width='100%', thickness=0.3, color=colors.grey))
    story.append(Paragraph(
        "All Saints' Cathedral, Nagpur &nbsp;|&nbsp; Diocese of Nagpur (C.N.I.) &nbsp;|&nbsp; "
        "Computer Generated Receipt — No Signature Required", foot))

    doc.build(story)
    return buf.getvalue()
