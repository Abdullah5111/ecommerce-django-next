import "./globals.css";
import type { Metadata } from "next";
import Header from "@/components/Header";
import { CartProvider } from "@/lib/cart";
import { AuthProvider } from "@/lib/useAuth";
import { ToastProvider } from "@/lib/useToast";
import { WishlistProvider } from "@/lib/useWishlist";
import ToastContainer from "@/components/ToastContainer";

export const metadata: Metadata = {
  title: "Shop",
  description: "A simple e-commerce demo built with Django + Next.js.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <CartProvider>
            <WishlistProvider>
              <ToastProvider>
                <Header />
                <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
                <ToastContainer />
              </ToastProvider>
            </WishlistProvider>
          </CartProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
