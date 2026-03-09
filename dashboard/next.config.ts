import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Disable client-side router cache so every navigation triggers
     fresh data fetches via useEffect. Without this, navigating back
     to a page within 30s can serve a stale cached render. */
  experimental: {
    staleTimes: {
      dynamic: 0,
      static: 0,
    },
  },
};

export default nextConfig;
