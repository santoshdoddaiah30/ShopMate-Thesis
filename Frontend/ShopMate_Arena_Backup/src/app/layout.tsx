import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShopMate — Personalized Shopping Assistant",
  description: "AI-powered personalized shopping over an Amazon 2023 catalog.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
