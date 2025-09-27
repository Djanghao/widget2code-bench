/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  transpilePackages: [
    "antd",
    "@ant-design/icons",
    "@ant-design/cssinjs",
    "rc-util",
    "rc-motion",
    "rc-resize-observer",
    "rc-pagination",
    "rc-select",
    "rc-tree",
    "rc-table",
    "rc-tabs",
    "rc-drawer",
    "rc-dialog",
    "rc-collapse",
    "rc-picker",
    "rc-image",
    "rc-upload",
    "rc-segmented",
  ],
};

module.exports = nextConfig;
