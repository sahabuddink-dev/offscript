import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import pymupdf
from docx import Document as WordDocument
from openpyxl import Workbook
from openpyxl.drawing.image import Image as SpreadsheetImage
from openpyxl.worksheet.table import Table
from pptx import Presentation
from pptx.util import Inches

from app.services.document_processing.base import ProcessingError
from app.services.document_processing.pipeline import _extract


class DocumentProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _png_path(self) -> Path:
        image_path = self.directory / "pixel.png"
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 20, 20), False)
        pixmap.save(image_path)
        return image_path

    def test_extracts_text_pdf_with_page_and_layout_metadata(self):
        file_path = self.directory / "text.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "A readable PDF paragraph.")
        document.save(file_path)
        document.close()

        items = _extract(file_path, "pdf")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].content["text"], "A readable PDF paragraph.")
        self.assertEqual(items[0].page_number, 1)
        self.assertEqual(items[0].source["parser"], "pymupdf")
        self.assertEqual(items[0].source["layout"], "text_block")

    def test_extracts_pdf_table_without_flattening_rows(self):
        file_path = self.directory / "table.pdf"
        document = pymupdf.open()
        page = document.new_page()
        x_positions = [72, 200, 340]
        y_positions = [72, 100, 128]
        for x_position in x_positions:
            page.draw_line((x_position, y_positions[0]), (x_position, y_positions[-1]))
        for y_position in y_positions:
            page.draw_line((x_positions[0], y_position), (x_positions[-1], y_position))
        for x_position, y_position, text in (
            (78, 91, "Name"),
            (206, 91, "Amount"),
            (78, 119, "North"),
            (206, 119, "50"),
        ):
            page.insert_text((x_position, y_position), text)
        document.save(file_path)
        document.close()

        table = next(
            item for item in _extract(file_path, "pdf") if item.content_type == "table"
        )

        self.assertEqual(table.page_number, 1)
        self.assertEqual(table.content["headers"], ["Name", "Amount"])
        self.assertEqual(table.content["rows"], [["North", "50"]])

    def test_ocr_runs_only_for_scanned_pdf_pages_and_preserves_position(self):
        image_path = self._png_path()
        file_path = self.directory / "scanned.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_image(page.rect, filename=str(image_path))
        document.save(file_path)
        document.close()

        recognized = {
            "text": "Scanned text",
            "confidence": 0.97,
            "bounding_box": [[1, 2], [3, 2], [3, 4], [1, 4]],
        }
        with patch(
            "app.services.document_processing.pdf.recognize_page",
            return_value=[recognized],
        ) as ocr:
            items = _extract(file_path, "pdf")

        ocr.assert_called_once()
        ocr_item = next(item for item in items if item.content_type == "ocr_text")
        self.assertEqual(ocr_item.page_number, 1)
        self.assertEqual(ocr_item.content["text"], "Scanned text")
        self.assertEqual(ocr_item.source["bounding_box"], recognized["bounding_box"])
        self.assertEqual(ocr_item.source["coordinate_space"], "rendered_image_pixels")
        self.assertTrue(any(item.content_type == "image_reference" for item in items))

    def test_extracts_docx_headings_paragraphs_and_structured_tables_in_order(self):
        file_path = self.directory / "report.docx"
        document = WordDocument()
        document.add_heading("Quarterly report", level=1)
        document.add_paragraph("Summary paragraph")
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Region"
        table.cell(0, 1).text = "Revenue"
        table.cell(1, 0).text = "West"
        table.cell(1, 1).text = "125"
        document.add_picture(str(self._png_path()))
        document.save(file_path)

        items = _extract(file_path, "docx")

        self.assertEqual(
            [item.content_type for item in items],
            ["heading", "paragraph", "table", "image_reference"],
        )
        self.assertEqual(items[0].content["text"], "Quarterly report")
        self.assertEqual(items[2].content["headers"], ["Region", "Revenue"])
        self.assertEqual(items[2].content["rows"], [["West", "125"]])
        image_item = next(item for item in items if item.content_type == "image_reference")
        self.assertEqual(image_item.source["parser"], "python-docx")

    def test_extracts_xlsx_sheets_rows_tables_and_cell_references(self):
        file_path = self.directory / "records.xlsx"
        workbook = Workbook()
        first = workbook.active
        first.title = "Sales"
        first.append(["Region", "Revenue"])
        first.append(["West", 125])
        first.add_table(
            Table(
                displayName="SalesTable",
                ref="A1:B2",
            )
        )
        second = workbook.create_sheet("Forecast")
        second["C4"] = "Next quarter"
        second.add_image(SpreadsheetImage(str(self._png_path())), "E2")
        third = workbook.create_sheet("Forecast Table")
        third.append(["Quarter", "Target"])
        third.append(["Q1", 200])
        workbook.save(file_path)
        workbook.close()

        items = _extract(file_path, "xlsx")

        sheet_names = {item.sheet_name for item in items}
        self.assertEqual(sheet_names, {"Sales", "Forecast", "Forecast Table"})
        table_item = next(item for item in items if item.content_type == "table")
        self.assertEqual(table_item.sheet_name, "Sales")
        self.assertEqual(table_item.cell_reference, "A1:B2")
        self.assertEqual(table_item.content["headers"], ["Region", "Revenue"])
        next_quarter = next(
            item
            for item in items
            if item.content_type == "row"
            and item.sheet_name == "Forecast"
        )
        self.assertEqual(next_quarter.content["cells"][0]["reference"], "C4")
        inferred_table = next(
            item
            for item in items
            if item.content_type == "table"
            and item.source.get("table_detection") == "inferred_used_range"
        )
        self.assertEqual(inferred_table.sheet_name, "Forecast Table")
        self.assertEqual(inferred_table.content["headers"], ["Quarter", "Target"])
        image_item = next(
            item
            for item in items
            if item.content_type == "image_reference"
            and item.sheet_name == "Forecast"
        )
        self.assertEqual(image_item.cell_reference, "E2")

    def test_extracts_pptx_slides_tables_text_and_image_references(self):
        image_path = self._png_path()
        file_path = self.directory / "presentation.pptx"
        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = "Quarterly results"
        textbox = slide.shapes.add_textbox(
            Inches(1),
            Inches(1),
            Inches(4),
            Inches(1),
        )
        textbox.text = "Revenue grew."
        table_shape = slide.shapes.add_table(
            2,
            2,
            Inches(1),
            Inches(2),
            Inches(4),
            Inches(1),
        )
        table_shape.table.cell(0, 0).text = "Region"
        table_shape.table.cell(0, 1).text = "Revenue"
        table_shape.table.cell(1, 0).text = "West"
        table_shape.table.cell(1, 1).text = "125"
        slide.shapes.add_picture(str(image_path), Inches(1), Inches(4))
        presentation.save(file_path)

        items = _extract(file_path, "pptx")

        self.assertTrue(any(item.content_type == "slide_title" for item in items))
        self.assertTrue(any(item.content_type == "paragraph" for item in items))
        table_item = next(item for item in items if item.content_type == "table")
        self.assertEqual(table_item.slide_number, 1)
        self.assertEqual(table_item.content["rows"], [["West", "125"]])
        image_item = next(item for item in items if item.content_type == "image_reference")
        self.assertEqual(image_item.slide_number, 1)
        self.assertEqual(image_item.source["parser"], "python-pptx")

    def test_empty_documents_produce_no_text_items_and_blank_pdf_skips_ocr(self):
        blank_pdf = self.directory / "blank.pdf"
        document = pymupdf.open()
        document.new_page()
        document.save(blank_pdf)
        document.close()
        blank_text = self.directory / "blank.txt"
        blank_text.write_text("", encoding="utf-8")
        blank_docx = self.directory / "blank.docx"
        WordDocument().save(blank_docx)

        with patch(
            "app.services.document_processing.pdf.recognize_page"
        ) as ocr:
            self.assertEqual(_extract(blank_pdf, "pdf"), [])
        ocr.assert_not_called()
        self.assertEqual(_extract(blank_text, "txt"), [])
        self.assertEqual(_extract(blank_docx, "docx"), [])

    def test_corrupted_files_and_unsupported_types_return_processing_errors(self):
        for extension in ("pdf", "docx", "xlsx", "pptx"):
            file_path = self.directory / f"corrupted.{extension}"
            file_path.write_bytes(b"not a valid document")
            with self.subTest(extension=extension):
                with self.assertRaises(ProcessingError):
                    _extract(file_path, extension)

        with self.assertRaisesRegex(ProcessingError, "Unsupported document format"):
            _extract(self.directory / "file.bin", "bin")


if __name__ == "__main__":
    unittest.main()
