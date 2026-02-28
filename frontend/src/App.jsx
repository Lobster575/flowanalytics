import { useState, useEffect, useRef, useCallback } from "react"
const API = import.meta.env.VITE_API_URL

// ─── Constants ────────────────────────────────────────────────────────────────
const FIATS = ["PLN", "EUR", "USD", "GBP", "CZK", "HUF"]
const CRYPTOS = ["USDT", "BTC", "ETH", "USDC"]
const EXCHANGES_CONFIG = [
  { id: "bybit",   label: "Bybit",   color: "#f7a600" },
  { id: "binance", label: "Binance", color: "#f0b90b" },
]
const CHART_SYMBOLS = [
  { id: "BTCUSDT", label: "BTC", name: "Bitcoin" },
  { id: "ETHUSDT", label: "ETH", name: "Ethereum" },
  { id: "BNBUSDT", label: "BNB", name: "BNB Chain" },
  { id: "SOLUSDT", label: "SOL", name: "Solana" },
  { id: "XRPUSDT", label: "XRP", name: "Ripple" },
]
const INTERVALS = ["15m","1h","4h","1d","1w"]
const COIN_NAMES = {
  BTC:"Bitcoin",ETH:"Ethereum",BNB:"BNB Chain",SOL:"Solana",XRP:"Ripple",
  ADA:"Cardano",DOT:"Polkadot",LINK:"Chainlink",AVAX:"Avalanche",MATIC:"Polygon",
  DOGE:"Dogecoin",SHIB:"Shiba Inu",LTC:"Litecoin",UNI:"Uniswap",TRX:"TRON",
}
const SORT_OPTIONS = [
  { id: "price", label: "Price" },
  { id: "volume", label: "Volume" },
  { id: "rate", label: "Rating" },
]

// ─── Fluid Particle Canvas ────────────────────────────────────────────────────
function ParticleField() {
  const ref = useRef(null)
  const mouseRef = useRef({ x: -1000, y: -1000 })

  useEffect(() => {
    const cv = ref.current
    const ctx = cv.getContext("2d")
    const set = () => { cv.width = window.innerWidth; cv.height = window.innerHeight }
    set()

    const COUNT = 110
    const pts = Array.from({ length: COUNT }, () => ({
      x: Math.random() * cv.width,
      y: Math.random() * cv.height,
      ox: 0, oy: 0,
      vx: (Math.random() - .5) * .4,
      vy: (Math.random() - .5) * .4,
      r: Math.random() * 1.8 + .5,
      o: Math.random() * .55 + .12,
    }))
    pts.forEach(p => { p.ox = p.x; p.oy = p.y })

    let raf
    const draw = () => {
      ctx.clearRect(0, 0, cv.width, cv.height)
      const mx = mouseRef.current.x
      const my = mouseRef.current.y

      pts.forEach(p => {
        // fluid repulsion from mouse
        const dx = p.x - mx, dy = p.y - my
        const dist = Math.sqrt(dx * dx + dy * dy)
        const radius = 120
        if (dist < radius && dist > 0) {
          const force = (1 - dist / radius) * 2.5
          p.vx += (dx / dist) * force
          p.vy += (dy / dist) * force
        }
        // spring back to origin
        p.vx += (p.ox - p.x) * 0.012
        p.vy += (p.oy - p.y) * 0.012
        // damping
        p.vx *= 0.88
        p.vy *= 0.88

        p.x += p.vx; p.y += p.vy

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(90,160,255,${p.o})`
        ctx.fill()
      })

      // connections
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)
          if (d < 100) {
            ctx.beginPath()
            ctx.moveTo(pts[i].x, pts[i].y)
            ctx.lineTo(pts[j].x, pts[j].y)
            ctx.strokeStyle = `rgba(90,160,255,${.09 * (1 - d / 100)})`
            ctx.lineWidth = .5
            ctx.stroke()
          }
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()

    const onMouse = e => { mouseRef.current = { x: e.clientX, y: e.clientY } }
    const onLeave = () => { mouseRef.current = { x: -1000, y: -1000 } }
    window.addEventListener("mousemove", onMouse)
    window.addEventListener("mouseleave", onLeave)
    window.addEventListener("resize", set)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("mousemove", onMouse)
      window.removeEventListener("mouseleave", onLeave)
      window.removeEventListener("resize", set)
    }
  }, [])
  return <canvas ref={ref} style={{ position: "fixed", top: 0, left: 0, zIndex: 0, pointerEvents: "none" }} />
}

// ─── Canvas Chart ─────────────────────────────────────────────────────────────
function BinanceChart({ data }) {
  const canvasRef = useRef(null)
  const [hovered, setHovered] = useState(null)
  const [crosshair, setCrosshair] = useState(null)
  const CHART_H = 300, VOL_H = 65
  const PAD = { top: 38, right: 78, bottom: 20, left: 10 }
  const MA_COLORS = { ma7: "#f0b90b", ma25: "#e8465a", ma99: "#a855f7" }

  useEffect(() => {
    if (!data.length) return
    const canvas = canvasRef.current
    if (!canvas) return
    const W = canvas.offsetWidth
    canvas.width = W * window.devicePixelRatio
    canvas.height = (CHART_H + VOL_H) * window.devicePixelRatio
    canvas.style.height = `${CHART_H + VOL_H}px`
    const ctx = canvas.getContext("2d")
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    const chartW = W - PAD.left - PAD.right
    const chartH = CHART_H - PAD.top - PAD.bottom
    const prices = data.flatMap(d => [d.high, d.low])
    const minP = Math.min(...prices), maxP = Math.max(...prices)
    const pRange = maxP - minP || 1
    const toY = p => PAD.top + chartH - ((p - minP) / pRange) * chartH
    const maxV = Math.max(...data.map(d => d.volume))
    const toVY = v => CHART_H + VOL_H - 4 - (v / maxV) * (VOL_H - 10)
    const barW = Math.max(1, chartW / data.length - 1)
    const toX = i => PAD.left + (i / (data.length - 1)) * chartW

    // grid
    ctx.strokeStyle = "rgba(50,90,180,0.1)"
    ctx.lineWidth = 1
    for (let i = 0; i <= 5; i++) {
      const y = PAD.top + (chartH / 5) * i
      ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke()
      const price = maxP - (pRange / 5) * i
      ctx.fillStyle = "rgba(130,170,255,0.45)"
      ctx.font = "9px DM Mono, monospace"
      ctx.textAlign = "left"
      ctx.fillText(price >= 1000 ? price.toLocaleString(undefined, { maximumFractionDigits: 0 }) : price.toFixed(4), W - PAD.right + 6, y + 3)
    }

    // crosshair
    if (crosshair) {
      ctx.strokeStyle = "rgba(130,170,255,0.2)"
      ctx.lineWidth = 1
      ctx.setLineDash([3, 4])
      ctx.beginPath(); ctx.moveTo(crosshair.x, PAD.top); ctx.lineTo(crosshair.x, CHART_H - PAD.bottom); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(PAD.left, crosshair.y); ctx.lineTo(W - PAD.right, crosshair.y); ctx.stroke()
      ctx.setLineDash([])
    }

    // MA lines
    ;["ma99", "ma25", "ma7"].forEach(key => {
      ctx.strokeStyle = MA_COLORS[key]; ctx.lineWidth = 1.2
      ctx.beginPath(); let s = false
      data.forEach((d, i) => {
        if (d[key] == null) return
        const x = toX(i), y = toY(d[key])
        if (!s) { ctx.moveTo(x, y); s = true } else ctx.lineTo(x, y)
      })
      ctx.stroke()
    })

    // candles
    data.forEach((d, i) => {
      const x = toX(i), up = d.close >= d.open
      const col = up ? "#26a69a" : "#ef5350"
      const bodyTop = toY(Math.max(d.open, d.close))
      const bodyBot = toY(Math.min(d.open, d.close))
      const bodyH = Math.max(1, bodyBot - bodyTop)
      const hw = Math.max(.5, barW / 2)
      ctx.strokeStyle = col; ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(x, toY(d.high)); ctx.lineTo(x, bodyTop)
      ctx.moveTo(x, bodyBot); ctx.lineTo(x, toY(d.low))
      ctx.stroke()
      ctx.fillStyle = up ? "rgba(38,166,154,0.9)" : "rgba(239,83,80,0.85)"
      ctx.fillRect(x - hw, bodyTop, barW, bodyH)
    })

    // volume
    data.forEach((d, i) => {
      const x = toX(i), hw = Math.max(.5, barW / 2)
      const vy = toVY(d.volume)
      ctx.fillStyle = d.close >= d.open ? "rgba(38,166,154,0.3)" : "rgba(239,83,80,0.25)"
      ctx.fillRect(x - hw, vy, barW, CHART_H + VOL_H - 4 - vy)
    })

    ctx.strokeStyle = "rgba(50,90,180,0.08)"; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(PAD.left, CHART_H); ctx.lineTo(W - PAD.right, CHART_H); ctx.stroke()

    // x labels
    ctx.fillStyle = "rgba(100,140,255,0.3)"; ctx.font = "9px DM Mono, monospace"; ctx.textAlign = "center"
    const step = Math.ceil(data.length / 8)
    data.forEach((d, i) => {
      if (i % step === 0) ctx.fillText(new Date(d.time).toLocaleDateString([], { month: "short", day: "numeric" }), toX(i), CHART_H + VOL_H - 2)
    })

    // MA legend
    let lx = PAD.left + 4
    ;[["MA(7)", "ma7"], ["MA(25)", "ma25"], ["MA(99)", "ma99"]].forEach(([label, key]) => {
      const last = [...data].reverse().find(d => d[key] != null)
      if (!last) return
      ctx.font = "9px DM Mono, monospace"; ctx.fillStyle = MA_COLORS[key]; ctx.textAlign = "left"
      const txt = `${label} ${last[key]?.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
      ctx.fillText(txt, lx, 14)
      lx += ctx.measureText(txt).width + 14
    })
  }, [data, crosshair, hovered])

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas || !data.length) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left, my = e.clientY - rect.top
    const W = canvas.offsetWidth
    const chartW = W - PAD.left - PAD.right
    const idx = Math.round(((mx - PAD.left) / chartW) * (data.length - 1))
    if (idx >= 0 && idx < data.length) { setHovered(idx); setCrosshair({ x: mx, y: my }) }
  }, [data])

  const hd = hovered !== null ? data[hovered] : data[data.length - 1]
  return (
    <div style={{ position: "relative" }}>
      {hd && (
        <div style={{ position: "absolute", top: 18, left: PAD.left + 4, display: "flex", gap: 14, zIndex: 2, pointerEvents: "none", flexWrap: "wrap" }}>
          <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10, color: "rgba(140,180,255,0.5)" }}>
            {new Date(hd.time).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" })}
          </span>
          {[["O", hd.open], ["H", hd.high], ["L", hd.low], ["C", hd.close]].map(([k, v]) => (
            <span key={k} style={{ fontFamily: "DM Mono,monospace", fontSize: 10 }}>
              <span style={{ color: "rgba(100,140,255,0.4)" }}>{k} </span>
              <span style={{ color: hd.close >= hd.open ? "#26a69a" : "#ef5350" }}>{v?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            </span>
          ))}
          <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10 }}>
            <span style={{ color: "rgba(100,140,255,0.4)" }}>CHG </span>
            <span style={{ color: hd.close >= hd.open ? "#26a69a" : "#ef5350" }}>{(((hd.close - hd.open) / hd.open) * 100).toFixed(2)}%</span>
          </span>
        </div>
      )}
      <canvas ref={canvasRef} style={{ width: "100%", height: `${CHART_H + VOL_H}px`, cursor: "crosshair" }}
        onMouseMove={handleMouseMove} onMouseLeave={() => { setHovered(null); setCrosshair(null) }} />
    </div>
  )
}

// ─── Rate Bar ─────────────────────────────────────────────────────────────────
function RateBar({ rate, trades }) {
  const [tip, setTip] = useState(false)
  const col = rate >= 95 ? "#26a69a" : rate >= 80 ? "#f7a600" : "#ef5350"
  return (
    <div style={{ position: "relative", cursor: "default" }}
      onMouseEnter={() => setTip(true)} onMouseLeave={() => setTip(false)}>
      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
        <div style={{ flex: 1, height: 3, background: "rgba(255,255,255,0.07)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ width: `${rate}%`, height: "100%", background: col, borderRadius: 2 }} />
        </div>
        <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10, color: col, opacity: .8, whiteSpace: "nowrap" }}>{rate.toFixed(0)}%</span>
      </div>
      {tip && (
        <div style={{ position: "absolute", bottom: "calc(100% + 8px)", left: 0, background: "rgba(4,10,28,0.98)", border: "1px solid rgba(80,130,255,0.25)", borderRadius: 10, padding: "10px 14px", fontFamily: "DM Mono,monospace", fontSize: 11, whiteSpace: "nowrap", zIndex: 200, pointerEvents: "none", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
          <div style={{ color: "rgba(150,190,255,0.5)", marginBottom: 5 }}>Seller stats</div>
          <div style={{ color: "#fff", marginBottom: 3 }}>Completion: <span style={{ color: col }}>{rate.toFixed(1)}%</span></div>
          <div style={{ color: "rgba(150,190,255,0.6)" }}>Total trades: {trades}</div>
        </div>
      )}
    </div>
  )
}

// ─── Copy Price ───────────────────────────────────────────────────────────────
function CopyPrice({ price, fiat }) {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(String(price)); setCopied(true); setTimeout(() => setCopied(false), 1500) }
  return (
    <span onClick={copy} style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span>{price.toFixed(3)}</span>
      <span style={{ fontSize: 10, color: "rgba(120,160,255,0.45)", fontFamily: "DM Mono,monospace" }}>{fiat}</span>
      {copied && <span style={{ fontSize: 9, color: "#26a69a", fontFamily: "DM Mono,monospace" }}>✓</span>}
    </span>
  )
}

// ─── Auto-refresh dot ─────────────────────────────────────────────────────────
function LiveDot({ lastUpdated }) {
  const [pulse, setPulse] = useState(false)
  useEffect(() => { setPulse(true); const t = setTimeout(() => setPulse(false), 800); return () => clearTimeout(t) }, [lastUpdated])
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 7, height: 7, borderRadius: "50%", background: "#26a69a",
        boxShadow: pulse ? "0 0 0 4px rgba(38,166,154,0.3)" : "none",
        transition: "box-shadow .4s ease"
      }} />
      {lastUpdated && <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10, color: "rgba(120,170,255,0.4)" }}>{lastUpdated}</span>}
    </div>
  )
}

// ─── Calculator ───────────────────────────────────────────────────────────────
function Calculator({ offers, side }) {
  const [amount, setAmount] = useState("")
  const [fromCur, setFromCur] = useState(side === "BUY" ? FIATS[0] : CRYPTOS[0])
  const [toCur, setToCur] = useState(side === "BUY" ? CRYPTOS[0] : FIATS[0])

  const best = offers.length ? offers.reduce((a, b) => side === "BUY" ? (a.price < b.price ? a : b) : (a.price > b.price ? a : b)) : null
  const num = parseFloat(amount) || 0
  const result = best && num ? (side === "BUY" ? num / best.price : num * best.price) : null

  const Sel = ({ value, options, onChange }) => (
    <div style={{ position: "relative" }}>
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ appearance: "none", background: "rgba(4,10,28,0.9)", border: "1px solid rgba(80,130,255,0.2)", borderRadius: 8, padding: "5px 24px 5px 10px", fontFamily: "DM Mono,monospace", fontSize: 11, color: "#a8c8ff", cursor: "pointer", outline: "none" }}>
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
      <span style={{ position: "absolute", right: 7, top: "50%", transform: "translateY(-50%)", color: "rgba(80,130,255,0.4)", fontSize: 9, pointerEvents: "none" }}>▾</span>
    </div>
  )

  return (
    <div className="glass-strong" style={{ padding: "18px 22px", marginBottom: 16 }}>
      <div style={{ fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(120,170,255,0.45)", fontFamily: "DM Mono,monospace", marginBottom: 12 }}>Quick Calculator</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: 1, minWidth: 140, display: "flex", gap: 0 }}>
          <input type="number" value={amount} onChange={e => setAmount(Math.max(0, e.target.value))}
            min="0"
            placeholder="0.00"
            style={{ flex: 1, background: "rgba(4,10,28,0.8)", border: "1px solid rgba(80,130,255,0.18)", borderRight: "none", borderRadius: "10px 0 0 10px", padding: "10px 12px", fontFamily: "DM Mono,monospace", fontSize: 15, color: "#fff", outline: "none", minWidth: 0 }}
            onFocus={e => e.target.style.borderColor = "rgba(80,130,255,0.45)"}
            onBlur={e => e.target.style.borderColor = "rgba(80,130,255,0.18)"} />
          <div style={{ background: "rgba(8,20,55,0.9)", border: "1px solid rgba(80,130,255,0.18)", borderLeft: "none", borderRadius: "0 10px 10px 0", padding: "0 8px", display: "flex", alignItems: "center" }}>
            <Sel value={fromCur} options={side === "BUY" ? FIATS : CRYPTOS} onChange={setFromCur} />
          </div>
        </div>

        <span style={{ color: "rgba(100,150,255,0.4)", fontSize: 16, flexShrink: 0 }}>→</span>

        <div style={{ flex: 1, minWidth: 140, background: "rgba(4,10,28,0.6)", border: "1px solid rgba(80,130,255,0.1)", borderRadius: 10, padding: "10px 12px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: "DM Mono,monospace", fontSize: 16, fontWeight: 600, color: result ? "#26a69a" : "rgba(80,130,255,0.2)" }}>
            {result ? result.toFixed(side === "BUY" ? 4 : 2) : "—"}
          </span>
          <Sel value={toCur} options={side === "BUY" ? CRYPTOS : FIATS} onChange={setToCur} />
        </div>
      </div>

      {best && result && (
        <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10, color: "rgba(100,150,255,0.35)" }}>best match →</span>
          {best.url ? (
            <a href={best.url} target="_blank" rel="noreferrer" style={{ fontFamily: "DM Mono,monospace", fontSize: 11, color: "#5ba8ff", textDecoration: "none" }}>
              {best.trusted && "⭐ "}{best.advertiser} ↗
            </a>
          ) : (
            <span style={{ fontFamily: "DM Mono,monospace", fontSize: 11, color: "#5ba8ff" }}>{best.trusted && "⭐ "}{best.advertiser}</span>
          )}
          <span style={{ fontFamily: "DM Mono,monospace", fontSize: 10, color: "rgba(100,150,255,0.35)" }}>@ {best.price.toFixed(3)}</span>
        </div>
      )}
    </div>
  )
}

// ─── Market Mode ──────────────────────────────────────────────────────────────
function MarketMode() {
  const [chartData, setChartData] = useState([])
  const [trending, setTrending] = useState([])
  const [symbol, setSymbol] = useState("BTCUSDT")
  const [interval, setInterval] = useState("1d")
  const [loadingChart, setLoadingChart] = useState(true)
  const [loadingTrending, setLoadingTrending] = useState(true)

  useEffect(() => {
    setLoadingChart(true)
    fetch(`${API}/market/chart?symbol=${symbol}&interval=${interval}`)
      .then(r => r.json()).then(d => { setChartData(d.data || []); setLoadingChart(false) })
      .catch(() => setLoadingChart(false))
  }, [symbol, interval])

  useEffect(() => {
    setLoadingTrending(true)
    fetch(`${API}/market/trending`)
      .then(r => r.json()).then(d => { setTrending(d.data || []); setLoadingTrending(false) })
      .catch(() => setLoadingTrending(false))
  }, [])

  const last = chartData[chartData.length - 1]
  const first = chartData[0]
  const change = last && first ? ((last.close - first.close) / first.close * 100) : null
  const isUp = (change || 0) >= 0
  const symInfo = CHART_SYMBOLS.find(s => s.id === symbol)

  return (
    <div>
      <div className="glass-strong" style={{ marginBottom: 16, overflow: "hidden" }}>
        <div style={{ padding: "14px 18px 0", display: "flex", gap: 2, flexWrap: "wrap", borderBottom: "1px solid rgba(50,90,180,0.08)" }}>
          {CHART_SYMBOLS.map(s => (
            <button key={s.id} onClick={() => setSymbol(s.id)} style={{
              padding: "7px 14px", border: "none", cursor: "pointer", fontFamily: "DM Mono,monospace", fontSize: 12, fontWeight: 600, transition: "all .2s",
              background: symbol === s.id ? "rgba(38,166,154,0.1)" : "transparent",
              color: symbol === s.id ? "#26a69a" : "rgba(120,170,255,0.4)",
              borderBottom: symbol === s.id ? "2px solid #26a69a" : "2px solid transparent",
              borderRadius: "4px 4px 0 0", marginBottom: -1
            }}>{s.label}/USDT</button>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", gap: 3, alignItems: "center", paddingBottom: 8 }}>
            {INTERVALS.map(iv => (
              <button key={iv} onClick={() => setInterval(iv)} style={{
                padding: "5px 9px", borderRadius: 6, border: "none", cursor: "pointer",
                fontFamily: "DM Mono,monospace", fontSize: 11, transition: "all .2s",
                background: interval === iv ? "rgba(80,130,255,0.14)" : "transparent",
                color: interval === iv ? "#c8dcff" : "rgba(100,150,255,0.3)"
              }}>{iv}</button>
            ))}
          </div>
        </div>

        <div style={{ padding: "14px 18px 4px", display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontFamily: "DM Mono,monospace", color: "rgba(120,170,255,0.4)", marginRight: 4 }}>{symInfo?.name}</span>
                    {last && (
            <>
              <span style={{ fontSize: 30, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", fontFamily: "DM Mono,monospace" }}>
                {last.close.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>

              {change !== null && (
                <span style={{ fontSize: 13, fontFamily: "DM Mono,monospace", color: isUp ? "#26a69a" : "#ef5350" }}>
                  {isUp ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
                </span>
              )}

              <a
                href={`https://www.binance.com/en/trade/${symInfo?.label}_USDT`}
                target="_blank"
                rel="noreferrer"
                style={{ marginLeft: "auto", padding: "6px 14px", borderRadius: 8 }}
              >
                Trade ↗
              </a>
            </>
          )}
        </div>

        <div style={{ padding: "4px 0 0" }}>
          {loadingChart ? (
            <div style={{ height: 365, display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(80,130,255,0.3)", fontFamily: "DM Mono,monospace", fontSize: 12 }}>
              <span className="pulse" style={{ marginRight: 8 }} />loading chart...
            </div>
          ) : <BinanceChart data={chartData} />}
        </div>
      </div>

      <div className="glass-strong" style={{ overflow: "hidden" }}>
        <div style={{ padding: "13px 18px", borderBottom: "1px solid rgba(50,90,180,0.07)" }}>
          <span style={{ fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(100,150,255,0.4)", fontFamily: "DM Mono,monospace" }}>Top Movers 24h</span>
        </div>
        {loadingTrending ? (
          <div style={{ padding: 36, textAlign: "center", color: "rgba(80,130,255,0.3)", fontFamily: "DM Mono,monospace", fontSize: 12 }}>
            <span className="pulse" />loading...
          </div>
        ) : (
          <>
            <div style={{ padding: "10px 18px", display: "grid", gridTemplateColumns: "1.4fr 1.2fr 1fr 1.5fr", gap: 12, borderBottom: "1px solid rgba(50,90,180,0.05)" }}>
              {["Symbol", "Price", "24h", "Volume"].map(h => (
                <span key={h} style={{ fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(80,130,255,0.3)", fontFamily: "DM Mono,monospace" }}>{h}</span>
              ))}
            </div>
            {trending.map((t, i) => (
              <a key={i} href={`https://www.binance.com/en/trade/${t.symbol}_USDT`} target="_blank" rel="noreferrer"
                style={{ padding: "10px 18px", display: "grid", gridTemplateColumns: "1.4fr 1.2fr 1fr 1.5fr", gap: 12, alignItems: "center", borderBottom: "1px solid rgba(50,90,180,0.03)", textDecoration: "none", opacity: 0, transform: "translateY(5px)", animation: `fadeUp .3s forwards ${i * 20}ms`, transition: "background .15s" }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(80,130,255,0.04)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                <div>
                  <div style={{ fontFamily: "DM Mono,monospace", fontSize: 13, fontWeight: 600, color: "#cce0ff" }}>{t.symbol}<span style={{ color: "rgba(100,150,255,0.3)", fontWeight: 400 }}>/USDT</span></div>
                  <div style={{ fontFamily: "DM Mono,monospace", fontSize: 9, color: "rgba(80,130,255,0.35)", marginTop: 2 }}>{COIN_NAMES[t.symbol] || ""}</div>
                </div>
                <span style={{ fontFamily: "DM Mono,monospace", fontSize: 12, color: "rgba(180,210,255,0.65)" }}>
                  ${t.price < 1 ? t.price.toFixed(5) : t.price.toLocaleString()}
                </span>
                <span style={{ fontFamily: "DM Mono,monospace", fontSize: 13, fontWeight: 600, color: t.change >= 0 ? "#26a69a" : "#ef5350" }}>
                  {t.change >= 0 ? "▲" : "▼"} {Math.abs(t.change).toFixed(2)}%
                </span>
                <span style={{ fontFamily: "DM Mono,monospace", fontSize: 11, color: "rgba(80,130,255,0.4)" }}>
                  ${(t.volume / 1_000_000).toFixed(1)}M
                </span>
              </a>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [mode, setMode] = useState("p2p")
  const [offers, setOffers] = useState([])
  const [loading, setLoading] = useState(true)
  const [fiat, setFiat] = useState("PLN")
  const [crypto, setCrypto] = useState("USDT")
  const [side, setSide] = useState("BUY")
  const [exchange, setExchange] = useState("bybit")
  const [sort, setSort] = useState("price")
  const [lastUpdated, setLastUpdated] = useState(null)
  const [countdown, setCountdown] = useState(30)
  const [error, setError] = useState(null)
  const prevOffersRef = useRef([])

  const loadOffers = useCallback((f, c, s, ex, sr) => {
    setError(null)
    fetch(`${API}/p2p?fiat=${f}&crypto=${c}&side=${s}&exchange=${ex}&sort=${sr}`)
      .then(r => r.json())
      .then(d => {
        prevOffersRef.current = d.offers || []
        setOffers(d.offers || [])
        setLoading(false)
        setLastUpdated(new Date().toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }))
        setCountdown(30)
      })
      .catch(() => { setError("Connection error"); setLoading(false) })
  }, [])

  useEffect(() => {
    if (mode !== "p2p") return
    // Don't clear offers on refresh — smooth transition
    setLoading(true)
    loadOffers(fiat, crypto, side, exchange, sort)
    const iv = setInterval(() => loadOffers(fiat, crypto, side, exchange, sort), 30000)
    const tick = setInterval(() => setCountdown(c => c > 0 ? c - 1 : 30), 1000)
    return () => { clearInterval(iv); clearInterval(tick) }
  }, [fiat, crypto, side, exchange, sort, mode, loadOffers])

  const bestPrice = offers.length ? Math.min(...offers.map(o => o.price)) : null

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
        body{background:#040a18;min-height:100vh;overflow-x:hidden;font-family:'Syne',sans-serif;display:flex;justify-content:center;}

        /* Grid only, no noise */
        body::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
          background-image:linear-gradient(rgba(50,100,220,0.045) 1px,transparent 1px),linear-gradient(90deg,rgba(50,100,220,0.045) 1px,transparent 1px);
          background-size:46px 46px;}

        .bg-orb{position:fixed;border-radius:50%;filter:blur(120px);pointer-events:none;z-index:0;}
        .orb1{width:700px;height:700px;background:radial-gradient(circle,rgba(15,55,155,0.22) 0%,transparent 70%);top:-220px;left:-130px;}
        .orb2{width:550px;height:550px;background:radial-gradient(circle,rgba(0,110,210,0.12) 0%,transparent 70%);bottom:-130px;right:-90px;}
        .orb3{width:340px;height:340px;background:radial-gradient(circle,rgba(38,166,154,0.07) 0%,transparent 70%);top:38%;left:42%;}

        .wrapper{position:relative;z-index:1;min-height:100vh;padding:36px 22px 80px;max-width:1020px;width:100%;}

        /* Liquid glass card */
        .glass-strong{
          background:rgba(8,16,42,0.55);
          backdrop-filter:blur(32px) saturate(1.4);
          -webkit-backdrop-filter:blur(32px) saturate(1.4);
          border:2px solid rgba(90,140,255,0.18);
          border-radius:20px;
          box-shadow:0 0 0 1px rgba(255,255,255,0.04) inset, 0 24px 48px rgba(0,0,0,0.35);
          transform:translateZ(0);
          isolation:isolate;
        }
        .glass{
          background:rgba(6,14,36,0.5);
          backdrop-filter:blur(20px);
          -webkit-backdrop-filter:blur(20px);
          border:1.5px solid rgba(70,120,220,0.14);
          border-radius:16px;
        }

        .header{margin-bottom:30px;}
        .logo{font-size:11px;font-weight:600;letter-spacing:.32em;text-transform:uppercase;color:rgba(100,160,255,0.45);margin-bottom:12px;}
        .title{font-size:clamp(28px,4.8vw,52px);font-weight:800;line-height:1.06;color:#fff;letter-spacing:-.02em;}
        .title span{background:linear-gradient(135deg,#4a9eff,#88c4ff,#e0f0ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
        .subtitle{margin-top:8px;font-size:13px;color:rgba(120,170,255,0.38);font-family:'DM Mono',monospace;font-weight:300;}

        .mode-switcher{display:inline-flex;background:rgba(6,14,36,0.7);border:2px solid rgba(70,120,220,0.15);border-radius:14px;padding:4px;margin-bottom:18px;}
        .mode-btn{padding:9px 28px;border-radius:10px;border:none;cursor:pointer;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;letter-spacing:.02em;transition:all .25s;background:transparent;color:rgba(120,170,255,0.35);}
        .mode-btn.active{background:rgba(12,30,90,0.95);color:#fff;box-shadow:0 2px 16px rgba(0,50,180,0.25);}

        .exchange-tabs{display:flex;gap:7px;margin-bottom:12px;}
        .ex-tab{padding:8px 16px;border-radius:11px;border:1.5px solid rgba(70,120,220,0.14);background:rgba(6,14,36,0.5);cursor:pointer;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;color:rgba(120,170,255,0.35);transition:all .2s;display:flex;align-items:center;gap:7px;}
        .ex-tab:hover{border-color:rgba(70,120,220,0.28);color:rgba(180,215,255,0.6);}
        .ex-tab.active{background:rgba(10,24,72,0.85);border-color:rgba(90,150,255,0.35);color:#d8ecff;}
        .ex-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}

        .controls{padding:15px 18px;display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:14px;}
        .sel-wrap{position:relative;}
        .sel-wrap select{appearance:none;background:rgba(4,10,26,0.88);border:1.5px solid rgba(70,120,220,0.18);color:#b8d4ff;font-family:'DM Mono',monospace;font-size:12px;font-weight:500;padding:8px 30px 8px 12px;border-radius:10px;cursor:pointer;outline:none;transition:all .2s;letter-spacing:.04em;}
        .sel-wrap select:hover{border-color:rgba(70,120,220,0.4);}
        .sel-wrap::after{content:'▾';position:absolute;right:9px;top:50%;transform:translateY(-50%);color:rgba(70,120,220,0.45);pointer-events:none;font-size:9px;}

        .side-toggle{display:flex;background:rgba(4,10,26,0.88);border:1.5px solid rgba(70,120,220,0.18);border-radius:10px;overflow:hidden;}
        .side-btn{padding:8px 16px;font-family:'DM Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.07em;border:none;cursor:pointer;transition:all .25s;color:rgba(120,170,255,0.38);background:transparent;}
        .side-btn.buy-active{background:rgba(38,166,154,0.18);color:#3dd6ae;border-radius:8px;text-shadow:0 0 12px rgba(38,166,154,0.5);}
        .side-btn.sell-active{background:rgba(239,83,80,0.16);color:#ff7070;border-radius:8px;text-shadow:0 0 12px rgba(239,83,80,0.45);}

        .sort-tabs{display:flex;gap:4px;}
        .sort-btn{padding:7px 12px;border-radius:9px;border:1.5px solid rgba(70,120,220,0.13);background:transparent;cursor:pointer;font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.06em;color:rgba(120,170,255,0.35);transition:all .2s;}
        .sort-btn.active{background:rgba(10,24,72,0.8);border-color:rgba(90,150,255,0.3);color:#a8ccff;}

        .meta{margin-left:auto;display:flex;align-items:center;gap:12px;}
        .countdown svg{transform:rotate(-90deg);}
        .countdown-track{fill:none;stroke:rgba(60,100,200,0.12);stroke-width:2;}
        .countdown-fill{fill:none;stroke:rgba(70,140,255,0.5);stroke-width:2;stroke-linecap:round;stroke-dasharray:88;transition:stroke-dashoffset 1s linear;}

        /* P2P Table */
        .table-wrap{overflow:hidden;}
        .table-header{padding:11px 18px;border-bottom:1px solid rgba(60,100,200,0.07);display:grid;grid-template-columns:1.2fr 1.8fr 1.8fr 0.55fr 2fr;gap:10px;}
        .th{font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:rgba(80,130,255,0.35);font-family:'DM Mono',monospace;}

        /* Compact row */
        .row{
          padding:10px 18px;
          display:grid;grid-template-columns:1.2fr 1.8fr 1.8fr 0.55fr 2fr;gap:10px;
          align-items:center;
          border-bottom:1px solid rgba(60,100,200,0.05);
          transition:background .2s, opacity .3s;
          opacity:0;transform:translateY(5px);animation:fadeUp .28s forwards;
        }
        .row:hover{background:rgba(70,120,220,0.04);}
        .row.best{background:rgba(38,166,154,0.05);animation:fadeUp .28s forwards, bestFlash .7s ease .1s;}
        @keyframes fadeUp{to{opacity:1;transform:translateY(0);}}
        @keyframes bestFlash{0%{background:rgba(38,166,154,0.14);}100%{background:rgba(38,166,154,0.05);}}

        .price-cell{font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#d0e4ff;cursor:pointer;transition:color .15s;line-height:1.2;}
        .price-cell:hover{color:#fff;}
        .range-cell{font-family:'DM Mono',monospace;font-size:11px;color:rgba(140,180,255,0.55);line-height:1.7;}
        .range-label{font-size:9px;color:rgba(80,130,255,0.35);letter-spacing:.05em;}
        .fee-cell{font-family:'DM Mono',monospace;font-size:11px;color:#26a69a;text-align:center;}

        .adv-wrap{display:flex;flex-direction:column;gap:4px;min-width:0;}
        .adv-row{display:flex;align-items:center;gap:5px;}
        .adv-name{font-size:12px;color:rgba(180,210,255,0.7);font-weight:600;text-decoration:none;transition:color .15s;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
        .adv-name:hover{color:#7ab8ff;}
        .link-icon{opacity:0;font-size:8px;transition:opacity .15s;flex-shrink:0;}
        .adv-name:hover .link-icon{opacity:1;}
        .payment-tags{display:flex;flex-wrap:wrap;gap:3px;margin-top:1px;}
        .payment-tag{font-family:'DM Mono',monospace;font-size:8px;color:rgba(80,130,255,0.5);background:rgba(20,50,130,0.22);border:1px solid rgba(60,100,200,0.12);border-radius:4px;padding:1px 5px;white-space:nowrap;}

        .best-badge{display:inline-block;font-size:8px;letter-spacing:.08em;text-transform:uppercase;background:rgba(38,166,154,0.14);color:#26a69a;padding:1px 6px;border-radius:20px;margin-left:5px;font-family:'DM Mono',monospace;vertical-align:middle;}

        .loading-state{padding:50px;text-align:center;color:rgba(80,130,255,0.35);font-family:'DM Mono',monospace;font-size:12px;letter-spacing:.1em;}
        .error-state{padding:32px;text-align:center;color:rgba(239,83,80,0.5);font-family:'DM Mono',monospace;font-size:12px;}

        .pulse{display:inline-block;width:6px;height:6px;border-radius:50%;background:#26a69a;margin-right:7px;animation:pulse 1.6s infinite;}
        @keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.25;transform:scale(.65);}}
        .divider{width:1px;height:16px;background:rgba(60,100,200,0.14);}

        @media(max-width:640px){
          .wrapper{padding:20px 13px 60px;}
          .title{font-size:32px;}
          .subtitle{font-size:11px;}
          .logo{font-size:10px;}

          .mode-switcher{width:100%;display:flex;}
          .mode-btn{flex:1;padding:9px 0;text-align:center;}

          .exchange-tabs{flex-wrap:wrap;}
          .ex-tab{padding:7px 12px;font-size:12px;}

          .controls{flex-wrap:wrap;padding:11px 13px;gap:7px;}
          .sel-wrap select{font-size:11px;padding:7px 24px 7px 10px;}
          .side-toggle{flex:1;}
          .side-btn{padding:7px 12px;font-size:11px;}
          .sort-tabs{flex:1;display:flex;justify-content:flex-end;}
          .sort-btn{padding:6px 8px;font-size:9px;}
          .divider{display:none;}
          .meta{width:100%;justify-content:flex-end;margin-left:0;}

          .table-header{
            grid-template-columns:1.3fr 0fr 1.1fr 0.5fr 1.7fr !important;
            gap:6px;padding:9px 12px;
          }
          .table-header .th:nth-child(2){display:none;}
          .row{
            grid-template-columns:1.3fr 0fr 1.1fr 0.5fr 1.7fr !important;
            gap:6px;padding:9px 12px;
          }
          .row>div:nth-child(2){display:none;}
          .price-cell{font-size:12px;}
          .range-cell{font-size:10px;}
          .adv-name{font-size:11px;}
          .payment-tags{display:none;}
          .best-badge{font-size:7px;}

          .glass-strong, .glass{border-radius:14px;}
        }

        @media(max-width:400px){
          .title{font-size:26px;}
          .price-cell{font-size:11px;}
          .adv-name{font-size:10px;}
        }
      `}</style>

      <ParticleField />
      <div className="bg-orb orb1" />
      <div className="bg-orb orb2" />
      <div className="bg-orb orb3" />

      <div className="wrapper">
        <div className="header">
          <div className="logo">⬡ Metaflow</div>
          <h1 className="title">Meta<span>flow</span><br />Analytics</h1>
          <p className="subtitle">// real-time · {mode === "p2p" ? `${exchange} p2p` : "market overview"}</p>
        </div>

        <div className="mode-switcher">
          <button className={`mode-btn ${mode === "p2p" ? "active" : ""}`} onClick={() => setMode("p2p")}>P2P</button>
          <button className={`mode-btn ${mode === "market" ? "active" : ""}`} onClick={() => setMode("market")}>Market</button>
        </div>

        {mode === "market" ? <MarketMode /> : (
          <>
            <div className="exchange-tabs">
              {EXCHANGES_CONFIG.map(ex => (
                <button key={ex.id} className={`ex-tab ${exchange === ex.id ? "active" : ""}`} onClick={() => setExchange(ex.id)}>
                  <span className="ex-dot" style={{ background: ex.color }} />
                  {ex.label}
                </button>
              ))}
            </div>

            <div className="glass-strong controls">
              <div className="sel-wrap">
                <select value={fiat} onChange={e => setFiat(e.target.value)}>
                  {FIATS.map(f => <option key={f}>{f}</option>)}
                </select>
              </div>
              <div className="divider" />
              <div className="sel-wrap">
                <select value={crypto} onChange={e => setCrypto(e.target.value)}>
                  {CRYPTOS.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="divider" />
              <div className="side-toggle">
                {["BUY", "SELL"].map(s => (
                  <button key={s}
                    className={`side-btn ${side === s ? (s === "BUY" ? "buy-active" : "sell-active") : ""}`}
                    onClick={() => setSide(s)}>{s}
                  </button>
                ))}
              </div>
              <div className="divider" />
              <div className="sort-tabs">
                {SORT_OPTIONS.map(o => (
                  <button key={o.id} className={`sort-btn ${sort === o.id ? "active" : ""}`} onClick={() => setSort(o.id)}>{o.label}</button>
                ))}
              </div>
              <div className="meta">
                <LiveDot lastUpdated={lastUpdated} />
                <div className="countdown">
                  <svg width="26" height="26" viewBox="0 0 32 32">
                    <circle className="countdown-track" cx="16" cy="16" r="14" />
                    <circle className="countdown-fill" cx="16" cy="16" r="14" style={{ strokeDashoffset: 88 - (countdown / 30) * 88 }} />
                  </svg>
                </div>
              </div>
            </div>

            {!loading && offers.length > 0 && (
              <Calculator offers={offers} side={side} />
            )}

            <div className="glass-strong table-wrap">
              {loading && offers.length === 0 ? (
                <div className="loading-state"><span className="pulse" />fetching offers...</div>
              ) : error ? (
                <div className="error-state">⚠ {error}</div>
              ) : offers.length === 0 ? (
                <div className="loading-state">no offers found</div>
              ) : (
                <>
                  <div className="table-header">
                    <span className="th">Price</span>
                    <span className="th">Min amount</span>
                    <span className="th">Max amount</span>
                    <span className="th">Fee</span>
                    <span className="th">Advertiser</span>
                  </div>
                  {offers.map((o, i) => {
                    const isBest = o.price === bestPrice
                    return (
                      <div key={`${o.advertiser}-${i}`} className={`row ${isBest ? "best" : ""}`}
                        style={{ animationDelay: `${i * 28}ms` }}>

                        <div className="price-cell" style={isBest ? { color: "#26a69a" } : {}}>
                          <CopyPrice price={o.price} fiat={fiat} />
                          {isBest && <span className="best-badge">best</span>}
                        </div>

                        <div className="range-cell">
                          <div><span className="range-label">MIN </span>{o.min_amount.toLocaleString()}</div>
                        </div>

                        <div className="range-cell">
                          <div><span className="range-label">MAX </span>{o.max_amount.toLocaleString()}</div>
                          {o.completion_rate > 0 && (
                            <div style={{ marginTop: 4 }}>
                              <RateBar rate={o.completion_rate} trades={o.trade_count || 0} />
                            </div>
                          )}
                        </div>

                        <div className="fee-cell">{o.commission === 0 ? "0%" : `${o.commission}%`}</div>

                        <div className="adv-wrap">
                          <div className="adv-row">
                            {o.url ? (
                              <a className="adv-name" href={o.url} target="_blank" rel="noreferrer">
                                {o.trusted && <span style={{ fontSize: 11, flexShrink: 0 }}>⭐</span>}
                                {o.advertiser}
                                <span className="link-icon">↗</span>
                              </a>
                            ) : (
                              <span className="adv-name">
                                {o.trusted && <span style={{ fontSize: 11 }}>⭐</span>}
                                {o.advertiser}
                              </span>
                            )}
                          </div>
                          {o.payment_methods?.length > 0 && (
                            <div className="payment-tags">
                              {o.payment_methods.slice(0, 4).map((pm, j) => <span key={j} className="payment-tag">{pm}</span>)}
                              {o.payment_methods.length > 4 && <span className="payment-tag">+{o.payment_methods.length - 4}</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}