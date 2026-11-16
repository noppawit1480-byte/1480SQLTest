import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: { default: "SQLab — เรียนและฝึก SQL", template: "%s · SQLab" },
  description: "แพลตฟอร์มเรียนรู้และฝึกฝน SQL ตั้งแต่พื้นฐานถึงระดับมืออาชีพ บน PostgreSQL จริง",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Applies the saved/system theme before paint to avoid a flash of the wrong theme.
const themeScript = `(()=>{try{const t=localStorage.getItem('theme');const d=t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
