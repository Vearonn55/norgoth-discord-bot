import "./globals.css";
import type { ReactNode } from "react";

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" data-coreui-theme="dark" className="dark-theme">
      <body>{children}</body>
    </html>
  );
}
