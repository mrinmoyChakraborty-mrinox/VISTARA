import type { Metadata, Viewport } from "next";
import { Fraunces, Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppPreloader } from "@/components/loader/AppPreloader";
import { Providers } from "@/components/providers/providers";
import { ThemeProvider } from "@/components/theme-provider";

const THEME_SCRIPT = `(function(){try{var s=localStorage.getItem('v-theme');var t=(s==='light'||s==='dark')?s:(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
  weight: ["300", "400", "600"],
});

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "700"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Vistara — Ask your camera what happened",
  description:
    "Vistara watches quietly, remembers what moves, and answers your questions with the exact frame as proof.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fraunces.variable} ${bricolage.variable} ${jetbrains.variable}`}
    >
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <ThemeProvider
          attribute="data-theme"
          defaultTheme="system"
          enableSystem
          storageKey="v-theme"
          disableTransitionOnChange={false}
        >
          <Providers>
            <AppPreloader />
            {children}
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}