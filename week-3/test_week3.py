"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
Automated Verification & Test Suite
Task 02: Improve Document Understanding

Covers:
1. Text Cleaning & Normalization Verification
2. OCR Handling & Preprocessing Verification
3. ML Model Classification & Confidence Scoring
4. Information Extraction & Missing Field Handling
5. Comprehensive Test Report across Sample Documents
"""

import os
import sys
import json
import unittest

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from text_cleaner import clean_extracted_text, normalize_for_classification, validate_text_quality, get_cleaning_summary
from ocr_engine import is_tesseract_available, extract_document_text, preprocess_image_for_ocr
from model_trainer import classify_document, RuleBasedClassifier, load_dataset, get_classifier
from extractor import extract_document_information, extract_invoice_fields, extract_resume_fields
from PIL import Image


class TestWeek3DocumentIntelligence(unittest.TestCase):

    def setUp(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.samples_dir = os.path.join(self.base_dir, "samples")

    # ==========================================================================
    # 1. TEXT CLEANING & NORMALIZATION TESTS
    # ==========================================================================
    def test_text_cleaning_whitespace_and_unicode(self):
        messy_input = "  Invoice   Number:\xa0\xa0INV-9921  \r\n\r\n\r\n\r\nTotal:   $500.00  \u200b• Item 1"
        cleaned = clean_extracted_text(messy_input)
        
        self.assertNotIn("\xa0", cleaned, "Non-breaking space should be removed/replaced")
        self.assertNotIn("\r", cleaned, "Carriage return should be standardized")
        self.assertNotIn("\u200b", cleaned, "Zero-width space should be removed")
        self.assertNotIn("\n\n\n", cleaned, "Triple or more newlines should be collapsed")
        self.assertIn("Invoice Number: INV-9921", cleaned)
        self.assertIn("- Item 1", cleaned)

    def test_text_quality_validator(self):
        empty_res = validate_text_quality("")
        self.assertFalse(empty_res["is_valid"])
        self.assertEqual(empty_res["status"], "EMPTY")

        short_res = validate_text_quality("Hi there!")
        self.assertFalse(short_res["is_valid"])
        self.assertEqual(short_res["status"], "VERY_SHORT")

        valid_res = validate_text_quality("This is a valid extracted document text with more than minimum required characters.")
        self.assertTrue(valid_res["is_valid"])
        self.assertEqual(valid_res["status"], "VALID")

    # ==========================================================================
    # 2. OCR HANDLING & PREPROCESSING TESTS
    # ==========================================================================
    def test_tesseract_engine_presence(self):
        has_tesseract = is_tesseract_available()
        self.assertTrue(has_tesseract, "Tesseract-OCR should be available on the system")

    def test_image_preprocessing_pipeline(self):
        test_img = Image.new("RGB", (400, 400), color=(240, 240, 240))
        proc_img, steps = preprocess_image_for_ocr(test_img, to_grayscale=True, scale_factor=1.5, binarize=True)
        
        self.assertIn("scaling", steps)
        self.assertIn("grayscale", steps)
        self.assertIn("otsu_binarization", steps)
        self.assertEqual(proc_img.size, (600, 600))
        self.assertEqual(proc_img.mode, "L")

    def test_scanned_image_extraction(self):
        scanned_path = os.path.join(self.samples_dir, "invoice_scanned_receipt.png")
        if os.path.exists(scanned_path):
            with open(scanned_path, "rb") as f:
                raw_bytes = f.read()
            text, meta = extract_document_text(raw_bytes, "invoice_scanned_receipt.png")
            self.assertTrue(meta["ocr_used"], "OCR must be utilized for scanned image")
            self.assertGreater(len(text), 100, "Should extract meaningful text from scanned receipt")
            self.assertIn("HARDWARE", text.upper())

    # ==========================================================================
    # 3. ML CLASSIFICATION & CONFIDENCE TESTS
    # ==========================================================================
    def test_classifier_predictions_and_confidence(self):
        inv_text = "TAX INVOICE Invoice Number INV-1002 Date: 12-Jan-2026 Billed To Customer Subtotal $500 Total Amount Due $540.00"
        res_inv = classify_document(inv_text)
        self.assertEqual(res_inv["document_type"], "Invoice")
        self.assertGreaterEqual(res_inv["confidence"], 0.70)
        self.assertTrue(res_inv["confidence_percentage"].endswith("%"))

        cv_text = "Curriculum Vitae Software Engineer Skills Python React Django Docker Experience Education Bachelor of Science"
        res_cv = classify_document(cv_text)
        self.assertEqual(res_cv["document_type"], "Resume")
        self.assertGreaterEqual(res_cv["confidence"], 0.70)

        oth_text = "Mutual Non-Disclosure Agreement entered into between Party A and Party B concerning confidential trade secrets."
        res_oth = classify_document(oth_text)
        self.assertEqual(res_oth["document_type"], "Other")

    # ==========================================================================
    # 4. EXTRACTION & MISSING FIELD RESILIENCE TESTS
    # ==========================================================================
    def test_invoice_complete_extraction(self):
        pdf_path = os.path.join(self.samples_dir, "invoice_standard.pdf")
        with open(pdf_path, "rb") as f:
            raw_text, _ = extract_document_text(f.read(), "invoice_standard.pdf")
        
        info = extract_document_information(clean_extracted_text(raw_text), "Invoice")
        flat = info["flat_values"]
        
        self.assertEqual(flat["invoice_number"], "INV-2026-0814")
        self.assertEqual(flat["date"], "12-Jan-2026")
        self.assertIn("APEX DIGITAL SOLUTIONS", flat["company_name"].upper())
        self.assertIn("8,389.38", flat["total_amount"])
        self.assertEqual(len(info["missing_fields"]), 0)
        self.assertEqual(info["completeness_score"], "100.0%")

    def test_invoice_missing_fields_handling(self):
        pdf_path = os.path.join(self.samples_dir, "invoice_missing_fields.pdf")
        with open(pdf_path, "rb") as f:
            raw_text, _ = extract_document_text(f.read(), "invoice_missing_fields.pdf")
            
        info = extract_document_information(clean_extracted_text(raw_text), "Invoice")
        flat = info["flat_values"]
        
        # Missing fields should explicitly equal 'Not Found' and NOT raise an error
        self.assertEqual(flat["invoice_number"], "Not Found")
        self.assertEqual(flat["total_amount"], "Not Found")
        self.assertIn("invoice_number", info["missing_fields"])
        self.assertIn("total_amount", info["missing_fields"])
        self.assertEqual(info["completeness_score"], "50.0%")

    def test_resume_missing_contact_resilience(self):
        pdf_path = os.path.join(self.samples_dir, "resume_missing_contact.pdf")
        with open(pdf_path, "rb") as f:
            raw_text, _ = extract_document_text(f.read(), "resume_missing_contact.pdf")
            
        info = extract_document_information(clean_extracted_text(raw_text), "Resume")
        flat = info["flat_values"]
        
        self.assertEqual(flat["name"], "Tariq Mehmood")
        self.assertEqual(flat["email"], "Not Found")
        self.assertEqual(flat["phone"], "Not Found")
        self.assertIn("email", info["missing_fields"])
        self.assertIn("phone", info["missing_fields"])


def run_full_sample_audit():
    """Runs end-to-end pipeline audit across all files in samples/ and prints a structured summary."""
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    files = sorted(os.listdir(samples_dir))
    
    print("\n" + "=" * 90)
    print("WEEK 3 END-TO-END SAMPLE DOCUMENT AUDIT")
    print("=" * 90)
    print(f"{'Filename':<32} | {'Doc Type':<8} | {'Conf':<6} | {'Missing Fields':<22} | {'Completeness':<12}")
    print("-" * 90)

    for fname in files:
        fpath = os.path.join(samples_dir, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "rb") as f:
            raw_b = f.read()

        raw_text, meta = extract_document_text(raw_b, fname)
        clean_text = clean_extracted_text(raw_text)
        cls_result = classify_document(clean_text)
        doc_type = cls_result["document_type"]
        conf_pct = cls_result["confidence_percentage"]

        ext_result = extract_document_information(clean_text, doc_type)
        missing_str = ", ".join(ext_result["missing_fields"]) if ext_result["missing_fields"] else "None"
        completeness = ext_result.get("completeness_score", "N/A")

        print(f"{fname:<32} | {doc_type:<8} | {conf_pct:<6} | {missing_str:<22} | {completeness:<12}")

    print("=" * 90 + "\n")


if __name__ == "__main__":
    print("Executing Unit & Integration Tests for Week 3...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWeek3DocumentIntelligence)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nAll Week 3 unit tests passed successfully!")
        run_full_sample_audit()
    else:
        sys.exit(1)
