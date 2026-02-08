import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Regulatory Collaboration MVP",
  description: "Regulatory-first collaboration workspace"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
