const COLOR_AI = { 0: "#3dff7a", 1: "#ffd000", 2: "#ff3b3b", 3: "#3ec6ff" };

function dibujarMapa(canvas, estado) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.fillStyle = "#0c120b";
  ctx.fillRect(0, 0, w, h);

  const T = Number((estado.params && estado.params.T) || 60);
  const pad = 48;
  const side = Math.min(w - pad * 1.2, h - pad * 1.2);
  const x0 = pad;
  const y0 = h - pad;
  const escala = side / T;
  const toX = (x) => x0 + x * escala;
  const toY = (y) => y0 - y * escala;

  ctx.strokeStyle = "#243322";
  ctx.lineWidth = 1;
  for (let k = 0; k <= 6; k++) {
    const v = (T * k) / 6;
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(v));
    ctx.lineTo(toX(T), toY(v));
    ctx.moveTo(toX(v), toY(0));
    ctx.lineTo(toX(v), toY(T));
    ctx.stroke();
  }
  ctx.strokeStyle = "#3d5a32";
  ctx.strokeRect(toX(0), toY(T), T * escala, T * escala);
  ctx.fillStyle = "#8aa078";
  ctx.font = "11px monospace";
  ctx.fillText("X (km)", w / 2, h - 12);
  ctx.save();
  ctx.translate(14, h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Y (km)", 0, 0);
  ctx.restore();

  const agentes = agentesDelDia(estado);
  if (!agentes.length) {
    ctx.fillStyle = "#8aa078";
    ctx.font = "14px monospace";
    ctx.textAlign = "center";
    ctx.fillText("SIN AGENTES — genere el teatro de operaciones", w / 2, h / 2);
    ctx.textAlign = "left";
    return { toX, toY, escala, agentes: [] };
  }

  if (estado.mostrarRadios) {
    ctx.strokeStyle = "rgba(197,165,114,0.28)";
    ctx.setLineDash([4, 4]);
    agentes.forEach((a) => {
      ctx.beginPath();
      ctx.arc(toX(a.AX), toY(a.AY), Number(a.AR) * escala, 0, Math.PI * 2);
      ctx.stroke();
    });
    ctx.setLineDash([]);
  }

  if (estado.mostrarRutas && estado.hit && estado.viewDay > 0) {
    const pos = Object.fromEntries(agentes.map((a) => [a.AID, a]));
    estado.hit.filter((m) => m.dia === estado.viewDay && m.NT > 0).forEach((m) => {
      const a = pos[m.X];
      const b = pos[m.Y];
      if (!a || !b) return;
      const infecto = Number(m.IT) === 1;
      ctx.strokeStyle = infecto ? "#ff7a18" : "#3dff7a";
      ctx.lineWidth = infecto ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(toX(a.AX), toY(a.AY));
      ctx.lineTo(toX(b.AX), toY(b.AY));
      ctx.stroke();
      const ang = Math.atan2(toY(b.AY) - toY(a.AY), toX(b.AX) - toX(a.AX));
      ctx.beginPath();
      ctx.moveTo(toX(b.AX), toY(b.AY));
      ctx.lineTo(toX(b.AX) - 8 * Math.cos(ang - 0.4), toY(b.AY) - 8 * Math.sin(ang - 0.4));
      ctx.lineTo(toX(b.AX) - 8 * Math.cos(ang + 0.4), toY(b.AY) - 8 * Math.sin(ang + 0.4));
      ctx.closePath();
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fill();
    });
  }

  const anMax = Math.max(...agentes.map((a) => Number(a.AN) || 1), 1);
  agentes.forEach((a) => {
    const x = toX(a.AX);
    const y = toY(a.AY);
    const r = 6 + 10 * (Number(a.AN) / anMax);
    ctx.fillStyle = COLOR_AI[Number(a.AI)] || "#999";
    ctx.strokeStyle = Number(a.AC) === 1 ? "#ffffff" : "#0b0f0a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    if (a.AT === "GE") {
      ctx.rect(x - r, y - r, r * 2, r * 2);
    } else if (a.AT === "MA") {
      ctx.moveTo(x, y - r);
      ctx.lineTo(x + r, y);
      ctx.lineTo(x, y + r);
      ctx.lineTo(x - r, y);
      ctx.closePath();
    } else {
      ctx.arc(x, y, r, 0, Math.PI * 2);
    }
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#c5d3b4";
    ctx.font = "10px monospace";
    ctx.fillText(String(a.AID), x + r + 2, y - 4);
  });
  return { toX, toY, escala, agentes };
}

function agentesDelDia(estado) {
  const base = estado.agentes || [];
  if (!estado.has || !estado.has.length) return base;
  const snap = {};
  estado.has.filter((r) => Number(r.dia) === Number(estado.viewDay)).forEach((r) => {
    snap[r.AID] = r;
  });
  if (!Object.keys(snap).length) return base;
  return base.map((a) => {
    const s = snap[a.AID];
    return s ? Object.assign({}, a, { AI: s.AI, AC: s.AC, MI: s.MI }) : a;
  });
}

function aidEnClick(canvas, evt, proyect) {
  if (!proyect || !proyect.agentes) return null;
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const sy = canvas.height / rect.height;
  const mx = (evt.clientX - rect.left) * sx;
  const my = (evt.clientY - rect.top) * sy;
  let best = null;
  let bestD = 16;
  proyect.agentes.forEach((a) => {
    const dx = proyect.toX(a.AX) - mx;
    const dy = proyect.toY(a.AY) - my;
    const d = Math.hypot(dx, dy);
    if (d < bestD) { bestD = d; best = a.AID; }
  });
  return best;
}
