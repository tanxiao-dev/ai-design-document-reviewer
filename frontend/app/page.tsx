"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";

type Severity = "High" | "Medium" | "Low";
type FindingType = "Issue" | "Confirmation";

type ReviewIssue = {
  id: string;
  finding_type: FindingType;
  category: string;
  severity: Severity;
  location: string;
  original_text: string;
  problem: string;
  suggestion: string;
};

type ReviewResponse = {
  document_name: string;
  summary: string;
  issue_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  demo_mode: boolean;
  issues: ReviewIssue[];
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File): string | null {
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!SUPPORTED_EXTENSIONS.includes(extension)) {
    return "PDF、DOCX、TXT、Markdown形式のファイルを選択してください。";
  }
  if (file.size === 0) return "空のファイルはレビューできません。";
  if (file.size > MAX_FILE_SIZE) return "ファイルサイズは10MB以下にしてください。";
  return null;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);

  const selectFile = (nextFile: File | undefined) => {
    if (!nextFile) return;
    const validationError = validateFile(nextFile);
    setError(validationError);
    setResult(null);
    setFile(validationError ? null : nextFile);
    if (validationError && inputRef.current) inputRef.current.value = "";
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    selectFile(event.target.files?.[0]);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    selectFile(event.dataTransfer.files[0]);
  };

  const runReview = async () => {
    if (!file || isLoading) return;
    setIsLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/review`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail ?? "レビューの実行に失敗しました。");
      }
      setResult(payload as ReviewResponse);
    } catch (caughtError) {
      setError(
        caughtError instanceof TypeError
          ? "バックエンドに接続できませんでした。起動状態を確認してください。"
          : caughtError instanceof Error
          ? caughtError.message
          : "バックエンドに接続できませんでした。",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main>
      <header className="app-header">
        <div className="header-inner">
          <div>
            <p className="product-label">DESIGN REVIEW CONSOLE</p>
            <h1>生成AI 設計書レビュー支援システム</h1>
          </div>
          <span className="poc-badge">PoC</span>
        </div>
      </header>

      <div className="page-shell">
        <section className="upload-section" aria-labelledby="upload-title">
          <div className="section-heading">
            <div>
              <p className="step-label">STEP 01</p>
              <h2 id="upload-title">設計書をアップロード</h2>
            </div>
            <span className="format-note">PDF / DOCX / TXT / Markdown</span>
          </div>

          <div
            className={`drop-zone${isDragging ? " is-dragging" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              id="document-file"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={handleChange}
              disabled={isLoading}
            />
            <div className="upload-copy">
              <strong>ファイルをここにドロップ</strong>
              <span>または</span>
              <label htmlFor="document-file">ファイルを選択</label>
              <small>最大ファイルサイズ: 10MB</small>
            </div>
          </div>

          {file && (
            <div className="selected-file" aria-live="polite">
              <div>
                <span className="selected-label">選択中のファイル</span>
                <strong>{file.name}</strong>
              </div>
              <span>{formatFileSize(file.size)}</span>
            </div>
          )}

          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}

          <button
            className="review-button"
            type="button"
            onClick={runReview}
            disabled={!file || isLoading}
          >
            {isLoading ? "設計書をレビューしています…" : "レビューを実行"}
          </button>
        </section>

        {result && (
          <section className="result-section" aria-labelledby="result-title">
            <div className="section-heading result-heading">
              <div>
                <p className="step-label">REVIEW RESULT</p>
                <h2 id="result-title">レビュー結果</h2>
              </div>
              <span className="result-filename">{result.document_name}</span>
            </div>

            {result.demo_mode && (
              <div className="demo-notice" role="status">
                <strong>デモモード：</strong>
                <span>この結果は生成AIによる実際のレビュー結果ではありません。</span>
              </div>
            )}

            <dl className="metrics">
              <div className="metric total">
                <dt>総指摘数</dt>
                <dd>{result.issue_count}</dd>
              </div>
              <div className="metric high">
                <dt>High</dt>
                <dd>{result.high_count}</dd>
              </div>
              <div className="metric medium">
                <dt>Medium</dt>
                <dd>{result.medium_count}</dd>
              </div>
              <div className="metric low">
                <dt>Low</dt>
                <dd>{result.low_count}</dd>
              </div>
            </dl>

            <div className="summary-block">
              <h3>AIレビュー総評</h3>
              <p>{result.summary}</p>
            </div>

            <div className="issues-heading">
              <h3>指摘一覧</h3>
              <span>{result.issue_count}件</span>
            </div>

            {result.issues.length === 0 ? (
              <p className="empty-result">明確な指摘事項は見つかりませんでした。</p>
            ) : (
              <div className="issue-list">
                {result.issues.map((issue) => (
                  <article
                    className={`issue-card severity-${issue.severity.toLowerCase()}`}
                    key={issue.id}
                  >
                    <div className="issue-topline">
                      <div className="issue-identifiers">
                        <span className={`severity-badge ${issue.severity.toLowerCase()}`}>
                          重要度: {issue.severity}
                        </span>
                        <span className="finding-badge">
                          {issue.finding_type === "Issue" ? "指摘" : "要確認"}
                        </span>
                        <span className="issue-id">{issue.id}</span>
                      </div>
                      <div className="issue-category">
                        <span>指摘カテゴリ</span>
                        <strong>{issue.category}</strong>
                      </div>
                    </div>

                    <dl className="issue-details">
                      <div>
                        <dt>指摘箇所</dt>
                        <dd>{issue.location}</dd>
                      </div>
                      <div>
                        <dt>該当箇所</dt>
                        <dd className={issue.original_text ? "quotation" : "muted"}>
                          {issue.original_text || "引用できる原文なし"}
                        </dd>
                      </div>
                      <div>
                        <dt>問題点</dt>
                        <dd>{issue.problem}</dd>
                      </div>
                      <div className="suggestion-row">
                        <dt>修正案</dt>
                        <dd>{issue.suggestion}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
