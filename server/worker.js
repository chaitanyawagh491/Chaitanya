import bcrypt from "bcryptjs";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS, DELETE",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Init-Secret",
};

async function signJWT(payload, secret) {
  const header = { alg: "HS256", typ: "JWT" };
  const encodedHeader = btoa(JSON.stringify(header))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  const encodedPayload = btoa(JSON.stringify(payload))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  const tokenInput = `${encodedHeader}.${encodedPayload}`;
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const key = await crypto.subtle.importKey(
    "raw", keyData, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC", key, encoder.encode(tokenInput)
  );
  const signatureArray = Array.from(new Uint8Array(signatureBuffer));
  const signature = btoa(String.fromCharCode.apply(null, signatureArray))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  return `${tokenInput}.${signature}`;
}

async function verifyJWT(token, secret) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const [encodedHeader, encodedPayload, signature] = parts;
    const tokenInput = `${encodedHeader}.${encodedPayload}`;
    const encoder = new TextEncoder();
    const keyData = encoder.encode(secret);
    const key = await crypto.subtle.importKey(
      "raw", keyData, { name: "HMAC", hash: "SHA-256" }, false, ["verify"]
    );
    const sigBinary = atob(signature.replace(/-/g, "+").replace(/_/g, "/"));
    const sigBuffer = new Uint8Array(sigBinary.length);
    for (let i = 0; i < sigBinary.length; i++) {
      sigBuffer[i] = sigBinary.charCodeAt(i);
    }
    const valid = await crypto.subtle.verify(
      "HMAC", key, sigBuffer, encoder.encode(tokenInput)
    );
    if (!valid) return null;
    const payload = JSON.parse(
      atob(encodedPayload.replace(/-/g, "+").replace(/_/g, "/"))
    );
    const currentEpoch = Math.floor(Date.now() / 1000);
    if (payload.exp && currentEpoch > payload.exp) {
      return null;
    }
    return payload;
  } catch (err) {
    return null;
  }
}

async function authenticateToken(request, env) {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }
  const token = authHeader.split(" ")[1];
  const jwtSecret = env.JWT_SECRET || "DEFAULT_JWT_SIGNING_KEY_visual_analyzer";
  return await verifyJWT(token, jwtSecret);
}

async function isPrimaryOwner(username, env) {
  const primaryOwner = env.PRIMARY_OWNER || "admin";
  if (username === primaryOwner) {
    return true;
  }
  try {
    const oldestUserRow = await env.DB.prepare(
      "SELECT username FROM users ORDER BY created_at ASC LIMIT 1"
    ).first();
    return oldestUserRow && oldestUserRow.username === username;
  } catch (e) {
    return false;
  }
}

async function logAudit(env, actor, action, target, ip, details) {
  try {
    await env.DB.prepare(
      "INSERT INTO audit_log (actor, action, target, ip_address, details) VALUES (?, ?, ?, ?, ?)"
    )
    .bind(actor, action, target, ip, details)
    .run();
  } catch (e) {
    console.error("Failed to write audit log:", e);
  }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const clientIP = request.headers.get("CF-Connecting-IP") || "127.0.0.1";
    const jwtSecret = env.JWT_SECRET || "DEFAULT_JWT_SIGNING_KEY_visual_analyzer";
    try {
      if (path === "/api/ping" && method === "GET") {
        let dbStatus = "connected";
        try {
          await env.DB.prepare("SELECT 1").first();
        } catch (e) {
          dbStatus = "error";
        }
        return new Response(
          JSON.stringify({ 
            status: "online", 
            database: dbStatus, 
            timestamp: new Date().toISOString() 
          }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/announcements" && method === "GET") {
        const row = await env.DB.prepare(
          "SELECT value FROM system_config WHERE key = 'announcements'"
        ).first();
        const announcements = row ? row.value : "No announcements active.";
        return new Response(
          JSON.stringify({ announcements }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/version" && method === "GET") {
        const row = await env.DB.prepare(
          "SELECT value FROM system_config WHERE key = 'latest_version'"
        ).first();
        const version = row ? row.value : "2.0.0";
        return new Response(version, { status: 200, headers: { ...corsHeaders, "Content-Type": "text/plain" } });
      }
      if (path === "/api/changelog" && method === "GET") {
        const row = await env.DB.prepare(
          "SELECT value FROM system_config WHERE key = 'changelog'"
        ).first();
        const changelog = row ? row.value : "";
        return new Response(changelog, { status: 200, headers: { ...corsHeaders, "Content-Type": "text/plain" } });
      }
      if (path === "/api/update" && method === "GET") {
        const clientVer = url.searchParams.get("version") || "";
        const configData = await env.DB.prepare("SELECT key, value FROM system_config").all();
        const configMap = {};
        configData.results.forEach((row) => {
          configMap[row.key] = row.value;
        });
        const latestVersion = configMap.latest_version || "2.0.0";
        const changelog = configMap.changelog || "";
        const downloadUrl = configMap.download_url || "";
        return new Response(
          JSON.stringify({
            latest_version: latestVersion,
            changelog: changelog,
            download_url: downloadUrl,
            update_available: latestVersion !== clientVer
          }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/login" && method === "POST") {
        const body = await request.json().catch(() => ({}));
        const username = (body.username || "").trim();
        const password = (body.password || "").trim();
        const hwid = (body.hwid || "").trim();
        if (!username || !password) {
          return new Response(
            JSON.stringify({ success: false, message: "Username and password required" }),
            { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const user = await env.DB.prepare("SELECT * FROM users WHERE username = ?")
          .bind(username)
          .first();
        if (!user || !bcrypt.compareSync(password, user.password_hash)) {
          await env.DB.prepare(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)"
          )
          .bind(username, clientIP, hwid, "FAILED_PASSWORD")
          .run();
          return new Response(
            JSON.stringify({ success: false, message: "Invalid username or password" }),
            { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (user.is_banned === 1) {
          await env.DB.prepare(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)"
          )
          .bind(username, clientIP, hwid, "BANNED")
          .run();
          return new Response(
            JSON.stringify({ success: false, message: "Account has been banned" }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        let userHWID = user.hwid;
        if (!userHWID) {
          await env.DB.prepare("UPDATE users SET hwid = ? WHERE username = ?")
            .bind(hwid, username)
            .run();
          userHWID = hwid;
        } else if (userHWID !== hwid) {
          await env.DB.prepare(
            "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)"
          )
          .bind(username, clientIP, hwid, "DEVICE_MISMATCH")
          .run();
          return new Response(
            JSON.stringify({ 
              success: false, 
              message: "Device mismatch." 
            }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const nowStr = new Date().toISOString().replace("T", " ").substring(0, 19);
        await env.DB.prepare("UPDATE users SET last_login = ? WHERE username = ?")
          .bind(nowStr, username)
          .run();
        await env.DB.prepare(
          "INSERT INTO login_history (username, ip_address, hwid, status) VALUES (?, ?, ?, ?)"
        )
        .bind(username, clientIP, hwid, "SUCCESS")
        .run();
        const expirationEpoch = Math.floor(Date.now() / 1000) + (24 * 3600);
        const token = await signJWT(
          { username: user.username, role: user.role, exp: expirationEpoch },
          jwtSecret
        );
        const creditsVal = user.credits !== null ? user.credits : 15;
        const creditsUnlimited = !!user.credits_unlimited;
        return new Response(
          JSON.stringify({
            success: true,
            token: token,
            user_data: {
              username: user.username,
              ip: clientIP,
              hwid: userHWID,
              role: user.role,
              expires: "Never (Lifetime)",
              createdate: user.created_at,
              lastlogin: nowStr,
              subscription: user.role === "admin" ? "Developer Admin" : user.role === "moderator" ? "Moderator" : "Standard Client",
              credits: creditsVal,
              credits_unlimited: creditsUnlimited,
              lifetime_requests: user.lifetime_requests || 0
            }
          }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/register" && method === "POST") {
        const body = await request.json().catch(() => ({}));
        const username = (body.username || "").trim();
        const password = (body.password || "").trim();
        const hwid = (body.hwid || "").trim();
        const requestedRole = (body.role || "user").trim();
        const inviteKey = (body.invite_key || "").trim();
        if (!username || !password) {
          return new Response(
            JSON.stringify({ success: false, message: "Username and password required" }),
            { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const existingUser = await env.DB.prepare("SELECT username FROM users WHERE username = ?")
          .bind(username)
          .first();
        if (existingUser) {
          return new Response(
            JSON.stringify({ success: false, message: "Username already exists" }),
            { status: 409, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const hashed = bcrypt.hashSync(password, 10);
        let finalRole = "user";
        let isBootstrap = false;
        const userCountRow = await env.DB.prepare("SELECT COUNT(*) as count FROM users").first();
        const isEmpty = userCountRow ? userCountRow.count === 0 : true;
        if (isEmpty) {
          finalRole = "admin";
          isBootstrap = true;
        } else {
          const initSecretHeader = request.headers.get("X-Init-Secret");
          if (initSecretHeader && env.INIT_SECRET && initSecretHeader === env.INIT_SECRET) {
            if (requestedRole === "admin" || requestedRole === "moderator") {
              finalRole = requestedRole;
              isBootstrap = true;
            }
          }
        }
        if (!isBootstrap) {
          if (!inviteKey) {
            return new Response(
              JSON.stringify({ success: false, message: "A valid invite/access key is required for registration." }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const inviteRow = await env.DB.prepare("SELECT * FROM invite_keys WHERE key = ? AND is_used = 0")
            .bind(inviteKey)
            .first();
          if (!inviteRow) {
            return new Response(
              JSON.stringify({ success: false, message: "Invalid or already used invite/access key." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          await env.DB.prepare("UPDATE invite_keys SET is_used = 1, used_by = ? WHERE key = ?")
            .bind(username, inviteKey)
            .run();
        }
        const initialCredits = 15;
        const initialUnlimited = finalRole === "admin" ? 1 : 0;
        await env.DB.prepare(
          "INSERT INTO users (username, password_hash, hwid, role, credits, credits_unlimited) VALUES (?, ?, ?, ?, ?, ?)"
        )
        .bind(username, hashed, hwid || null, finalRole, initialCredits, initialUnlimited)
        .run();
        if (isBootstrap && finalRole !== "user") {
          await logAudit(
            env,
            "SYSTEM_INIT",
            "INITIALIZE_PRIVILEGED_ROLE",
            username,
            clientIP,
            `User registered as role '${finalRole}' with unlimited=${initialUnlimited}.`
          );
        } else {
          await logAudit(
            env,
            "SYSTEM",
            "REGISTER_USER_WITH_KEY",
            username,
            clientIP,
            `User registered using access key '${inviteKey}'. Credits: ${initialCredits}.`
          );
        }
        return new Response(
          JSON.stringify({ success: true, message: `Registration successful. Assigned role: ${finalRole}` }),
          { status: 201, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/user/credits" && method === "GET") {
        const session = await authenticateToken(request, env);
        if (!session) {
          return new Response(
            JSON.stringify({ message: "Unauthorized" }),
            { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const user = await env.DB.prepare(
          "SELECT credits, credits_unlimited, lifetime_requests, last_request_at FROM users WHERE username = ?"
        ).bind(session.username).first();
        if (!user) {
          return new Response(
            JSON.stringify({ message: "User not found" }),
            { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({
            username: session.username,
            credits: user.credits !== null ? user.credits : 0,
            credits_unlimited: !!user.credits_unlimited,
            lifetime_requests: user.lifetime_requests || 0,
            last_request_at: user.last_request_at || null
          }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path === "/api/user/consume-credit" && method === "POST") {
        const session = await authenticateToken(request, env);
        if (!session) {
          return new Response(
            JSON.stringify({ message: "Unauthorized" }),
            { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const user = await env.DB.prepare(
          "SELECT credits, credits_unlimited FROM users WHERE username = ?"
        ).bind(session.username).first();
        if (!user) {
          return new Response(
            JSON.stringify({ message: "User not found" }),
            { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const nowStr = new Date().toISOString().replace("T", " ").substring(0, 19);
        if (user.credits_unlimited) {
          await env.DB.prepare(
            "UPDATE users SET lifetime_requests = lifetime_requests + 1, last_request_at = ? WHERE username = ?"
          ).bind(nowStr, session.username).run();
          return new Response(
            JSON.stringify({ success: true, credits: -1, unlimited: true, message: "Request processed." }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (!user.credits || user.credits <= 0) {
          return new Response(
            JSON.stringify({
              success: false,
              credits: 0,
              unlimited: false,
              message: "No credits available. Contact administrator."
            }),
            { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        await env.DB.prepare(
          "UPDATE users SET credits = credits - 1, lifetime_requests = lifetime_requests + 1, last_request_at = ? WHERE username = ?"
        ).bind(nowStr, session.username).run();
        const updated = await env.DB.prepare(
          "SELECT credits FROM users WHERE username = ?"
        ).bind(session.username).first();
        return new Response(
          JSON.stringify({
            success: true,
            credits: updated ? updated.credits : 0,
            unlimited: false,
            message: "Credit consumed."
          }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (path.startsWith("/api/admin")) {
        const session = await authenticateToken(request, env);
        if (!session) {
          return new Response(
            JSON.stringify({ success: false, message: "Invalid or expired session token." }),
            { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        const actorRole = session.role;
        const actorName = session.username;
        if (actorRole !== "admin" && actorRole !== "moderator") {
          return new Response(
            JSON.stringify({ success: false, message: "Forbidden. Admin or Moderator privileges required." }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/invites" && method === "GET") {
          const invitesQuery = await env.DB.prepare(
            "SELECT key, is_used, used_by, created_at FROM invite_keys ORDER BY created_at DESC"
          ).all();
          return new Response(
            JSON.stringify(invitesQuery.results),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/invites" && method === "POST") {
          const inviteUUID = crypto.randomUUID().substring(0, 12).toUpperCase();
          const key = `PORTAL-${inviteUUID}`;
          await env.DB.prepare(
            "INSERT INTO invite_keys (key, is_used) VALUES (?, 0)"
          )
          .bind(key)
          .run();
          await logAudit(
            env,
            actorName,
            "GENERATE_INVITE_KEY",
            key,
            clientIP,
            "Generated a new invite key."
          );
          return new Response(
            JSON.stringify({ message: "Invite key generated successfully", key: key }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path.startsWith("/api/admin/invites/") && method === "DELETE") {
          const targetKey = decodeURIComponent(path.substring("/api/admin/invites/".length));
          await env.DB.prepare("DELETE FROM invite_keys WHERE key = ?").bind(targetKey).run();
          await logAudit(env, actorName, "DELETE_INVITE_KEY", targetKey, clientIP, `Deleted invite key.`);
          return new Response(
            JSON.stringify({ message: `Invite key '${targetKey}' deleted successfully` }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/users" && method === "GET") {
          const oldestUserRow = await env.DB.prepare(
            "SELECT username FROM users ORDER BY created_at ASC LIMIT 1"
          ).first();
          const oldestUser = oldestUserRow ? oldestUserRow.username : null;
          const usersQuery = await env.DB.prepare(
            "SELECT username, role, hwid, is_banned, credits, credits_unlimited, lifetime_requests, last_request_at, created_at, last_login FROM users"
          ).all();
          const primaryOwner = env.PRIMARY_OWNER || "admin";
          const results = usersQuery.results.map(u => ({
            ...u,
            is_owner: u.username === oldestUser || u.username === primaryOwner
          }));
          return new Response(
            JSON.stringify(results),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path.match(/^\/api\/admin\/users\/[^/]+\/credits$/) && method === "GET") {
          const targetUser = decodeURIComponent(path.split("/")[4]);
          const user = await env.DB.prepare(
            "SELECT credits, credits_unlimited, lifetime_requests, last_request_at FROM users WHERE username = ?"
          ).bind(targetUser).first();
          if (!user) {
            return new Response(
              JSON.stringify({ message: "User not found" }),
              { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          return new Response(
            JSON.stringify({
              username: targetUser,
              credits: user.credits !== null ? user.credits : 0,
              credits_unlimited: !!user.credits_unlimited,
              lifetime_requests: user.lifetime_requests || 0,
              last_request_at: user.last_request_at || null
            }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path.match(/^\/api\/admin\/users\/[^/]+\/credits$/) && method === "POST") {
          if (actorRole !== "admin") {
            return new Response(
              JSON.stringify({ message: "Admin role required for credit management." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const targetUser = decodeURIComponent(path.split("/")[4]);
          const body = await request.json().catch(() => ({}));
          const action = body.action || "set";
          const amount = parseInt(body.amount) || 0;
          const unlimited = body.unlimited;
          const userExists = await env.DB.prepare("SELECT username FROM users WHERE username = ?").bind(targetUser).first();
          if (!userExists) {
            return new Response(
              JSON.stringify({ message: "User not found" }),
              { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          let auditDetails = "";
          if (unlimited !== undefined) {
            await env.DB.prepare("UPDATE users SET credits_unlimited = ? WHERE username = ?")
              .bind(unlimited ? 1 : 0, targetUser).run();
            const state = unlimited ? "enabled" : "disabled";
            auditDetails = `Unlimited credits ${state}`;
            await logAudit(env, actorName, "SET_CREDITS_UNLIMITED", targetUser, clientIP, auditDetails);
            return new Response(
              JSON.stringify({ message: `Unlimited credits ${state} for '${targetUser}'.` }),
              { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (action === "set") {
            await env.DB.prepare("UPDATE users SET credits = ? WHERE username = ?").bind(amount, targetUser).run();
            auditDetails = `Credits set to ${amount}`;
          } else if (action === "add") {
            await env.DB.prepare("UPDATE users SET credits = credits + ? WHERE username = ?").bind(amount, targetUser).run();
            auditDetails = `Added ${amount} credits`;
          } else {
            return new Response(
              JSON.stringify({ message: "Invalid action." }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const updated = await env.DB.prepare("SELECT credits FROM users WHERE username = ?").bind(targetUser).first();
          await logAudit(env, actorName, `ADMIN_CREDITS_${action.toUpperCase()}`, targetUser, clientIP, auditDetails);
          return new Response(
            JSON.stringify({ message: `${auditDetails} for '${targetUser}'.`, credits: updated.credits }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/users" && method === "POST") {
          const body = await request.json().catch(() => ({}));
          const username = (body.username || "").trim();
          const password = (body.password || "").trim();
          const targetRole = (body.role || "user").trim();
          if (!username || !password) {
            return new Response(
              JSON.stringify({ message: "Username and password required" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (actorRole === "moderator" && targetRole !== "user") {
            return new Response(
              JSON.stringify({ message: "Moderators cannot create privileged user profiles." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const hashed = bcrypt.hashSync(password, 10);
          try {
            await env.DB.prepare(
              "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)"
            )
            .bind(username, hashed, targetRole)
            .run();
            await logAudit(
              env,
              actorName,
              "CREATE_USER",
              username,
              clientIP,
              `Created profile with role '${targetRole}'.`
            );
            return new Response(
              JSON.stringify({ message: `User '${username}' created successfully` }),
              { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          } catch (e) {
            return new Response(
              JSON.stringify({ message: "Username already exists or database error" }),
              { status: 409, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
        }
        if (path.startsWith("/api/admin/users/") && method === "DELETE") {
          const targetUser = decodeURIComponent(path.substring("/api/admin/users/".length));
          if (actorName === targetUser) {
            return new Response(
              JSON.stringify({ message: "Cannot delete your own account" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (await isPrimaryOwner(targetUser, env)) {
            return new Response(
              JSON.stringify({ message: "Cannot delete the protected primary owner account." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const targetProfile = await env.DB.prepare("SELECT role FROM users WHERE username = ?")
            .bind(targetUser)
            .first();
          if (!targetProfile) {
            return new Response(
              JSON.stringify({ message: "User not found" }),
              { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (actorRole === "moderator") {
            return new Response(
              JSON.stringify({ message: "Moderators are not authorized to delete profiles." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          await env.DB.prepare("DELETE FROM users WHERE username = ?").bind(targetUser).run();
          await logAudit(env, actorName, "DELETE_USER", targetUser, clientIP, `Deleted user profile.`);
          return new Response(
            JSON.stringify({ message: `User '${targetUser}' deleted successfully` }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/reset-password" && method === "POST") {
          const body = await request.json().catch(() => ({}));
          const targetUser = (body.username || "").trim();
          const newPassword = (body.password || "").trim();
          if (!targetUser || !newPassword) {
            return new Response(
              JSON.stringify({ message: "Username and new password required" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (await isPrimaryOwner(targetUser, env) && actorName !== targetUser) {
            return new Response(
              JSON.stringify({ message: "Cannot reset password for the protected primary owner account." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const targetProfile = await env.DB.prepare("SELECT role FROM users WHERE username = ?")
            .bind(targetUser)
            .first();
          if (!targetProfile) {
            return new Response(
              JSON.stringify({ message: "User not found" }),
              { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (actorRole === "moderator" && targetProfile.role === "admin") {
            return new Response(
              JSON.stringify({ message: "Moderators cannot reset administrator passwords." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const hashed = bcrypt.hashSync(newPassword, 10);
          await env.DB.prepare("UPDATE users SET password_hash = ? WHERE username = ?")
            .bind(hashed, targetUser)
            .run();
          await logAudit(env, actorName, "RESET_PASSWORD", targetUser, clientIP, `Reset user password.`);
          return new Response(
            JSON.stringify({ message: `Password for user '${targetUser}' reset successfully` }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/reset-hwid" && method === "POST") {
          const body = await request.json().catch(() => ({}));
          const targetUser = (body.username || "").trim();
          if (!targetUser) {
            return new Response(
              JSON.stringify({ message: "Username required" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (await isPrimaryOwner(targetUser, env) && actorName !== targetUser) {
            return new Response(
              JSON.stringify({ message: "Cannot reset HWID for the protected primary owner account." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          await env.DB.prepare("UPDATE users SET hwid = NULL WHERE username = ?")
            .bind(targetUser)
            .run();
          await logAudit(env, actorName, "RESET_HWID", targetUser, clientIP, `Reset HWID binding.`);
          return new Response(
            JSON.stringify({ message: `Hardware ID for user '${targetUser}' reset successfully` }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/ban" && method === "POST") {
          const body = await request.json().catch(() => ({}));
          const targetUser = (body.username || "").trim();
          const banned = Number(body.banned ?? 1);
          if (!targetUser) {
            return new Response(
              JSON.stringify({ message: "Username required" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (actorName === targetUser) {
            return new Response(
              JSON.stringify({ message: "Cannot ban your own account" }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (await isPrimaryOwner(targetUser, env)) {
            return new Response(
              JSON.stringify({ message: "Cannot ban the protected primary owner account." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const targetProfile = await env.DB.prepare("SELECT role FROM users WHERE username = ?")
            .bind(targetUser)
            .first();
          if (!targetProfile) {
            return new Response(
              JSON.stringify({ message: "User not found" }),
              { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          if (actorRole === "moderator" && targetProfile.role === "admin") {
            return new Response(
              JSON.stringify({ message: "Moderators cannot ban admin profiles." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          await env.DB.prepare("UPDATE users SET is_banned = ? WHERE username = ?")
            .bind(banned, targetUser)
            .run();
          const action = banned === 1 ? "BANNED" : "UNBANNED";
          await logAudit(env, actorName, action, targetUser, clientIP, `Banned status set to: ${banned}`);
          return new Response(
            JSON.stringify({ message: `User '${targetUser}' has been ${action.toLowerCase()}` }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/version" && method === "POST") {
          if (actorRole !== "admin") {
            return new Response(
              JSON.stringify({ message: "Forbidden. Admin role required to modify configuration." }),
              { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const body = await request.json().catch(() => ({}));
          const version = (body.version || "").trim();
          const changelog = (body.changelog || "").trim();
          const downloadUrl = (body.download_url || "").trim();
          const announcements = (body.announcements || "").trim();
          if (!version && !announcements && !changelog && !downloadUrl) {
            return new Response(
              JSON.stringify({ message: "Provide at least one setting to update." }),
              { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          const statements = [];
          if (version) {
            statements.push(env.DB.prepare("INSERT OR REPLACE INTO system_config (key, value) VALUES ('latest_version', ?)").bind(version));
          }
          if (changelog) {
            statements.push(env.DB.prepare("INSERT OR REPLACE INTO system_config (key, value) VALUES ('changelog', ?)").bind(changelog));
          }
          if (downloadUrl) {
            statements.push(env.DB.prepare("INSERT OR REPLACE INTO system_config (key, value) VALUES ('download_url', ?)").bind(downloadUrl));
          }
          if (announcements) {
            statements.push(env.DB.prepare("INSERT OR REPLACE INTO system_config (key, value) VALUES ('announcements', ?)").bind(announcements));
          }
          await env.DB.batch(statements);
          await logAudit(
            env,
            actorName,
            "UPDATE_SYSTEM_METADATA",
            null,
            clientIP,
            `Updated configs: version='${version}', url='${downloadUrl}'`
          );
          return new Response(
            JSON.stringify({ message: "System configuration updated successfully" }),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/audit-logs" && method === "GET") {
          const logsQuery = await env.DB.prepare(
            "SELECT id, actor, action, target, ip_address, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 150"
          ).all();
          return new Response(
            JSON.stringify(logsQuery.results),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (path === "/api/admin/login-history" && method === "GET") {
          const historyQuery = await env.DB.prepare(
            "SELECT id, username, ip_address, hwid, status, timestamp FROM login_history ORDER BY id DESC LIMIT 150"
          ).all();
          return new Response(
            JSON.stringify(historyQuery.results),
            { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
      }
      return new Response(
        JSON.stringify({ success: false, message: "Endpoint not found" }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    } catch (err) {
      console.error(err);
      return new Response(
        JSON.stringify({ success: false, message: `Server error: ${err.message}` }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
  },
};
