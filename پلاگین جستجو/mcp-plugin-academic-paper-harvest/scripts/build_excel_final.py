#!/usr/bin/env python
"""Build final Excel with 10 columns (including Persian title translation).

Usage:
    python build_excel_final.py <lit_table_final.json> <output.xlsx>
"""
import sys, json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def main():
    if len(sys.argv) < 3:
        print("Usage: python build_excel_final.py <lit_table_final.json> <output.xlsx>")
        sys.exit(1)
    with open(sys.argv[1], encoding='utf-8') as f:
        data = json.load(f)
    rows = data['rows']
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "مرور ادبیات"
    
    # Styles
    header_font = Font(name='B Nazanin', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    data_font = Font(name='B Nazanin', size=10)
    data_align = Alignment(vertical='top', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='B4C6E7'),
        right=Side(style='thin', color='B4C6E7'),
        top=Side(style='thin', color='B4C6E7'),
        bottom=Side(style='thin', color='B4C6E7'),
    )
    alt_fill = PatternFill(start_color='D6E4F0', end_color='D6E4F0', fill_type='solid')
    
    # 10 headers
    headers = [
        'شماره',
        'نویسنده(ها)',
        'سال',
        'عنوان (Original)',
        'عنوان (فارسی)',
        'مجله/منبع',
        'بُعد پایان‌نامه',
        'روش‌شناسی',
        'یافته/مفهوم کلیدی',
        'ارتباط با پایان‌نامه',
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
    
    # Column widths
    widths = [5, 25, 7, 42, 42, 28, 14, 16, 52, 32]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    
    # Data rows
    for i, r in enumerate(rows):
        row_num = i + 2
        vals = [
            i + 1,
            r['authors'],
            r['year'],
            r['title'],
            r['title_fa'],
            r['journal'],
            r['dimension'],
            r['method'],
            r['finding'],
            r['relevance'],
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(row=row_num, column=col, value=v)
            cell.font = data_font
            cell.alignment = data_align
            cell.border = thin_border
            if i % 2 == 1:
                cell.fill = alt_fill
    
    # Freeze header + auto-filter
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:J{len(rows)+1}"
    
    out_path = sys.argv[2]
    wb.save(out_path)
    print(f"Saved: {out_path}")
    print(f"Total rows: {len(rows)}")

if __name__ == "__main__":
    main()
