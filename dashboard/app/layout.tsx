import type { Metadata } from "next";
import "./globals.css";
import AppSidebar from "@/components/app-sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

/**
 * Per ui-ux-pro-max skill:
 * - Use expressive display font + restrained body font (not Inter/Roboto defaults)
 * - frontend-design: avoid system/AI-default fonts
 *
 * We use Playfair Display (serif, for the brand logo feel) + DM Sans (body).
 * DM Sans is a geometric sans that pairs well with serif headings — warmer than Inter.
 */

export const metadata: Metadata = {
  title: "VIE. MANLY — Dashboard",
  description:
    "Business analytics dashboard for Vie Market & Bar, Manly. Sales, staff, members, inventory, and SMS campaigns.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700&family=Playfair+Display:wght@400;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className="antialiased"
        style={{
          fontFamily: "'DM Sans', ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <TooltipProvider>
          <div className="flex min-h-screen">
            <AppSidebar />
            <main className="ml-[220px] flex-1 p-8 bg-background min-h-screen">
              {children}
            </main>
          </div>
        </TooltipProvider>
      </body>
    </html>
  );
}
