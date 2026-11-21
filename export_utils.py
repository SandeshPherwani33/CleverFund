"""
Export utilities for PDF generation and report sharing
"""

import io
import uuid
from datetime import datetime
from pathlib import Path
import json

# Try to import reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: reportlab not installed. PDF export will not be available.")


def generate_pdf_report(predictions: list, stats: dict) -> bytes:
    """
    Generate a PDF report from prediction data.
    
    Args:
        predictions: List of prediction records with name, funding, result, probability
        stats: Dictionary with total count and useML flag
    
    Returns:
        PDF file as bytes
    """
    if not PDF_AVAILABLE:
        raise RuntimeError("PDF generation not available. Install reportlab: pip install reportlab")
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elements.append(Paragraph("CleverFund Prediction Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Report metadata
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated on {timestamp}", meta_style))
    
    model_type = "ML (SMOTE+RF)" if stats.get('useML') else "Rule-Based"
    elements.append(Paragraph(f"Model: {model_type}", meta_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary section
    summary_style = ParagraphStyle(
        'SummaryTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    elements.append(Paragraph("Summary", summary_style))
    
    summary_data = [
        ["Total Predictions", str(stats.get('total', 0))],
        ["Report Generated", timestamp],
        ["Prediction Model", model_type]
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Predictions table
    if predictions:
        elements.append(Paragraph("Recent Predictions", summary_style))
        
        # Prepare table data
        table_data = [["Startup Name", "Funding", "Result", "Probability"]]
        
        for pred in predictions[:20]:  # Limit to 20 predictions
            name = pred.get('name', 'N/A')[:25]  # Truncate long names
            funding = pred.get('funding', 'N/A')
            result = pred.get('result', 'N/A')
            prob = pred.get('probability', 'N/A')
            
            table_data.append([name, funding, result, prob])
        
        # Create table
        pred_table = Table(table_data, colWidths=[2.2*inch, 1.4*inch, 1.2*inch, 1.2*inch])
        pred_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(pred_table)
    
    elements.append(Spacer(1, 0.2*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#94a3b8'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph("CleverFund - Startup Success Prediction System", footer_style))
    elements.append(Paragraph("This report is confidential and for internal use only", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF bytes
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def generate_share_url(predictions: list, stats: dict) -> str:
    """
    Generate a shareable URL by creating a temporary report file.
    
    Args:
        predictions: List of prediction records
        stats: Dictionary with statistics
    
    Returns:
        Shareable URL or unique ID
    """
    # Create a unique report ID
    report_id = str(uuid.uuid4())[:8]
    
    # Store report data temporarily
    report_data = {
        'id': report_id,
        'created_at': datetime.now().isoformat(),
        'predictions': predictions,
        'stats': stats
    }
    
    # Create reports directory if it doesn't exist
    reports_dir = Path('data/shared_reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Save report data
    report_file = reports_dir / f'{report_id}.json'
    with open(report_file, 'w') as f:
        json.dump(report_data, f)
    
    # Return the share URL (relative path that can be used by frontend)
    return f'/api/shared-report/{report_id}'


def get_shared_report(report_id: str) -> dict:
    """
    Retrieve a shared report by ID.
    
    Args:
        report_id: The report ID
    
    Returns:
        Report data dictionary or None if not found
    """
    report_file = Path('data/shared_reports') / f'{report_id}.json'
    
    if not report_file.exists():
        return None
    
    try:
        with open(report_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading report {report_id}: {e}")
        return None
