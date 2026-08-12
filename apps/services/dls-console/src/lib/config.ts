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

export type MongoTls = {
  /** trust bundle for the server's certificate */
  caPath: string | null;
  /** ONE PEM holding the client certificate and its key, concatenated */
  certKeyPath: string | null;
};

/**
 * TLS material for Mongo, as file paths — the same shape as `kafkaSsl`, so an
 * operator mounts certificates and names paths once and both clients read them
 * the same way. The alternative is spelling `tls=true&tlsCAFile=...` into
 * `MONGO_URI` by hand, which puts connection semantics in a string nobody
 * validates.
 *
 * Unlike Kafka's triple these are deliberately *independent*, because both
 * halves are useful alone: a CA with no client certificate is server-TLS with
 * ordinary password auth (the common case behind an internal CA), and a client
 * certificate with no CA is x509 against a server whose issuer node already
 * trusts. Requiring them together would reject both.
 *
 * `certKeyPath` is a single file, not a pair — the Node driver's
 * `tlsCertificateKeyFile` wants the certificate and the private key
 * concatenated into one PEM. Kafka's client is the one that takes them apart.
 */
function mongoTls(): MongoTls | null {
  const caPath = process.env.MONGO_TLS_CA_PATH;
  const certKeyPath = process.env.MONGO_TLS_CERT_KEY_PATH;
  if (!caPath && !certKeyPath) return null;
  return { caPath: caPath ?? null, certKeyPath: certKeyPath ?? null };
}

function mongoUri(): string {
  const explicit = process.env.MONGO_URI;
  if (explicit) return explicit;
  const host = str("MONGO_HOST", "localhost");
  const port = num("MONGO_PORT", 27017);
  // x509 keeps the identity in the certificate's subject, so credentials are
  // absent by design there and demanding them would make the mechanism
  // unreachable. Everywhere else they are still required — an unauthenticated
  // URI would otherwise be one unset variable away.
  if (!process.env.MONGO_USERNAME && !process.env.MONGO_PASSWORD && mongoTls()?.certKeyPath) {
    return `mongodb://${host}:${port}/`;
  }
  const user = encodeURIComponent(str("MONGO_USERNAME"));
  const password = encodeURIComponent(str("MONGO_PASSWORD"));
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
    const uri = mongoUri();
    const tls = mongoTls();
    return {
      uri,
      database: str("MONGO_DATABASE", "hermes"),
      // The collection the services write to (`settings.dls_collection`). One
      // shared collection for the whole pipeline — `source_topic` says who
      // wrote the document, so per-service collections would only fragment the
      // reads.
      collection: str("MONGO_DLS_COLLECTION", "dls"),
      tls,
      // Mongo reads the username off the certificate's subject, so x509 is
      // precisely the case where a client certificate is present and the URI
      // carries no credentials. Inferred rather than configured: an explicit
      // MONGO_AUTH_MECHANISM would be a second switch that has to agree with
      // the first, and disagreeing switches are how "it authenticated as
      // nobody" happens. A hand-written MONGO_URI stating its own mechanism is
      // left alone — it has credentials, or it says `authMechanism` itself.
      x509: Boolean(tls?.certKeyPath) && !uri.includes("@"),
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
