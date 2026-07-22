import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const langgraphUrl = process.env.LANGGRAPH_API_URL || "http://localhost:2024";
    return [
      {
        source: "/api/:path*",
        destination: `${langgraphUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
