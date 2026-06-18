import path from 'node:path';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root to THIS directory. Without this, Next.js
  // walks up and finds a stray ~/package-lock.json, infers the wrong
  // root, and fails to detect web/middleware.ts — which breaks
  // clerkMiddleware() detection and cascades into "Missing secretKey".
  outputFileTracingRoot: path.resolve(import.meta.dirname),
};

export default nextConfig;
