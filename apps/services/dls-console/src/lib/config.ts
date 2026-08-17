import "server-only";

/**
 * Server-side config, read once from the environment.
 *
 * Flat names on purpose: the Python services nest (`SECTION__FIELD`) because
 * each of their clients is a separate pydantic config, while this app holds one
 * Mongo client and one Kafka client for the whole process. The exception is
 * Mongo's credentials and x509 material, which keep the services' own
 * `MONGO_CONFIG__AUTH__*` spelling — one cluster's Secret is mounted into both,
 * and a second spelling for the same values is a second thing to get wrong.
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
  /** client certificate; holds the key too when `keyPath` is unset */
  certPath: string | null;
  /** the key as its own file, for material that ships cert and key apart */
  keyPath: string | null;
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
 * `keyPath` is optional because both shapes exist in the wild: pymongo (and so
 * the Python services) takes ONE PEM with the certificate and key concatenated,
 * which is `certPath` alone; material mounted as a separate `.crt` and `.key`
 * names both. `src/lib/mongo.ts` is where that fork turns into driver options.
 */
function mongoTls(): MongoTls | null {
  const caPath = process.env.MONGO_CONFIG__AUTH__LOCAL__CA_PATH;
  const certPath = process.env.MONGO_CONFIG__AUTH__LOCAL__CERT_PATH;
  const keyPath = process.env.MONGO_CONFIG__AUTH__LOCAL__KEY_PATH;
  if (!caPath && !certPath && !keyPath) return null;
  // A key with no certificate proves nothing and would hand the driver half a
  // credential, so it is a config error rather than a silent server-TLS-only.
  if (keyPath && !certPath) {
    throw new Error("MONGO_CONFIG__AUTH__LOCAL__KEY_PATH needs MONGO_CONFIG__AUTH__LOCAL__CERT_PATH");
  }
  return { caPath: caPath ?? null, certPath: certPath ?? null, keyPath: keyPath ?? null };
}

function mongoUri(): string {
  const explicit = process.env.MONGO_URI;
  if (explicit) return explicit;
  const host = str("MONGO_CONFIG__LOCAL_HOST", "localhost");
  const port = num("MONGO_CONFIG__PORT", 27017);
  // x509 keeps the identity in the certificate's subject, so credentials are
  // absent by design there and demanding them would make the mechanism
  // unreachable. Everywhere else they are still required — an unauthenticated
  // URI would otherwise be one unset variable away.
  if (
    !process.env.MONGO_CONFIG__AUTH__USERNAME &&
    !process.env.MONGO_CONFIG__AUTH__PASSWORD &&
    mongoTls()?.certPath
  ) {
    return `mongodb://${host}:${port}/`;
  }
  const user = encodeURIComponent(str("MONGO_CONFIG__AUTH__USERNAME"));
  const password = encodeURIComponent(str("MONGO_CONFIG__AUTH__PASSWORD"));
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
  const caPath = process.env.CONSUMER_CONFIG__SSL__CA_PATH;
  const certPath = process.env.CONSUMER_CONFIG__SSL__CERT_PATH;
  const keyPath = process.env.CONSUMER_CONFIG__SSL__KEY_PATH;
  if (!caPath && !certPath && !keyPath) return null;
  if (!caPath || !certPath || !keyPath) {
    throw new Error(
      "CONSUMER_CONFIG__SSL__CA_PATH, __CERT_PATH and __KEY_PATH go together",
    );
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
      database: str("MONGO_CONFIG__DATABASE", "hermes"),
      // The collection the services write to (`settings.dls_collection`). One
      // shared collection for the whole pipeline — `source_topic` says who
      // wrote the document, so per-service collections would only fragment the
      // reads.
      collection: str("DLS_COLLECTION", "dls"),
      tls,
      // Mongo reads the username off the certificate's subject, so x509 is
      // precisely the case where a client certificate is present and the URI
      // carries no credentials. Inferred rather than configured: an explicit
      // MONGO_AUTH_MECHANISM would be a second switch that has to agree with
      // the first, and disagreeing switches are how "it authenticated as
      // nobody" happens. A hand-written MONGO_URI stating its own mechanism is
      // left alone — it has credentials, or it says `authMechanism` itself.
      x509: Boolean(tls?.certPath) && !uri.includes("@"),
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
    return `${str("MONGO_CONFIG__DATABASE", "hermes")}.${str("DLS_COLLECTION", "dls")}`;
  },
  /**
   * SSL by default, matching the Python services' KafkaConfig — a deployed
   * broker speaks TLS, so the unset case has to be the safe one. Plaintext is
   * then a thing an operator writes down (every chart does, for the local
   * broker) rather than what a forgotten variable silently produces.
   */
  get kafka(): KafkaConfig {
    const securityProtocol = str("CONSUMER_CONFIG__SECURITY_PROTOCOL", "SSL");
    const ssl = kafkaSsl();
    // Same refusal the Python side makes: SSL with no material would connect
    // as plaintext or fail deep inside librdkafka, and neither says why.
    if (securityProtocol === "SSL" && !ssl) {
      throw new Error(
        "CONSUMER_CONFIG__SECURITY_PROTOCOL=SSL needs CONSUMER_CONFIG__SSL__CA_PATH, __CERT_PATH and __KEY_PATH",
      );
    }
    return {
      brokers: str("CONSUMER_CONFIG__BOOTSTRAP_SERVERS", "localhost:9092"),
      securityProtocol,
      ssl,
      produceTimeoutMs: num("KAFKA_PRODUCE_TIMEOUT", 15) * 1000,
    };
  },
  get lag() {
    return { groupIdTemplate: str("LAG_GROUP_ID_TEMPLATE", "{service}-service") };
  },
  /**
   * OIDC, confidential client. Names mirror dlq-triage's `AUTH__OIDC_*` block
   * (flattened, as everything here is) so one realm's client spells the same
   * way in both apps.
   *
   * `issuerUrl` is the bare realm URL — no `/.well-known/openid-configuration`
   * suffix. Nothing here fetches a discovery document (see `src/lib/oidc.ts`),
   * so a suffix would only corrupt every endpoint path derived from it.
   */
  get auth() {
    const issuerUrl = str("AUTH_OIDC_ISSUER_URL");
    const internalUrl = process.env.AUTH_OIDC_INTERNAL_URL;
    return {
      issuerUrl,
      /** Base this *process* uses to reach the IdP. Split-horizon aware. */
      idpBase: (internalUrl || issuerUrl).replace(/\/$/, ""),
      clientId: str("AUTH_OIDC_CLIENT_ID"),
      // Absent means the deploy is missing its Secret; the token exchange
      // answers 503 rather than quietly behaving like a public client.
      clientSecret: process.env.AUTH_OIDC_CLIENT_SECRET || null,
      // Optional: Keycloak's stock access token carries `aud: account`, so this
      // stays unchecked until the realm has an audience mapper for the console.
      audience: process.env.AUTH_OIDC_AUDIENCE || null,
      jwksTtl: num("AUTH_OIDC_JWKS_TTL", 300),
      // Seals the session cookie. Never leaves this process — unlike the client
      // secret, which is shared with the IdP. The two are not interchangeable.
      sessionSecret: str("AUTH_SECRET"),
      devBypass: bool("DEV_BYPASS", false),
      devActor: str("DEV_ACTOR", "dev@example.com"),
    };
  },
  /** The two values the browser needs to build its authorize redirect. Public
   *  by construction: no secret is reachable from this getter. */
  get publicAuth() {
    return {
      issuerUrl: str("AUTH_OIDC_ISSUER_URL").replace(/\/$/, ""),
      clientId: str("AUTH_OIDC_CLIENT_ID"),
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
