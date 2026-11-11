import http.client
import io
import json
import socket
import sys
import threading
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import uvicorn

from app.database.connection import SessionLocal, engine
from app.main import app
from app.models import Document


def _office_file(extension: str) -> bytes:
    members = {
        ".docx": (
            "word/document.xml",
            b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        ),
        ".xlsx": (
            "xl/workbook.xml",
            b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        ),
        ".pptx": (
            "ppt/presentation.xml",
            b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        ),
    }
    member, content_type = members[extension]
    package_content = (
        b'<?xml version="1.0"?><Types><Override PartName="/'
        + member.encode()
        + b'" ContentType="'
        + content_type
        + b'"/></Types>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", package_content)
        package.writestr("_rels/.rels", b"<Relationships />")
        package.writestr(member, b"<document />")
    return buffer.getvalue()


class DocumentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=cls.port,
            log_level="error",
            lifespan="on",
        )
        cls.server = uvicorn.Server(config)
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()

        deadline = time.monotonic() + 30
        while not cls.server.started and cls.thread.is_alive():
            if time.monotonic() >= deadline:
                cls.server.should_exit = True
                cls.thread.join(timeout=5)
                raise RuntimeError("FastAPI test server failed to start.")
            time.sleep(0.05)

        if not cls.server.started:
            raise RuntimeError("FastAPI test server exited before startup.")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        engine.dispose()

    def setUp(self):
        self.document_ids = []

    def tearDown(self):
        for document_id in self.document_ids:
            self._request("DELETE", f"/api/documents/{document_id}")

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def _request(self, method, path, body=None, headers=None):
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers or {},
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read())
            finally:
                error.close()

    def _upload(self, filename, content):
        boundary = f"offscript-test-{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self._request(
            "POST",
            "/api/documents/upload",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    def _wait_for_processing(self, document_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response_status, response = self._request(
                "GET",
                f"/api/documents/{document_id}/processing",
            )
            self.assertEqual(response_status, 200)
            if response["status"] in {"completed", "failed"}:
                return response
            time.sleep(0.05)
        self.fail(f"Document processing did not finish: {document_id}")

    def _upload_chunked(self, filename, content_size):
        boundary = f"offscript-test-{uuid.uuid4().hex}"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.putrequest("POST", "/api/documents/upload")
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()

        def send_chunk(chunk):
            connection.send(f"{len(chunk):X}\r\n".encode("ascii"))
            connection.send(chunk)
            connection.send(b"\r\n")

        send_chunk(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                "Content-Type: text/plain\r\n\r\n"
            ).encode()
        )
        chunk = b"l" * (256 * 1024)
        remaining = content_size
        while remaining:
            next_chunk = chunk[: min(len(chunk), remaining)]
            send_chunk(next_chunk)
            remaining -= len(next_chunk)
        send_chunk(f"\r\n--{boundary}--\r\n".encode())
        connection.send(b"0\r\n\r\n")

        response = connection.getresponse()
        payload = json.loads(response.read())
        status_code = response.status
        connection.close()
        return status_code, payload

    def test_supported_formats_upload_and_metadata_are_retrievable(self):
        files = [
            ("report.pdf", b"%PDF-1.7\nminimal test document"),
            ("letter.docx", _office_file(".docx")),
            ("records.xlsx", _office_file(".xlsx")),
            ("slides.pptx", _office_file(".pptx")),
            ("notes.txt", "UTF-8 text document".encode()),
        ]
        uploaded = []

        for filename, content in files:
            with self.subTest(filename=filename):
                response_status, response = self._upload(filename, content)
                self.assertEqual(response_status, 201)
                self.assertEqual(response["filename"], filename)
                self.assertEqual(response["file_size"], len(content))
                self.assertEqual(response["file_type"], Path(filename).suffix[1:])
                self.assertEqual(response["status"], "uploaded")
                self.assertNotIn("file_path", response)
                self.assertNotIn("stored_filename", response)
                self.document_ids.append(response["id"])
                uploaded.append(response)

        first_id = uploaded[0]["id"]
        details_status, details = self._request(
            "GET", f"/api/documents/{first_id}"
        )
        self.assertEqual(details_status, 200)
        self.assertEqual(details["id"], first_id)

        list_status, listing = self._request("GET", "/api/documents/")
        self.assertEqual(list_status, 200)
        listed_ids = {document["id"] for document in listing["documents"]}
        self.assertTrue({document["id"] for document in uploaded} <= listed_ids)

    def test_rejects_unsupported_empty_and_mismatched_files(self):
        unsupported_status, _ = self._upload("payload.exe", b"not allowed")
        empty_status, _ = self._upload("empty.txt", b"")
        mismatched_status, _ = self._upload("not-a-pdf.pdf", b"plain text")
        invalid_text_status, _ = self._upload("binary.txt", b"\xff\x00")

        self.assertEqual(unsupported_status, 400)
        self.assertEqual(empty_status, 400)
        self.assertEqual(mismatched_status, 400)
        self.assertEqual(invalid_text_status, 400)

    def test_multiple_uploads_and_path_safe_original_filename(self):
        first_status, first = self._upload("../team-notes.txt", b"first")
        second_status, second = self._upload("team-notes.txt", b"second")
        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 201)
        self.assertEqual(first["filename"], "team-notes.txt")
        self.assertNotEqual(first["id"], second["id"])
        self.document_ids.extend((first["id"], second["id"]))

        with SessionLocal() as db:
            first_record = db.get(Document, uuid.UUID(first["id"]))
            second_record = db.get(Document, uuid.UUID(second["id"]))
            self.assertIsNotNone(first_record)
            self.assertIsNotNone(second_record)
            self.assertNotEqual(first_record.stored_filename, second_record.stored_filename)
            self.assertTrue(Path(first_record.file_path).is_file())
            self.assertTrue(Path(second_record.file_path).is_file())

    def test_large_chunked_upload_has_no_application_size_limit(self):
        content_size = 12 * 1024 * 1024
        response_status, response = self._upload_chunked(
            "large-document.txt", content_size
        )
        self.assertEqual(response_status, 201)
        self.assertEqual(response["file_size"], content_size)
        self.document_ids.append(response["id"])

    def test_processing_api_runs_and_reprocesses_a_document(self):
        upload_status, document = self._upload(
            "processing.txt",
            b"First paragraph.\nSecond paragraph.",
        )
        self.assertEqual(upload_status, 201)
        self.document_ids.append(document["id"])
        document_id = document["id"]

        status_code, initial_status = self._request(
            "GET",
            f"/api/documents/{document_id}/processing",
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(initial_status["status"], "not_started")

        start_status, start = self._request(
            "POST",
            f"/api/documents/{document_id}/process",
        )
        self.assertEqual(start_status, 202)
        self.assertEqual(start["status"], "queued")
        completed = self._wait_for_processing(document_id)
        self.assertEqual(completed["status"], "completed")

        content_status, content = self._request(
            "GET",
            f"/api/documents/{document_id}/content",
        )
        self.assertEqual(content_status, 200)
        self.assertEqual(content["status"], "completed")
        self.assertEqual(
            [item["content"]["text"] for item in content["items"]],
            ["First paragraph.", "Second paragraph."],
        )
        self.assertTrue(
            all(
                item["source"]["filename"] == "processing.txt"
                for item in content["items"]
            )
        )

        retry_status, _ = self._request(
            "POST",
            f"/api/documents/{document_id}/process",
        )
        self.assertEqual(retry_status, 202)
        self.assertEqual(self._wait_for_processing(document_id)["status"], "completed")
        _, reprocessed_content = self._request(
            "GET",
            f"/api/documents/{document_id}/content",
        )
        self.assertEqual(len(reprocessed_content["items"]), 2)

    def test_processing_failure_is_reported_for_a_corrupted_pdf(self):
        upload_status, document = self._upload(
            "corrupted.pdf",
            b"%PDF-1.7\nnot a valid PDF body",
        )
        self.assertEqual(upload_status, 201)
        self.document_ids.append(document["id"])

        start_status, _ = self._request(
            "POST",
            f"/api/documents/{document['id']}/process",
        )
        self.assertEqual(start_status, 202)
        failed = self._wait_for_processing(document["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["error_message"])

    def test_delete_removes_metadata_and_file_and_missing_id_is_404(self):
        upload_status, document = self._upload("delete-me.txt", b"delete this")
        self.assertEqual(upload_status, 201)
        self.document_ids.append(document["id"])
        document_id = uuid.UUID(document["id"])

        with SessionLocal() as db:
            stored_document = db.get(Document, document_id)
            self.assertIsNotNone(stored_document)
            stored_path = Path(stored_document.file_path)
            self.assertTrue(stored_path.is_file())

        delete_status, delete_response = self._request(
            "DELETE", f"/api/documents/{document_id}"
        )
        self.assertEqual(delete_status, 200)
        self.assertEqual(delete_response["message"], "Document deleted successfully.")

        with SessionLocal() as db:
            self.assertIsNone(db.get(Document, document_id))
        self.assertFalse(stored_path.exists())

        missing_id = uuid.uuid4()
        detail_status, _ = self._request("GET", f"/api/documents/{missing_id}")
        missing_delete_status, _ = self._request(
            "DELETE", f"/api/documents/{missing_id}"
        )
        self.assertEqual(detail_status, 404)
        self.assertEqual(missing_delete_status, 404)


if __name__ == "__main__":
    unittest.main()
