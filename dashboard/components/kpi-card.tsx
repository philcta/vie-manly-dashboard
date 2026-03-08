"use client";

import { motion, useReducedMotion } from "framer-motion";
import AnimatedNumber from "@/components/animated-number";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KpiCardProps {
    label: string;
    value: number;
    formatter: (n: number) => string;
    /** Percentage change vs comparison. null = hide badge, undefined = hide badge */
    change?: number | null;
    /** If true, show "N/A" badge instead of a percentage (comparison data unavailable) */
    noCompData?: boolean;
    changeLabel?: string;
    subtitle?: string;
    delay?: number;
    /**
     * Invert the color semantics: positive change = RED, negative = GREEN.
     * Use for cost ratios where an increase is bad and a decrease is good.
     */
    invertColor?: boolean;
}

/**
 * KPI metric card — the core dashboard building block.
 *
 * Per design system: white bg, 12px radius, soft shadow, hover lift.
 * Per frontend-design: cursor-pointer on interactive elements.
 * Per ui-ux-pro-max: 44x44px min touch target, visible focus states.
 */
export default function KpiCard({
    label,
    value,
    formatter,
    change,
    noCompData = false,
    changeLabel,
    subtitle,
    delay = 0,
    invertColor = false,
}: KpiCardProps) {
    const shouldReduceMotion = useReducedMotion();

    // Determine badge color
    const hasChange = change !== null && change !== undefined;
    const isUp = hasChange && change > 0;
    const isDown = hasChange && change < 0;

    // Normal: up=green, down=red. Inverted (costs): up=red, down=green
    const badgeGreen = invertColor ? isDown : isUp;
    const badgeRed = invertColor ? isUp : isDown;

    return (
        <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: delay * 0.05 }}
            className="bg-card rounded-xl border border-border p-5 hover-lift cursor-pointer"
            style={{
                boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
            }}
        >
            {/* Label */}
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
                {label}
            </p>

            {/* Value */}
            <div className="flex items-end gap-3">
                <AnimatedNumber
                    value={value}
                    formatter={formatter}
                    className="text-[28px] font-bold text-foreground leading-none"
                />

                {/* N/A Badge — comparison data not available */}
                {noCompData && (
                    <span className="inline-flex items-center gap-1 text-[13px] font-semibold px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                        <Minus className="w-3.5 h-3.5" />
                        N/A
                    </span>
                )}

                {/* Change Badge — only show when we have real comparison data */}
                {!noCompData && hasChange && (
                    <span
                        className={`inline-flex items-center gap-1 text-[13px] font-semibold px-2.5 py-1 rounded-full ${badgeGreen
                            ? "bg-positive text-white"
                            : badgeRed
                                ? "bg-coral text-white"
                                : "bg-muted text-muted-foreground"
                            }`}
                    >
                        {isUp ? (
                            <TrendingUp className="w-3.5 h-3.5" />
                        ) : isDown ? (
                            <TrendingDown className="w-3.5 h-3.5" />
                        ) : (
                            <Minus className="w-3.5 h-3.5" />
                        )}
                        {Math.abs(change).toFixed(1)}%
                    </span>
                )}
            </div>

            {/* Subtitle / Change Label */}
            {(subtitle || changeLabel) && (
                <p className="text-xs text-muted-foreground mt-1.5">
                    {subtitle || changeLabel}
                </p>
            )}
        </motion.div>
    );
}
