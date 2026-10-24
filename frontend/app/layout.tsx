import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "生成AI 設計書レビュー支援システム",
  description: "システム設計書のレビューを生成AIで支援するPoC",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
