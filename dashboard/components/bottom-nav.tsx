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

const navItems = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/members", label: "Members", icon: Users },
    { href: "/inventory", label: "Inventory", icon: Package },
    { href: "/staff", label: "Staff", icon: UserCog },
    { href: "/campaigns", label: "SMS", icon: MessageSquare },
    { href: "/settings", label: "Settings", icon: Settings },
];

export default function BottomNav() {
    const pathname = usePathname();

    return (
        <nav className="fixed bottom-0 left-0 right-0 z-[90] md:hidden bg-[#1E1E2E] border-t border-white/10 safe-area-bottom">
            <div className="flex items-stretch justify-around h-[60px]">
                {navItems.map((item) => {
                    const isActive =
                        pathname === item.href ||
                        (item.href !== "/" && pathname.startsWith(item.href));

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex flex-col items-center justify-center gap-0.5 flex-1 min-w-0 py-1.5 transition-colors
                                ${isActive
                                    ? "text-[#A8B094]"
                                    : "text-[#7A7A8A] active:text-white"
                                }`}
                        >
                            <item.icon
                                className={`w-5 h-5 ${isActive ? "text-[#6B7355]" : ""}`}
                            />
                            <span className={`text-[9px] font-medium leading-none ${isActive ? "text-[#A8B094]" : ""}`}>
                                {item.label}
                            </span>
                            {isActive && (
                                <div className="absolute top-0 w-8 h-[2px] bg-[#6B7355] rounded-b-full" />
                            )}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}
