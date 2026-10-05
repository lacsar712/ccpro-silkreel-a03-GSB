import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, clearToken, setToken, token } from "./api.js";
import "./app.css";

const STATUS_LABEL = { soaking: "浸茧", reeling: "缫丝中", reeled: "已缫完" };

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

function TopBar({ view, onNav, onLogout, title, subtitle }) {
  return (
    <div class="topbar">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <nav class="tabs">
        <button class={view === "yard" ? "on" : ""} onClick={() => onNav("yard")}>
          环盆作业台
        </button>
        <button class={view === "cocoons" ? "on" : ""} onClick={() => onNav("cocoons")}>
          茧粒台
        </button>
        <button onClick={onLogout}>退出</button>
      </nav>
    </div>
  );
}

function Yard({ onNav, onLogout }) {
  const [board, setBoard] = useState(null);
  const [picked, setPicked] = useState(null);
  const [temp, setTemp] = useState("40");
  const [err, setErr] = useState("");

  async function refresh() {
    const data = await api("/api/board");
    setBoard(data);
    if (picked) {
      setPicked(data.basins.find((b) => b.id === picked.id) || data.basins[0]);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  if (!board) {
    return (
      <div class="yard">
        <TopBar view="yard" onNav={onNav} onLogout={onLogout} title="环盆作业台" subtitle="装载环盆…" />
        {err && <p class="err">{err}</p>}
      </div>
    );
  }

  const n = board.basins.length;
  async function writeTemp() {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/readings`, {
        method: "POST",
        body: JSON.stringify({ waterTempC: Number(temp) }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }
  async function setStatus(status) {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div class="yard">
      <TopBar
        view="yard"
        onNav={onNav}
        onLogout={onLogout}
        title={board.filature}
        subtitle={`${board.riverside} · 点盆登记汤温；已缫完须最近汤温 38～42℃；浸茧改缫丝中须与缫丝中邻盆茧粒差 ≤120 粒`}
      />
      <div class="ring">
        {board.basins.map((b, i) => {
          const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
          const left = 50 + Math.cos(angle) * 38;
          const top = 50 + Math.sin(angle) * 38;
          return (
            <button
              key={b.id}
              class={`basin ${b.status}`}
              style={{ left: `${left}%`, top: `${top}%` }}
              onClick={() => setPicked(b)}
            >
              <strong>{b.code}</strong>
              <span>{STATUS_LABEL[b.status]}</span>
            </button>
          );
        })}
      </div>
      {picked && (
        <div class="drawer">
          <h3>
            {picked.code} · {STATUS_LABEL[picked.status]}
          </h3>
          <p>
            茧粒 {picked.cocoonGrains} 粒 · 最近汤温：{picked.latestTempC ?? "无"} ℃ · 记录 {picked.readingCount} 次
          </p>
          <input value={temp} onInput={(e) => setTemp(e.target.value)} />
          <button onClick={writeTemp}>登记汤温</button>
          <div>
            <button disabled={picked.status === "soaking"} onClick={() => setStatus("soaking")}>
              浸茧
            </button>
            <button disabled={picked.status === "reeling"} onClick={() => setStatus("reeling")}>
              缫丝中
            </button>
            <button disabled={picked.status === "reeled"} onClick={() => setStatus("reeled")}>
              已缫完
            </button>
          </div>
          {err && <p class="err">{err}</p>}
        </div>
      )}
    </div>
  );
}

function Cocoons({ onNav, onLogout }) {
  const [data, setData] = useState(null);
  const [dockId, setDockId] = useState("");
  const [err, setErr] = useState("");

  async function refresh() {
    const d = await api("/api/cocoon-board");
    setData(d);
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  const docks = data?.docks ?? [];
  const shown = dockId === "" ? docks : docks.filter((d) => String(d.id) === dockId);

  return (
    <div class="yard">
      <TopBar
        view="cocoons"
        onNav={onNav}
        onLogout={onLogout}
        title="茧粒台"
        subtitle="各盆茧粒与最近缫丝中盆的差 · 只读"
      />
      <div class="panel">
        <label class="filter">
          按坞筛
          <select value={dockId} onChange={(e) => setDockId(e.target.value)}>
            <option value="">全部坞</option>
            {docks.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => refresh().catch((e) => setErr(e.message))}>刷新</button>
      </div>
      {err && <p class="err">{err}</p>}
      {shown.map((dock) => (
        <section key={dock.id} class="panel">
          <h2>
            {dock.name} · {dock.riverside}
          </h2>
          <table class="grains">
            <thead>
              <tr>
                <th>盆位</th>
                <th>状态</th>
                <th>茧粒</th>
                <th>与最近缫丝中盆的差</th>
              </tr>
            </thead>
            <tbody>
              {dock.basins.map((b) => (
                <tr key={b.id}>
                  <td>{b.code}</td>
                  <td>{STATUS_LABEL[b.status]}</td>
                  <td>{b.cocoonGrains} 粒</td>
                  <td>{b.gapToReeling == null ? "—" : `${b.gapToReeling} 粒（邻盆 ${b.neighborCode}）`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(Boolean(token()));
  const [view, setView] = useState("yard");
  if (!ready) {
    return <Login onOk={() => setReady(true)} />;
  }
  const logout = () => {
    clearToken();
    location.reload();
  };
  return view === "yard" ? (
    <Yard onNav={setView} onLogout={logout} />
  ) : (
    <Cocoons onNav={setView} onLogout={logout} />
  );
}

render(<App />, document.getElementById("app"));
