"use client";

import { motion, useReducedMotion } from "framer-motion";
import AnimatedNumber from "@/components/animated-number";
import { TrendingUp, TrendingDown, Minus, Info } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

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
    /** Optional info tooltip shown next to the label */
    tooltip?: string;
    /** When true, gives the card a premium accent treatment (gradient border + warm tint) */
    accent?: boolean;
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
    tooltip,
    accent = false,
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
            className={`rounded-xl p-4 hover-lift cursor-pointer relative overflow-hidden ${accent
                ? "bg-gradient-to-br from-[#FAFAF5] to-[#F5F5ED] border border-[#C5C9A8]/40"
                : "bg-card border border-border"
                }`}
            style={{
                boxShadow: accent
                    ? "0 2px 12px rgba(107, 115, 85, 0.10), 0 1px 4px rgba(0,0,0,0.04)"
                    : "0 2px 8px rgba(0, 0, 0, 0.04)",
            }}
        >
            {/* Accent left bar */}
            {accent && (
                <div
                    className="absolute left-0 top-0 bottom-0 w-[3px]"
                    style={{
                        background: "linear-gradient(180deg, #6B7355 0%, #A8B094 100%)",
                    }}
                />
            )}
            {/* Label */}
            <div className="flex items-center gap-1.5 mb-2">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {label}
                </p>
                {tooltip && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Info className="w-3.5 h-3.5 text-muted-foreground/60 hover:text-muted-foreground cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent side="top" sideOffset={6} className="max-w-[240px] text-xs leading-relaxed">
                            {tooltip}
                        </TooltipContent>
                    </Tooltip>
                )}
            </div>

            {/* Value */}
            <div className="flex items-center gap-2 flex-wrap">
                <AnimatedNumber
                    value={value}
                    formatter={formatter}
                    className="text-2xl font-bold text-foreground leading-none"
                />

                {/* N/A Badge — comparison data not available */}
                {noCompData && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Minus className="w-3.5 h-3.5" />
                        N/A
                    </span>
                )}

                {/* Change Badge — only show when we have real comparison data */}
                {!noCompData && hasChange && (
                    <span
                        className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${badgeGreen
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
