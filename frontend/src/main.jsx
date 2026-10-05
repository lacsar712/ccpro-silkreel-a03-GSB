import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, clearToken, setToken, token } from "./api.js";
import "./app.css";

const STATUS_LABEL = { soaking: "浸茧", reeling: "缫丝中", reeled: "已缫完" };
const MAX_DIFF = 120;

function Login({ onOk }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(data.access_token);
      onOk();
    } catch (ex) {
      setErr(ex.message);
    }
  }
  return (
    <div class="login">
      <h1>江口缫丝坞</h1>
      <p>汤温环盆作业台，不是列表台账。</p>
      <form onSubmit={submit} autocomplete="off">
        <label>
          用户名
          <input name="username" autocomplete="off" value={username} onInput={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          密码
          <input name="password" type="password" autocomplete="off" value={password} onInput={(e) => setPassword(e.target.value)} />
        </label>
        <p class="hint">已预填 admin / 123456，另有 worker / 123456</p>
        <button type="submit">登录</button>
      </form>
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function TopNav({ view, onNav, onLogout }) {
  return (
    <nav class="topnav">
      <button
        class={view === "ring" ? "nav-on" : ""}
        onClick={() => onNav("ring")}
      >
        环盆作业台
      </button>
      <button
        class={view === "cocoon" ? "nav-on" : ""}
        onClick={() => onNav("cocoon")}
      >
        茧粒台
      </button>
      <button class="logout" onClick={onLogout}>
        退出
      </button>
    </nav>
  );
}

function YardPicker({ yards, yardId, onPick, allowAll }) {
  return (
    <select class="yard-pick" value={yardId ?? ""} onChange={(e) => onPick(e.target.value === "" ? null : Number(e.target.value))}>
      {allowAll && <option value="">全部坞</option>}
      {yards.map((y) => (
        <option value={y.id} key={y.id}>
          {y.name}（{y.riverside}）
        </option>
      ))}
    </select>
  );
}

function RingBoard({ onNav, onLogout }) {
  const [yards, setYards] = useState(null);
  const [yardId, setYardId] = useState(null);
  const [picked, setPicked] = useState(null);
  const [temp, setTemp] = useState("40");
  const [err, setErr] = useState("");

  async function refresh() {
    const data = await api("/api/board");
    setYards(data.yards);
    setYardId((cur) =>
      cur && data.yards.some((y) => y.id === cur) ? cur : data.yards[0].id
    );
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  if (!yards) {
    return (
      <div class="yard">
        <TopNav view="ring" onNav={onNav} onLogout={onLogout} />
        {err || "装载环盆…"}
      </div>
    );
  }

  const yard = yards.find((y) => y.id === yardId) || yards[0];
  const basins = yard.basins;
  const n = basins.length;
  const current = picked && basins.find((b) => b.id === picked.id);

  async function writeTemp() {
    setErr("");
    try {
      await api(`/api/basins/${current.id}/readings`, {
        method: "POST",
        body: JSON.stringify({ waterTempC: Number(temp) }),
      });
      await refresh();
    } catch (ex) {
      setErr(ex.message);
    }
  }
  async function setStatus(status) {
    setErr("");
    try {
      await api(`/api/basins/${current.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await refresh();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div class="yard">
      <TopNav view="ring" onNav={onNav} onLogout={onLogout} />
      <div class="topbar">
        <div>
          <h1>{yard.name}</h1>
          <p>
            {yard.riverside} · 点盆登记汤温；改缫丝中时与邻盆比茧粒（差不得超过 {MAX_DIFF}）；
            已缫完须最近汤温 38～42℃
          </p>
        </div>
        <YardPicker yards={yards} yardId={yard.id} allowAll={false} onPick={(id) => { setYardId(id); setPicked(null); setErr(""); }} />
      </div>
      <div class="ring">
        {basins.map((b, i) => {
          const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
          const left = 50 + Math.cos(angle) * 38;
          const top = 50 + Math.sin(angle) * 38;
          return (
            <button
              key={b.id}
              class={`basin ${b.status}${current && current.id === b.id ? " picked" : ""}`}
              style={{ left: `${left}%`, top: `${top}%` }}
              onClick={() => { setPicked(b); setErr(""); }}
            >
              <strong>{b.code}</strong>
              <span>{STATUS_LABEL[b.status]}</span>
              <span>{b.cocoonCount} 粒</span>
            </button>
          );
        })}
      </div>
      {current && (
        <div class="drawer">
          <h3>
            {current.code} · {STATUS_LABEL[current.status]}
          </h3>
          <p>
            茧粒：{current.cocoonCount} 粒 · 最近汤温：{current.latestTempC ?? "无"} ℃ · 记录 {current.readingCount} 次
          </p>
          <input value={temp} onInput={(e) => setTemp(e.target.value)} />
          <button onClick={writeTemp}>登记汤温</button>
          <div>
            <button onClick={() => setStatus("soaking")}>浸茧</button>
            <button onClick={() => setStatus("reeling")}>缫丝中</button>
            <button onClick={() => setStatus("reeled")}>已缫完</button>
          </div>
          {err && <p class="err">{err}</p>}
        </div>
      )}
    </div>
  );
}

function CocoonBoard({ onNav, onLogout }) {
  const [yards, setYards] = useState(null);
  const [yardId, setYardId] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/api/cocoon-board")
      .then((data) => {
        setYards(data.yards);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const visible = yards
    ? yardId == null
      ? yards
      : yards.filter((y) => y.id === yardId)
    : null;

  return (
    <div class="yard cocoon-page">
      <TopNav view="cocoon" onNav={onNav} onLogout={onLogout} />
      <div class="topbar">
        <div>
          <h1>茧粒台</h1>
          <p>只读：各盆茧粒数，以及与最近缫丝中盆的差（超过 {MAX_DIFF} 粒标红）。</p>
        </div>
        {yards && (
          <YardPicker
            yards={yards}
            yardId={yardId}
            allowAll
            onPick={(id) => { setYardId(id); setErr(""); }}
          />
        )}
      </div>
      {!yards && (err || "装载茧粒台…")}
      {visible &&
        visible.map((yard) => (
          <section class="cocoon-yard" key={yard.id}>
            <h2>
              {yard.name}（{yard.riverside}）
            </h2>
            <table>
              <thead>
                <tr>
                  <th>盆号</th>
                  <th>状态</th>
                  <th>环序</th>
                  <th>茧粒（粒）</th>
                  <th>最近缫丝中盆</th>
                  <th>相差（粒）</th>
                </tr>
              </thead>
              <tbody>
                {yard.basins.map((b) => {
                  const over = b.diffToNearestReeling !== null && b.diffToNearestReeling > MAX_DIFF;
                  return (
                    <tr key={b.id} class={over ? "over" : ""}>
                      <td>{b.code}</td>
                      <td>{STATUS_LABEL[b.status]}</td>
                      <td>{b.ringIndex + 1}</td>
                      <td>{b.cocoonCount}</td>
                      <td>{b.nearestReelingCode ?? "—"}</td>
                      <td>{b.diffToNearestReeling ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ))}
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function Shell() {
  const [view, setView] = useState("ring");
  const logout = () => {
    clearToken();
    location.reload();
  };
  // 顶栏切台：用 key 让两页各自保持独立状态
  return view === "ring" ? (
    <RingBoard key="ring" onNav={setView} onLogout={logout} />
  ) : (
    <CocoonBoard key="cocoon" onNav={setView} onLogout={logout} />
  );
}

function App() {
  const [ready] = useState(Boolean(token()));
  return ready ? <Shell /> : <Login onOk={() => location.reload()} />;
}

render(<App />, document.getElementById("app"));
