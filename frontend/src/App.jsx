import { useCallback, useEffect, useRef, useState } from "react";

import apiClient from "./services/apiClient.js";
import "./styles/index.css";

const ACCEPTED_TYPES = ".pdf,.docx,.xlsx,.pptx,.txt";

function getErrorMessage(error) {
  return (
    error.response?.data?.detail ||
    error.message ||
    "Something went wrong. Please try again."
  );
}

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function App() {
  const fileInput = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.get("/api/documents/");
      setDocuments(data.documents);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const uploadFiles = async (fileList) => {
    const files = Array.from(fileList);
    if (!files.length) return;

    setUploading(true);
    setError("");
    setNotice("");
    const outcomes = await Promise.allSettled(
      files.map((file) => {
        const formData = new FormData();
        formData.append("file", file);
        return apiClient.post("/api/documents/upload", formData);
      }),
    );
    const uploaded = outcomes.filter(
      (outcome) => outcome.status === "fulfilled",
    ).length;
    const failures = outcomes.filter(
      (outcome) => outcome.status === "rejected",
    );

    await loadDocuments();
    setUploading(false);
    if (failures.length) {
      setError(
        failures
          .map((failure) => getErrorMessage(failure.reason))
          .join(" "),
      );
    }
    if (uploaded) {
      setNotice(
        `${uploaded} document${uploaded === 1 ? "" : "s"} uploaded successfully.`,
      );
    }
  };

  const showDetails = async (documentId) => {
    setDetailsLoading(true);
    setError("");
    try {
      const { data } = await apiClient.get(`/api/documents/${documentId}`);
      setSelectedDocument(data);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setDetailsLoading(false);
    }
  };

  const deleteDocument = async (document) => {
    if (!window.confirm(`Delete "${document.filename}"? This cannot be undone.`)) {
      return;
    }

    setDeletingId(document.id);
    setError("");
    setNotice("");
    try {
      await apiClient.delete(`/api/documents/${document.id}`);
      if (selectedDocument?.id === document.id) setSelectedDocument(null);
      setNotice(`"${document.filename}" was deleted.`);
      await loadDocuments();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setDeletingId(null);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    uploadFiles(event.dataTransfer.files);
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="OffScript home">
          <span className="brand-mark" aria-hidden="true">O</span>
          <span>OffScript</span>
        </a>
        <span className="workspace-label">Document workspace</span>
      </header>

      <div className="page-content">
        <section className="page-heading">
          <div>
            <p className="eyebrow">DOCUMENT MANAGEMENT</p>
            <h1>Your documents</h1>
            <p className="subtitle">
              Upload and organize the files your team works with.
            </p>
          </div>
          <span className="document-count">
            {documents.length} {documents.length === 1 ? "document" : "documents"}
          </span>
        </section>

        <section
          className={`upload-panel${dragging ? " is-dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) {
              setDragging(false);
            }
          }}
          onDrop={handleDrop}
          aria-label="Upload documents"
        >
          <input
            ref={fileInput}
            className="visually-hidden"
            type="file"
            accept={ACCEPTED_TYPES}
            multiple
            onChange={(event) => {
              uploadFiles(event.target.files);
              event.target.value = "";
            }}
          />
          <div className="upload-icon" aria-hidden="true">↑</div>
          <div className="upload-copy">
            <h2>{uploading ? "Uploading documents…" : "Add documents"}</h2>
            <p>Drag and drop files here, or browse from your computer.</p>
            <span>PDF, DOCX, XLSX, PPTX, and TXT</span>
          </div>
          <button
            className="button button-primary"
            type="button"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            Browse files
          </button>
        </section>

        {error && (
          <div className="feedback feedback-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}
        {notice && (
          <div className="feedback feedback-success" role="status">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice("")} aria-label="Dismiss message">
              ×
            </button>
          </div>
        )}

        <section className="documents-section" aria-labelledby="documents-heading">
          <div className="section-heading">
            <div>
              <h2 id="documents-heading">All documents</h2>
              <p>Manage your uploaded files and view their details.</p>
            </div>
            <button
              className="button button-secondary"
              type="button"
              onClick={loadDocuments}
              disabled={loading}
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="state-card" role="status">Loading documents…</div>
          ) : documents.length === 0 ? (
            <div className="state-card empty-state">
              <div className="empty-icon" aria-hidden="true">▤</div>
              <h3>No documents yet</h3>
              <p>Upload a document to see it listed here.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Type</th>
                    <th scope="col">Size</th>
                    <th scope="col">Uploaded</th>
                    <th scope="col">Status</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((document) => (
                    <tr key={document.id}>
                      <td>
                        <button
                          className="document-name"
                          type="button"
                          onClick={() => showDetails(document.id)}
                        >
                          <span className="file-icon" aria-hidden="true">
                            {document.file_type.toUpperCase().slice(0, 3)}
                          </span>
                          <span>{document.filename}</span>
                        </button>
                      </td>
                      <td className="muted-cell">{document.file_type.toUpperCase()}</td>
                      <td className="muted-cell">{formatFileSize(document.file_size)}</td>
                      <td className="muted-cell">{formatDate(document.created_at)}</td>
                      <td>
                        <span className="status-pill">{document.status}</span>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="text-button"
                            type="button"
                            onClick={() => showDetails(document.id)}
                          >
                            Details
                          </button>
                          <button
                            className="text-button text-danger"
                            type="button"
                            disabled={deletingId === document.id}
                            onClick={() => deleteDocument(document)}
                          >
                            {deletingId === document.id ? "Deleting…" : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {(selectedDocument || detailsLoading) && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedDocument(null);
          }}
        >
          <section
            className="details-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="details-heading"
          >
            <div className="details-heading">
              <div>
                <p className="eyebrow">DOCUMENT DETAILS</p>
                <h2 id="details-heading">
                  {detailsLoading ? "Loading…" : selectedDocument?.filename}
                </h2>
              </div>
              <button
                className="close-button"
                type="button"
                onClick={() => setSelectedDocument(null)}
                aria-label="Close document details"
              >
                ×
              </button>
            </div>
            {selectedDocument && (
              <dl className="details-list">
                <div><dt>File type</dt><dd>{selectedDocument.file_type.toUpperCase()}</dd></div>
                <div><dt>File size</dt><dd>{formatFileSize(selectedDocument.file_size)}</dd></div>
                <div><dt>Status</dt><dd><span className="status-pill">{selectedDocument.status}</span></dd></div>
                <div><dt>Uploaded</dt><dd>{formatDate(selectedDocument.created_at)}</dd></div>
                <div><dt>Last updated</dt><dd>{formatDate(selectedDocument.updated_at)}</dd></div>
                <div><dt>Document ID</dt><dd className="id-value">{selectedDocument.id}</dd></div>
              </dl>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

export default App;
