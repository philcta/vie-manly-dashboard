"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

interface AnimatedNumberProps {
    value: number;
    duration?: number;
    formatter?: (n: number) => string;
    className?: string;
}

/**
 * Animated count-up number.
 * Per design system: numbers count up over 0.8s with spring-like easing.
 * Per ui-ux-pro-max: prefers-reduced-motion respected.
 */
export default function AnimatedNumber({
    value,
    duration = 800,
    formatter = (n: number) => n.toFixed(0),
    className = "",
}: AnimatedNumberProps) {
    const [display, setDisplay] = useState(value);
    const prevValue = useRef(value);
    const frameRef = useRef<number>(0);
    const shouldReduceMotion = useReducedMotion();

    useEffect(() => {
        if (shouldReduceMotion) {
            setDisplay(value);
            return;
        }

        const start = prevValue.current;
        const end = value;
        const startTime = performance.now();

        const animate = (now: number) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic for a smooth deceleration
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = start + (end - start) * eased;

            setDisplay(current);

            if (progress < 1) {
                frameRef.current = requestAnimationFrame(animate);
            }
        };

        frameRef.current = requestAnimationFrame(animate);
        prevValue.current = value;

        return () => cancelAnimationFrame(frameRef.current);
    }, [value, duration, shouldReduceMotion]);

    return (
        <span className={`tabular-nums ${className}`}>
            {formatter(display)}
        </span>
    );
}
