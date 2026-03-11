"use client";

import { useState, useEffect } from "react";
import AppSidebar from "@/components/app-sidebar";

export default function DashboardShell({ children }: { children: React.ReactNode }) {
    const [collapsed, setCollapsed] = useState(false);

    // Sync with sidebar: media query + manual toggle events
    useEffect(() => {
        const mql = window.matchMedia("(max-width: 1023px)");

        const sync = () => {
            if (mql.matches) {
                setCollapsed(true);
            } else {
                setCollapsed(localStorage.getItem("sidebar-collapsed") === "true");
            }
        };

        sync();
        mql.addEventListener("change", sync);
        window.addEventListener("sidebar-toggle", sync);
        return () => {
            mql.removeEventListener("change", sync);
            window.removeEventListener("sidebar-toggle", sync);
        };
    }, []);

    return (
        <div className="flex min-h-screen">
            <AppSidebar />
            <main
                className="flex-1 p-3 sm:p-4 lg:p-5 xl:p-6 bg-background min-h-screen transition-all duration-300 ease-in-out overflow-x-hidden"
                style={{ marginLeft: collapsed ? 56 : 220 }}
            >
                {children}
            </main>
        </div>
    );
}
