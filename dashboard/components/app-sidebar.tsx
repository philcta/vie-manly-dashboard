"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    Users,
    Package,
    UserCog,
    MessageSquare,
    Settings,
} from "lucide-react";

/**
 * Dashboard sidebar navigation.
 * Per shadcn skill: use SidebarProvider pattern for state management.
 * Per ui-ux-pro-max: cursor-pointer on all clickable, smooth transitions 150-300ms.
 * Per frontend-design: deep charcoal sidebar with olive active indicator.
 */

const navItems = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/members", label: "Members", icon: Users },
    { href: "/inventory", label: "Inventory", icon: Package },
    { href: "/staff", label: "Staff", icon: UserCog },
    { href: "/campaigns", label: "SMS Campaigns", icon: MessageSquare },
    { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppSidebar() {
    const pathname = usePathname();

    return (
        <aside className="fixed top-0 left-0 h-screen w-[220px] bg-[#1E1E2E] flex flex-col z-50">
            {/* Logo */}
            <div className="px-6 py-6 flex flex-col items-center border-b border-white/6">
                <h1 className="text-[#A8B094] font-serif text-2xl font-bold tracking-wide">
                    VIE<span className="text-[#6B7355]">.</span>
                </h1>
                <span className="text-[#7A7A8A] text-[10px] uppercase tracking-[0.3em] mt-0.5">
                    M A N L Y
                </span>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
                {navItems.map((item) => {
                    const isActive =
                        pathname === item.href ||
                        (item.href !== "/" && pathname.startsWith(item.href));

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`
                group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                transition-all duration-200 cursor-pointer
                ${isActive
                                    ? "text-[#A8B094] bg-[rgba(107,115,85,0.08)] border-l-[3px] border-[#6B7355] ml-0 pl-[9px]"
                                    : "text-[#B8B8C8] hover:text-white hover:bg-white/[0.03] border-l-[3px] border-transparent"
                                }
              `}
                        >
                            <item.icon
                                className={`w-[18px] h-[18px] flex-shrink-0 ${isActive ? "text-[#6B7355]" : "text-[#7A7A8A] group-hover:text-[#B8B8C8]"
                                    }`}
                            />
                            <span>{item.label}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom info */}
            <div className="px-4 py-4 border-t border-white/6">
                <p className="text-[10px] text-[#5A5A6A] text-center">
                    Vie Market &amp; Bar
                </p>
            </div>
        </aside>
    );
}
