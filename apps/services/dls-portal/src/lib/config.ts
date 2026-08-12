import "server-only";

/**
 * Server-side config, read once from the environment.
 *
 * Flat names on purpose: the Python services nest (`SECTION__FIELD`) because
 * each of their clients is a separate pydantic config, while this app holds one
 * Mongo client and one Kafka client for the whole process.
 *
 * `server-only` is the guard that matters — importing this from a client
 * component is a build error, so a broker address or a Mongo password can never
 * be bundled into the browser.
 */

function str(name: string, fallback?: string): string {
  const value = process.env[name];
  if (value === undefined || value === "") {
    if (fallback !== undefined) return fallback;
    throw new Error(`missing required env var ${name}`);
  }
  return value;
}

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  const parsed = Number(raw);
  if (Number.isNaN(parsed)) throw new Error(`env var ${name} is not a number: ${raw}`);
  return parsed;
}

function bool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  return ["1", "true", "yes", "on"].includes(raw.toLowerCase());
}

function mongoUri(): string {
  const explicit = process.env.MONGO_URI;
  if (explicit) return explicit;
  const user = encodeURIComponent(str("MONGO_USERNAME"));
  const password = encodeURIComponent(str("MONGO_PASSWORD"));
  const host = str("MONGO_HOST", "localhost");
  const port = num("MONGO_PORT", 27017);
  // authSource=admin matches how the pipeline's Mongo is provisioned: the user
  // lives in `admin`, the data in `hermes`.
  return `mongodb://${user}:${password}@${host}:${port}/?authSource=admin`;
}

export type KafkaConfig = {
  brokers: string;
  securityProtocol: string;
  ssl: { caPath: string; certPath: string; keyPath: string } | null;
  produceTimeoutMs: number;
};

function kafkaSsl(): KafkaConfig["ssl"] {
  const caPath = process.env.KAFKA_SSL_CA_PATH;
  const certPath = process.env.KAFKA_SSL_CERT_PATH;
  const keyPath = process.env.KAFKA_SSL_KEY_PATH;
  if (!caPath && !certPath && !keyPath) return null;
  if (!caPath || !certPath || !keyPath) {
    throw new Error("KAFKA_SSL_CA_PATH, KAFKA_SSL_CERT_PATH and KAFKA_SSL_KEY_PATH go together");
  }
  return { caPath, certPath, keyPath };
}

/**
 * Lazily, per section — and that laziness is load-bearing.
 *
 * `next build` imports every route module to collect its metadata, in an
 * environment that has none of these variables. Reading them at module scope
 * would make a missing Mongo password a *build* failure rather than a startup
 * one, so nothing is touched until a request actually needs it.
 */
export const config = {
  get mongo() {
    return {
      uri: mongoUri(),
      database: str("MONGO_DATABASE", "hermes"),
      // The collection the services write to (`settings.dls_collection`). One
      // shared collection for the whole pipeline — `source_topic` says who
      // wrote the document, so per-service collections would only fragment the
      // reads.
      collection: str("MONGO_DLS_COLLECTION", "dls"),
    };
  },
  /**
   * `database.collection`, for the shell to show which store it is looking at.
   *
   * Split out of `mongo` rather than derived from it at the call site: the
   * layout renders this, and touching `mongo` there would drag `mongoUri()` —
   * and its throw on a missing password — into a render that has no business
   * needing credentials.
   */
  get storeLabel(): string {
    return `${str("MONGO_DATABASE", "hermes")}.${str("MONGO_DLS_COLLECTION", "dls")}`;
  },
  get kafka(): KafkaConfig {
    return {
      brokers: str("KAFKA_BROKERS", "localhost:9092"),
      securityProtocol: str("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
      ssl: kafkaSsl(),
      produceTimeoutMs: num("KAFKA_PRODUCE_TIMEOUT", 15) * 1000,
    };
  },
  get lag() {
    return { groupIdTemplate: str("LAG_GROUP_ID_TEMPLATE", "{service}-service") };
  },
  get auth() {
    return {
      devBypass: bool("DEV_BYPASS", false),
      devActor: str("DEV_ACTOR", "dev@example.com"),
    };
  },
};

/** `cargo-lexical.files` -> `cargo-lexical`. */
export function serviceOf(sourceTopic: string): string {
  return sourceTopic.split(".", 1)[0];
}

/** `cargo-lexical.files` -> `cargo-lexical-service`. */
export function groupIdFor(sourceTopic: string): string {
  return config.lag.groupIdTemplate.replace("{service}", serviceOf(sourceTopic));
}
