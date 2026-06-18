#!/usr/bin/env node

const http = require("http");
const { spawn } = require("child_process");

function arg(name, fallback = "") {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) return fallback;
  const values = [];
  for (let i = index + 1; i < process.argv.length; i += 1) {
    if (process.argv[i].startsWith("--")) break;
    values.push(process.argv[i]);
  }
  return values.length ? values.join(" ") : fallback;
}

function startCommand(label, command) {
  if (!command) return;
  const child = spawn(command, { shell: true, stdio: "inherit" });
  child.on("exit", (code, signal) => {
    console.error(`${label} exited`, { code, signal });
    process.exit(code || 1);
  });
}

function proxy(req, res, upstream, stripPrefix = "") {
  const target = new URL(upstream);
  let path = req.url || "/";
  if (stripPrefix && path.startsWith(stripPrefix)) {
    path = path.slice(stripPrefix.length) || "/";
  }

  const options = {
    hostname: target.hostname,
    port: target.port,
    protocol: target.protocol,
    method: req.method,
    path,
    headers: {
      ...req.headers,
      host: target.host,
    },
  };

  const upstreamReq = http.request(options, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
    upstreamRes.pipe(res);
  });

  upstreamReq.on("error", (error) => {
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: error.message }));
  });

  req.pipe(upstreamReq);
}

const listen = Number(arg("--listen", process.env.PORT || "8080"));
const apiPrefix = arg("--api-prefix", "/api");
const apiUpstream = arg("--api-upstream", process.env.API_UPSTREAM || "");
const mcpUpstream = arg("--mcp-upstream", process.env.MCP_UPSTREAM || "");

startCommand("mcp", arg("--mcp-command", ""));
startCommand("api", arg("--api-command", ""));

const server = http.createServer((req, res) => {
  const url = req.url || "/";
  if (url === "/healthz") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }
  if (apiUpstream && url.startsWith(apiPrefix)) {
    proxy(req, res, apiUpstream, apiPrefix);
    return;
  }
  if (mcpUpstream) {
    proxy(req, res, mcpUpstream);
    return;
  }
  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: "no upstream matched" }));
});

server.listen(listen, "0.0.0.0", () => {
  console.log(`dual-entrypoint listening on ${listen}`);
});
