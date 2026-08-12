import NextAuth, { customFetch } from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

/**
 * OIDC Authorization Code against Keycloak, with this app as the confidential
 * client.
 *
 * This is the part the old SPA had to hand-roll: a browser-only client could not
 * hold `client_secret`, so it posted its code to a backend route that exchanged
 * it. Here the exchange happens in the same process that serves the page, and
 * the browser ends up holding nothing but an encrypted session cookie — no
 * access token in JS reach, no refresh loop in the client.
 *
 * Split horizon (`AUTH_KEYCLOAK_INTERNAL_ISSUER`): the browser must be sent to
 * the URL Keycloak was configured with (its tokens carry that host in `iss`),
 * while this pod usually cannot reach that URL and has to go through the
 * in-cluster Service. Pointing discovery at the internal base is not enough —
 * Keycloak builds every endpoint in its discovery document from `KC_HOSTNAME`,
 * so the pod gets handed the public token endpoint anyway and fails with
 * ECONNREFUSED against its own localhost. So the rewrite happens one level
 * lower, on the fetch itself: `issuer` stays public (that is what `iss`
 * validation and the browser redirect need) and every *server-side* call to it
 * is rewritten to the internal host. The authorization redirect is built for
 * the browser rather than fetched, so it is untouched.
 *
 * If the IdP's TLS is signed by an internal CA, point `NODE_EXTRA_CA_CERTS` at
 * the bundle: node ships its own trust store, and without it every login fails
 * on certificate verification.
 */

const issuer = process.env.AUTH_KEYCLOAK_ISSUER ?? "";
const internal = process.env.AUTH_KEYCLOAK_INTERNAL_ISSUER;

/** Public issuer URL -> the host this pod can actually reach. */
function internalize(url: string): string {
  if (!internal || !url.startsWith(issuer)) return url;
  return internal + url.slice(issuer.length);
}

const serverFetch: typeof fetch = (input, init) => {
  const url = input instanceof Request ? input.url : String(input);
  const rewritten = internalize(url);
  if (rewritten === url) return fetch(input, init);
  // A Request carries the body/method; rebuild it around the new URL rather
  // than dropping to a bare fetch and losing the token POST's form body.
  return input instanceof Request
    ? fetch(new Request(rewritten, input), init)
    : fetch(rewritten, init);
};

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    Keycloak({
      issuer,
      clientId: process.env.AUTH_KEYCLOAK_ID,
      clientSecret: process.env.AUTH_KEYCLOAK_SECRET,
      [customFetch]: serverFetch,
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    jwt({ token, profile }) {
      // Keycloak's `preferred_username` is what an operator recognises as
      // themselves, and it is what the Python backend audited as the actor. Keep
      // the same identity so an audit ledger written by either app reads alike.
      if (profile?.preferred_username) token.name = String(profile.preferred_username);
      return token;
    },
    session({ session, token }) {
      if (token.name) session.user.name = token.name;
      return session;
    },
  },
});
