const API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error("GET " + path + " → " + r.status);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    const data = await r.json();
    if (!r.ok || data.error) throw new Error(data.error || ("POST " + path + " → " + r.status));
    return data;
  },
  defaults() { return this.get("/defaults"); },
  generar(params) { return this.post("/generar", params); },
  simular(payload) { return this.post("/simular", payload); }
};
