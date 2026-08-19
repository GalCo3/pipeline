import "server-only";

import { KafkaJS } from "@confluentinc/kafka-javascript";

import { config } from "@/lib/config";

/**
 * The librdkafka client, shared by the producer and the admin client.
 *
 * @confluentinc/kafka-javascript wraps the same librdkafka the Python services
 * use, so broker TLS and config semantics are identical on both sides of the
 * pipeline — that is why it is here rather than a pure-JS client.
 *
 * The SSL keys are librdkafka's own (`ssl.ca.location`, …), passed through
 * alongside the KafkaJS-shaped block. They mirror
 * `hermes.connections.config_models.kafka.BaseKafkaSecurityConfig.get_settings`
 * exactly, so a chart that configures a Python service configures this app the
 * same way.
 */

function securityProperties(): Record<string, string> {
  const properties: Record<string, string> = {
    "security.protocol": config.kafka.securityProtocol.toLowerCase(),
  };
  if (config.kafka.ssl) {
    properties["ssl.ca.location"] = config.kafka.ssl.caPath;
    properties["ssl.certificate.location"] = config.kafka.ssl.certPath;
    properties["ssl.key.location"] = config.kafka.ssl.keyPath;
  }
  return properties;
}

export function kafka(): KafkaJS.Kafka {
  return new KafkaJS.Kafka({
    kafkaJS: { brokers: config.kafka.brokers.split(",").map((b) => b.trim()) },
    ...securityProperties(),
  });
}
