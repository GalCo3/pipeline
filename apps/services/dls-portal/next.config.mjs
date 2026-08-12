/** @type {import('next').NextConfig} */
const nextConfig = {
  // The image is a self-contained node server (see Dockerfile), not a static
  // export: every read hits Mongo and every replay hits Kafka, so there is no
  // build-time-renderable page here.
  output: "standalone",

  // @confluentinc/kafka-javascript is a native (librdkafka) addon. Next's server
  // bundler cannot trace a .node binary, so it stays an external require — the
  // package must exist in node_modules at runtime, which the Dockerfile ensures.
  serverExternalPackages: ["@confluentinc/kafka-javascript", "mongodb"],

  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
