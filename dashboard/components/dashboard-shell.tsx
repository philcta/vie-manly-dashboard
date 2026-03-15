"use client";

import { useState, useEffect } from "react";
import AppSidebar from "@/components/app-sidebar";
import AiCoachPanel from "@/components/ai-coach-panel";
import BottomNav from "@/components/bottom-nav";

export default function DashboardShell({ children }: { children: React.ReactNode }) {
    const [collapsed, setCollapsed] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

    // Sync with sidebar: media query + manual toggle events
    useEffect(() => {
        const lgMql = window.matchMedia("(max-width: 1023px)");
        const mdMql = window.matchMedia("(max-width: 767px)");

        const sync = () => {
            setIsMobile(mdMql.matches);
            if (lgMql.matches) {
                setCollapsed(true);
            } else {
                setCollapsed(localStorage.getItem("sidebar-collapsed") === "true");
            }
        };

        sync();
        lgMql.addEventListener("change", sync);
        mdMql.addEventListener("change", sync);
        window.addEventListener("sidebar-toggle", sync);
        return () => {
            lgMql.removeEventListener("change", sync);
            mdMql.removeEventListener("change", sync);
            window.removeEventListener("sidebar-toggle", sync);
        };
    }, []);

    return (
        <div className="flex min-h-screen">
            <AppSidebar />
            <main
                className="flex-1 p-3 sm:p-4 lg:p-5 xl:p-6 bg-background min-h-screen transition-all duration-300 ease-in-out overflow-x-hidden pb-20 md:pb-6"
                style={{ marginLeft: isMobile ? 0 : (collapsed ? 56 : 220) }}
            >
                {children}
            </main>
            <AiCoachPanel />
            <BottomNav />
        </div>
    );
}
