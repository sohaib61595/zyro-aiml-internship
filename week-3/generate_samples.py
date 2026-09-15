"""
Sample generator script for Week 3 Document Intelligence.
Creates high-fidelity PDFs and scanned images for Invoices, Resumes, and Other documents.
"""

import os
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

os.makedirs("week-3/samples", exist_ok=True)

def create_pdf(filename: str, title: str, sections: list[tuple[str, str]]):
    """Creates a clean, styled digital PDF using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    
    # Draw header banner
    rect = fitz.Rect(40, 40, 555, 80)
    page.draw_rect(rect, color=(0.15, 0.25, 0.45), fill=(0.93, 0.95, 0.98), width=1)
    page.insert_text((55, 65), title, fontsize=16, fontname="helv", color=(0.1, 0.2, 0.4))
    
    y = 110
    for header, body in sections:
        if header:
            page.insert_text((40, y), header.upper(), fontsize=11, fontname="helv", color=(0.2, 0.3, 0.6))
            y += 18
            page.draw_line((40, y - 5), (555, y - 5), color=(0.8, 0.8, 0.8), width=0.5)
            y += 6
        
        for line in body.splitlines():
            if y > 800:
                page = doc.new_page(width=595, height=842)
                y = 50
            page.insert_text((40, y), line, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15))
            y += 15
        y += 12
        
    doc.save(os.path.join("week-3/samples", filename))
    doc.close()
    print(f"Generated PDF: {filename}")


# 1. invoice_standard.pdf
create_pdf(
    "invoice_standard.pdf",
    "TAX INVOICE - APEX DIGITAL SOLUTIONS LLC",
    [
        ("Vendor Information", "Apex Digital Solutions LLC\n142 Innovation Way, Suite 400, Austin, TX 78701\nTax ID: 84-2948192 | Email: billing@apexsolutions.io"),
        ("Client Details", "Billed To: Horizon Enterprises Inc.\nAttn: Accounts Payable\n900 Market Street, San Francisco, CA 94103"),
        ("Invoice Metadata", "Invoice Number: INV-2026-0814\nInvoice Date: 12-Jan-2026\nDue Date: 11-Feb-2026\nPayment Terms: Net 30"),
        ("Line Items", "Description                                  Qty     Rate         Amount\nCloud Infrastructure Setup                    1     $3,500.00    $3,500.00\nDatabase Optimization & Tuning               20       $150.00    $3,000.00\nSecurity Compliance Audit                     1     $1,250.00    $1,250.00"),
        ("Payment Summary", "Subtotal: $7,750.00\nSales Tax (8.25%): $639.38\nTotal Amount: $8,389.38\n\nPlease remit payment via ACH or Wire Transfer to Apex Digital Solutions.")
    ]
)

# 2. invoice_pkr_currency.pdf
create_pdf(
    "invoice_pkr_currency.pdf",
    "COMMERCIAL INVOICE - FALCON LOGISTICS PVT LTD",
    [
        ("Company Details", "Falcon Logistics Pvt Ltd\nPlot 45-C, Korangi Industrial Area, Karachi, Pakistan\nNTN: 4920194-7 | Sales Tax Reg: 17-00-4920-194-7"),
        ("Bill To", "Zenith Retailers Ltd\nMain Boulevard, Gulberg III, Lahore, Pakistan"),
        ("Invoice Info", "Invoice Number: FL-90421\nInvoice Date: 04/02/2026\nPO Number: PO-55291"),
        ("Consignment Details", "Description                            Qty     Rate (PKR)     Total (PKR)\nFreight Forwarding - Air Cargo           3        45,000        135,000\nCustoms Clearance Handling               1        25,000         25,000\nWarehousing Fee (14 days)               14         3,000         42,000"),
        ("Financial Summary", "Sub Total: PKR 202,000\nSindh Sales Tax (13%): PKR 26,260\nTotal Amount: PKR 228,260\n\nBank: Habib Bank Limited, Branch Code 0192, Account # 001928472910")
    ]
)

# 3. invoice_missing_fields.pdf (Intentionally missing Invoice Number and Total Amount)
create_pdf(
    "invoice_missing_fields.pdf",
    "PRO-FORMA BILLING STATEMENT - ACME CONSULTING",
    [
        ("Service Provider", "Company Name: Acme Business Consulting\n77 Commercial Way, Chicago, IL 60601"),
        ("Recipient", "Client: BlueSky Ventures Group"),
        ("Statement Date", "Date: 15-Mar-2026"),
        ("Description of Work", "Preliminary strategic assessment and market readiness evaluation.\nDetailed scope of deliverables scheduled for Q2.\nPayment terms subject to mutual milestone signoff.\n(Note: Total fee to be finalized upon scope approval.)")
    ]
)

# 4. resume_software_engineer.pdf
create_pdf(
    "resume_software_engineer.pdf",
    "CURRICULUM VITAE - MUHAMMAD USMAN",
    [
        ("Candidate Profile", "Name: Muhammad Usman\nEmail: usman.dev@gmail.com\nPhone: +92 300 1234567\nLocation: Lahore, Pakistan | LinkedIn: linkedin.com/in/usman-dev"),
        ("Professional Summary", "Dedicated Full Stack Software Engineer with 4+ years of experience designing high-throughput web applications, REST APIs, and distributed backend systems. Proficient in Python, Django, React, and PostgreSQL."),
        ("Education", "Bachelor of Science in Computer Science (BSCS)\nFAST-NUCES Lahore (2018 - 2022) | CGPA: 3.65"),
        ("Work Experience", "Senior Software Engineer | TechLogix (2022 - Present)\n- Architected microservices with FastAPI and Celery handling 2M+ requests daily.\n- Optimized SQL queries in PostgreSQL reducing database latency by 35%.\n- Built frontend dashboards using React, Next.js, and TailwindCSS.\n\nSoftware Engineer | Systems Ltd (2020 - 2022)\n- Developed RESTful APIs using Python, Flask, and Docker containerization."),
        ("Technical Skills", "Python, JavaScript, TypeScript, SQL, C++, Django, FastAPI, Flask, React, Next.js, Node.js, PostgreSQL, Redis, MongoDB, Docker, Kubernetes, AWS, Git, Linux")
    ]
)

# 5. resume_missing_contact.pdf (Missing phone number and email)
create_pdf(
    "resume_missing_contact.pdf",
    "PROFESSIONAL RESUME - TARIQ MEHMOOD",
    [
        ("Candidate Name", "Name: Tariq Mehmood\nAddress: Sector G-10, Islamabad, Pakistan"),
        ("Executive Summary", "Senior Project Manager and Scrum Master with over 8 years managing agile software delivery teams across enterprise banking systems."),
        ("Education", "Master of Business Administration (Project Management) - NUST (2014 - 2016)\nBS Computer Science - COMSATS (2010 - 2014)"),
        ("Experience", "Lead Agile Coach | Teradata Corporation (2018 - Present)\n- Facilitated daily standups, sprint planning, and backlog refinement.\n- Coached 5 cross-functional squads to increase sprint velocity by 28%."),
        ("Key Competencies", "Scrum, Agile, Jira, Confluence, Project Management, Leadership, Risk Management, Communication, Git")
    ]
)

# 6. other_business_memo.pdf
create_pdf(
    "other_business_memo.pdf",
    "INTERNAL MEMORANDUM - GLOBAL ENTERPRISES",
    [
        ("Memorandum Details", "TO: All Engineering Leads & Product Managers\nFROM: Chief Technology Officer\nDATE: March 14, 2026\nSUBJECT: Transition to Hybrid Work Schedule and Office Relocation"),
        ("Announcement", "Please be advised that effective April 1st, 2026, our engineering teams will transition to a 3-day in-office hybrid schedule. All core team syncs will be conducted on Tuesdays and Thursdays.\n\nAdditionally, our corporate office will relocate to the Technology Center on 5th Avenue. Please review floor plans and submit badge renewal requests before March 25th."),
        ("Action Items", "1. Department heads must submit hybrid roster schedules by Friday.\n2. Facilities team will coordinate physical equipment transfers on March 28-29.\n3. IT Support desk will be available on-site for workstation setup.")
    ]
)

# 7. other_contract_agreement.pdf
create_pdf(
    "other_contract_agreement.pdf",
    "MUTUAL NON-DISCLOSURE AGREEMENT (NDA)",
    [
        ("Preamble", "This Mutual Non-Disclosure Agreement (\"Agreement\") is entered into as of January 10, 2026 (\"Effective Date\"), by and between Alpha BioTech Inc. and Beta Health Solutions Ltd."),
        ("Confidential Information", "1. Definition: \"Confidential Information\" refers to any proprietary information, technical data, trade secrets, know-how, research data, or financial disclosures shared between parties.\n2. Standard of Care: The Receiving Party shall exercise reasonable care to protect confidential disclosures from unauthorized dissemination."),
        ("Governing Law & Jurisdiction", "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of law principles.\nIN WITNESS WHEREOF, the parties hereto have executed this Agreement.")
    ]
)


# 8. Create Scanned Invoice Image: invoice_scanned_receipt.png
def create_scanned_image(filename: str, lines: list[str], add_noise: bool = True):
    img = Image.new("RGB", (700, 900), color=(248, 247, 243))
    draw = ImageDraw.Draw(img)
    
    y = 50
    for line in lines:
        draw.text((60, y), line, fill=(35, 35, 35))
        y += 26
        
    if add_noise:
        # Simulate paper scan artifact / slight blur
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
        # Add subtle paper scan lines
        draw = ImageDraw.Draw(img)
        for _ in range(12):
            sy = random.randint(10, 880)
            draw.line([(30, sy), (670, sy)], fill=(230, 228, 222), width=1)
            
    img.save(os.path.join("week-3/samples", filename))
    print(f"Generated Scanned Image: {filename}")

create_scanned_image(
    "invoice_scanned_receipt.png",
    [
        "===================================================",
        "           METRO HARDWARE & TOOL SUPPLIES         ",
        "         445 INDUSTRIAL WAY, DALLAS, TX           ",
        "===================================================",
        "",
        "TAX INVOICE",
        "Invoice Number: INV-99214",
        "Date: 18-Feb-2026",
        "Company Name: Metro Hardware Depot",
        "Customer: Blue Ridge Contractors",
        "",
        "---------------------------------------------------",
        "ITEM DESCRIPTION               QTY   PRICE   TOTAL",
        "---------------------------------------------------",
        "Heavy Duty Cordless Drill       2    $120.00 $240.00",
        "Masonry Drill Bit Set 12pc      4     $25.00 $100.00",
        "Safety Protection Goggles      10     $15.00 $150.00",
        "Hex Key Wrench Metric           5     $18.00  $90.00",
        "---------------------------------------------------",
        "Subtotal: $580.00",
        "Sales Tax (8.0%): $46.40",
        "Total Amount: $626.40",
        "---------------------------------------------------",
        "",
        "PAYMENT METHOD: CASH / VISA RECEIPT",
        "THANK YOU FOR SHOPPING WITH METRO HARDWARE!"
    ],
    add_noise=True
)

# 9. Create Scanned Resume Image: resume_scanned.jpg
create_scanned_image(
    "resume_scanned.jpg",
    [
        "SARAH CHEN",
        "Email: sarah.chen.ml@outlook.com",
        "Phone: (415) 890-3412",
        "Location: San Francisco, CA",
        "",
        "PROFESSIONAL PROFILE",
        "AI & Machine Learning Engineer specializing in Computer Vision,",
        "Natural Language Processing, and deep learning model deployment.",
        "",
        "EDUCATION",
        "Master of Science in Computer Science - Stanford University",
        "Bachelor of Science in Electrical Engineering - UC Berkeley",
        "",
        "EXPERIENCE",
        "Machine Learning Engineer | NeuralScale AI (2023 - Present)",
        "- Developed multi-modal document understanding models with PyTorch.",
        "- Improved OCR accuracy on scanned images with OpenCV binarization.",
        "",
        "TECHNICAL SKILLS",
        "Python, PyTorch, TensorFlow, Scikit-Learn, OpenCV, NLP,",
        "Docker, AWS, Git, Pandas, NumPy, Machine Learning, Deep Learning"
    ],
    add_noise=True
)

print("All sample files generated successfully!")
